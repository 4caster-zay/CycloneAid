"""Tk session adapter. Widgets display immutable model state; workers never read Tk."""
from dataclasses import replace
from pathlib import Path
import pickle
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import pandas as pd
from cycloneaid.model import derive_intensity, utc_timestamp
from cycloneaid.session import (ForecastRow, SessionController, parse_row, validate_session,
                                ForecastSession, SessionSettings, save_project, load_project, recovery_path)
from cycloneaid.imports import read_tracks, prepare_track
from cycloneaid.rendering import RenderCoordinator, RenderRequest
from cycloneaid.diagnostics import error_message
from validation import validate_forecast_points
from cycloneaid.gui_name import NameEditingMixin
from cycloneaid.gui_maps import MapReadinessMixin
from cycloneaid.gui_outputs import OutputTabsMixin
from cycloneaid.ui_theme import style_widget_tree


class SessionScreenMixin(NameEditingMixin, MapReadinessMixin, OutputTabsMixin):
    def _init_session(self):
        self.controller = SessionController(ForecastSession(settings=SessionSettings(storm_name="")))
        self._project_generation = 0
        self._chart_job_project = None
        self._last_geography_mode = self.controller.session.settings.geography_mode
        self._init_name_editing()
        self._init_map_readiness()
        self.renderer = RenderCoordinator()
        self._displayed_rows = {}
        self._displayed_order = ()
        self._map_state = {}
        self._map_markers = {}
        self._map_after = None
        self._fit_pending = False
        self._refreshing = False
        self._previews = {}
        self._project_path = None
        self._validation_revision = -1
        self._closing = False
        self._discard = False
        self._bindings = []
        self._timers = []

    def _start_session(self):
        for variable in (self.forecaster_confidence_var, self.export_preset_var):
            variable.trace_add("write", self._topbar_changed)
        root = self.winfo_toplevel()
        for sequence, action in (("<Control-n>", self.new_session), ("<Control-s>", self.save_session), ("<Control-o>", self.open_session),
                                 ("<Control-z>", self.undo), ("<Control-y>", self.redo),
                                 ("<Delete>", self._on_delete_key)):
            callback = lambda event, fn=action: fn(event)
            self._bindings.append((sequence, root.bind(sequence, callback, add="+")))
        self.controller.mark_saved()
        self._poll_after = self.after(100, self._poll_renderer)
        self._autosave_after = self.after(30000, self._autosave)
        self._recovery_after = self.after(150, self._offer_recovery)

    def _theme(self):
        return sys.modules[type(self).__module__]

    def _topbar_changed(self, *_):
        if self._refreshing:
            return
        settings = replace(self.controller.session.settings,
                           confidence=self.forecaster_confidence_var.get(), preset=self.export_preset_var.get())
        self._commit(settings=settings, infer_issue_time=False)

    def _commit(self, *, rows=None, settings=None, fit=False, infer_issue_time=True):
        if self.controller.commit(rows=rows, settings=settings, infer_issue_time=infer_issue_time):
            self._session_changed(fit=fit)

    def _session_changed(self, fit=False):
        session = self.controller.session
        if session.settings.geography_mode == 'degraded' and self._last_geography_mode != 'degraded':
            self._map_asset_enable_requested = False
        self._last_geography_mode = session.settings.geography_mode
        self.renderer.invalidate(session.revision)
        self._refreshing = True
        try:
            self._sync_name_from_session()
            self.forecaster_confidence_var.set(session.settings.confidence)
            self.export_preset_var.set(session.settings.preset)
        finally:
            self._refreshing = False
        self._display_session()
        self._update_action_buttons()
        self._sync_map(fit=fit)
        self._mark_outputs_stale()
        self._refresh_map_readiness()
        self._update_project_status()

    def _display_session(self):
        session = self.controller.session
        rows = {row.row_id: row for row in session.rows}
        for row_id in self._displayed_rows.keys()-rows.keys():
            self.tree.delete(row_id)
        try:
            issue = utc_timestamp(session.settings.issue_time)
        except (TypeError, ValueError):
            issue = pd.NaT
        for row in session.rows:
            if row != self._displayed_rows.get(row.row_id) or getattr(self, "_displayed_issue", None) != session.settings.issue_time:
                values = list(row.values)
                # Timestamp readability must not depend on other draft cells
                # already having coordinates and wind values.
                try:
                    timestamp = utc_timestamp(row.values[0])
                    if not pd.isna(timestamp):
                        values[0] = timestamp.tz_localize(None).isoformat(sep=" ")
                        values[1] = f"{(timestamp-issue).total_seconds()/3600:g}" if not pd.isna(issue) else ""
                except (TypeError, ValueError, OverflowError):
                    pass
                try:
                    point = parse_row(row)
                    values[3] = f"{point.lon:g}"
                    result = validate_forecast_points([point])
                    tag = 'invalid' if result.has_errors() else ('warning' if result.has_warnings() else 'normal')
                except (TypeError, ValueError, OverflowError):
                    tag = 'invalid'
                if row.row_id in self._displayed_rows:
                    self.tree.item(row.row_id, values=values, tags=(tag,))
                else:
                    self.tree.insert('', 'end', iid=row.row_id, values=values, tags=(tag,))
        order = tuple(row.row_id for row in session.rows)
        if order != self._displayed_order:
            for index, row_id in enumerate(order):
                self.tree.move(row_id, '', index)
        self._displayed_rows, self._displayed_order = rows, order
        self._displayed_issue = session.settings.issue_time

    def _validated(self):
        if self._validation_revision != self.controller.session.revision:
            self._points, self._validation = validate_session(self.controller.session)
            self._validation_revision = self.controller.session.revision
        return self._points, self._validation

    def _validate_data(self):
        return self._validated()[1]

    def _is_table_valid(self):
        return self._validate_data().is_valid

    def _update_action_buttons(self, force_validation=True):
        if not hasattr(self, '_action_btns'):
            return
        valid = self._is_table_valid() and not self.renderer.busy
        for button in self._action_btns:
            button.config(state=tk.NORMAL if valid else tk.DISABLED)
        if hasattr(self, '_validation_var'):
            result = self._validate_data()
            text = (f"{len(result.hard_errors)} issue(s) · review forecast" if result.has_errors() else
                    f"{len(result.soft_warnings)} note(s) · ready to preview" if result.has_warnings() else
                    "Forecast ready")
            if not self.controller.session.rows:
                text = "Add, generate, or import forecast rows to begin"
            self._validation_var.set(text)

    def _set_status(self, text, color=None):
        if hasattr(self, '_status_lbl'):
            options = dict(text=text)
            if color and not isinstance(self._status_lbl, ttk.Label):
                options['fg'] = color
            self._status_lbl.config(**options)

    def _set_buttons_loading(self, loading, message=""):
        self._update_action_buttons()
        self._set_status(message if loading else "Ready")
        if hasattr(self, '_render_progress'):
            if loading:
                self._render_progress.pack(side=tk.LEFT, padx=8, after=self._status_lbl)
                self._render_progress.start(15)
            else:
                self._render_progress.stop()
                self._render_progress.pack_forget()
        if hasattr(self, '_map_asset_job_id'):
            self._refresh_map_readiness()

    def _default_row(self):
        return ["", "0", "", "", "", "False", "Tropical", "TD", "False"]

    def add_row(self, values=None):
        self._commit(rows=(*self.controller.session.rows, ForecastRow(tuple(values or self._default_row()))))

    def generate_rows(self):
        from cycloneaid.gui_generation import GenerateRowsDialog
        return GenerateRowsDialog(self)

    def _insert(self, below):
        selection = self.tree.selection()
        if not selection:
            return
        rows = list(self.controller.session.rows)
        index = next(i for i, row in enumerate(rows) if row.row_id == selection[-1 if below else 0])
        rows.insert(index+int(below), ForecastRow(tuple(self._default_row())))
        self._commit(rows=rows)

    def insert_row_above(self):
        self._insert(False)

    def insert_row_below(self):
        self._insert(True)

    def duplicate_row(self):
        selection = set(self.tree.selection())
        rows = []
        for row in self.controller.session.rows:
            rows.append(row)
            if row.row_id in selection:
                rows.append(ForecastRow(row.values, override_reason=row.override_reason, time_origin=row.time_origin))
        self._commit(rows=rows)

    def _move(self, down):
        rows = list(self.controller.session.rows)
        selection = set(self.tree.selection())
        indices = range(len(rows)-1, -1, -1) if down else range(len(rows))
        for i in indices:
            j = i+(1 if down else -1)
            if rows[i].row_id in selection and 0 <= j < len(rows) and rows[j].row_id not in selection:
                rows[i], rows[j] = rows[j], rows[i]
        self._commit(rows=rows)

    def move_row_up(self):
        self._move(False)

    def move_row_down(self):
        self._move(True)

    def remove_row(self):
        selected = set(self.tree.selection())
        self._commit(rows=[row for row in self.controller.session.rows if row.row_id not in selected])

    def clear_table(self):
        if self.controller.session.rows and messagebox.askyesno("Clear Table", "Clear the forecast? You can undo this action."):
            self._commit(rows=[])

    def undo(self, event=None):
        if event is not None and self._text_input_has_focus() and self.focus_get() is not self._name_entry:
            return
        self._flush_name_edit()
        if self.cell_editor and self.cell_editor.frame is not None:
            return
        if self.controller.undo():
            self._sync_name_from_session(force=True)
            self._session_changed()
        return 'break'

    def redo(self, event=None):
        if event is not None and self._text_input_has_focus() and self.focus_get() is not self._name_entry:
            return
        self._flush_name_edit()
        if self.cell_editor and self.cell_editor.frame is not None:
            return
        if self.controller.redo():
            self._sync_name_from_session(force=True)
            self._session_changed()
        return 'break'

    def _on_cell_save(self, item, col_idx, new_value):
        self.cell_editor = None
        rows = list(self.controller.session.rows)
        index = next((i for i, row in enumerate(rows) if row.row_id == item), None)
        if index is None:
            return
        row = rows[index]
        if str(new_value) == row.values[col_idx]:
            return
        if col_idx == 0:
            try:
                before, after = utc_timestamp(row.values[0]), utc_timestamp(new_value)
                if not pd.isna(before) and before == after:
                    return
            except (TypeError, ValueError, OverflowError):
                pass
        values = list(row.values)
        reason, origin = row.override_reason, row.time_origin
        if col_idx == 7:
            try:
                mismatch = new_value != derive_intensity(float(values[4]))
            except (TypeError, ValueError):
                mismatch = True
            if mismatch:
                reason = simpledialog.askstring("Intensity override", "Reason for this manual intensity classification:",
                                                initialvalue=reason, parent=self)
                if not reason or not reason.strip():
                    return
            else:
                reason = ""
        values[col_idx] = str(new_value)
        if col_idx == 4 and not reason:
            try:
                values[7] = derive_intensity(float(new_value))
            except (TypeError, ValueError):
                pass
        if col_idx == 0:
            origin = "provided"
            values[8] = "False"
        elif col_idx == 1:
            try:
                issue = utc_timestamp(self.controller.session.settings.issue_time)
                if pd.isna(issue):
                    raise ValueError("Set an issue time in Session settings first")
                values[0] = (issue+pd.Timedelta(hours=float(new_value))).isoformat()
                origin, values[8] = "generated", "True"
            except (ValueError, TypeError) as exc:
                messagebox.showerror("Lead time", str(exc))
                return
        elif col_idx == 8:
            origin = "legacy-estimated" if str(new_value) == "True" else "provided"
        rows[index] = replace(row, values=tuple(values), override_reason=reason, time_origin=origin)
        self._commit(rows=rows)
        self.cell_editor = None

    _auto_intensity = staticmethod(derive_intensity)

    def _on_map_right_click(self, coords):
        lat, lon = coords
        values = self._default_row()
        values[2:4] = [f"{lat:.4f}", f"{lon:.4f}"]
        self.add_row(values)

    def _sync_map(self, fit=False):
        self._fit_pending = self._fit_pending or fit
        if self._map_after is not None:
            self.after_cancel(self._map_after)
        self._map_after = self.after(100, self._refresh_map)

    def fit_map(self):
        self._sync_map(fit=True)

    def _refresh_map(self):
        self._map_after = None
        if self.map_widget is None:
            return
        ui = self._theme()
        state, coordinates = {}, []
        for row in self.controller.session.rows:
            try:
                point = parse_row(row)
                if not (-90 <= point.lat <= 90):
                    continue
            except (TypeError, ValueError):
                # A location may be editable before wind/time are entered.
                try:
                    from cycloneaid.model import normalize_longitude
                    lat, lon = float(row.values[2]), normalize_longitude(row.values[3])
                    if not -90 <= lat <= 90:
                        continue
                    point = None
                except (ValueError, TypeError):
                    continue
            lat, lon = (point.lat, point.lon) if point else (lat, lon)
            text = row.values[7]+(" LAND" if row.values[5] == "True" else "")
            color = ui.INTENSITY_COLORS.get(row.values[7], '#ffffff')
            state[row.row_id] = (lat, lon, text, color)
            coordinates.append((lat, lon))
        for row_id in self._map_state.keys()-state.keys():
            self._map_markers.pop(row_id).delete()
        for row_id, current in state.items():
            old = self._map_state.get(row_id)
            marker = self._map_markers.get(row_id)
            if marker is not None and old != current:
                if old[3] != current[3]:
                    marker.delete()
                    marker = None
                else:
                    marker.set_position(current[0], current[1])
                    marker.set_text(current[2])
            if marker is None:
                self._map_markers[row_id] = self.map_widget.set_marker(
                    current[0], current[1], text=current[2], marker_color_circle=current[3],
                    marker_color_outside=current[3])
        self._map_state = state
        if tuple(coordinates) != getattr(self, '_path_coordinates', ()):
            if self._map_path is not None:
                if len(coordinates) >= 2:
                    self._map_path.set_position_list(coordinates)
                else:
                    self._map_path.delete()
                    self._map_path = None
            elif len(coordinates) >= 2:
                self._map_path = self.map_widget.set_path(coordinates, color=ui.PRIMARY_COLOR, width=3)
            self._path_coordinates = tuple(coordinates)
        if self._fit_pending and coordinates:
            lats, lons = zip(*coordinates)
            if len(coordinates) > 1 and (min(lats) != max(lats) or min(lons) != max(lons)):
                self.map_widget.fit_bounding_box((max(lats), min(lons)), (min(lats), max(lons)))
            else:
                self.map_widget.set_position(lats[0], lons[0])
                self.map_widget.set_zoom(8)
        self._fit_pending = False

    def _import(self, extension):
        self._flush_pending_edits()
        types = {"csv": [("CSV files", "*.csv")], "gpx": [("GPX files", "*.gpx")],
                 "kml": [("KML/KMZ files", "*.kml *.kmz")]}
        path = filedialog.askopenfilename(filetypes=types[extension])
        if not path:
            return
        try:
            tracks = read_tracks(path)
            index = 0
            if len(tracks) > 1:
                choice = simpledialog.askinteger("Select track", "Import one track:\n"+
                                                  "\n".join(f"{i+1}. {track.name}" for i, track in enumerate(tracks)),
                                                  minvalue=1, maxvalue=len(tracks), parent=self)
                if choice is None:
                    return
                index = choice-1
            track = tracks[index]
            timing = {}
            if any(not str(record.get('time') or '').strip() for record in track.records):
                start = simpledialog.askstring("Missing timestamps", "Explicit UTC start (YYYY-MM-DD HH:MM). Existing times are preserved:", parent=self)
                if start is None:
                    return
                interval = simpledialog.askfloat("Missing timestamps", "Hours between successive positions:", initialvalue=6, minvalue=.001, parent=self)
                if interval is None:
                    return
                timing = dict(start=start, interval_hours=interval)
            notes = []
            if extension != "csv":
                wind = simpledialog.askfloat("Track wind values", "Spatial track has no wind data. Initialize points to this wind (kt) for editing:",
                                             initialvalue=0, minvalue=0, parent=self)
                if wind is None:
                    return
                from cycloneaid.imports import ImportTrack
                track = ImportTrack(track.name, tuple(dict(record, wind_kt=wind) for record in track.records))
                notes.append(f"Imported spatial track: winds initialized by operator to {wind:g} kt")
            rows, warnings = prepare_track(track, **timing, override_resolver=lambda i, point: simpledialog.askstring(
                "Imported intensity override", f"Row {i}: reason for {point.intensity_class} at {point.wind_kt:g} kt:", parent=self))
            settings = replace(self.controller.session.settings, issue_time=parse_row(rows[0]).time.isoformat(),
                               import_notes="; ".join((*notes, *warnings)))
            self._close_session_details()
            self._project_generation += 1
            self._commit(rows=rows, settings=settings, fit=True)
            if warnings or notes:
                messagebox.showwarning("Import notes", "\n".join((*notes, *warnings)))
        except Exception as exc:
            messagebox.showerror("Import Error", str(exc))

    def import_csv(self):
        self._import("csv")

    def import_gpx(self):
        self._import("gpx")

    def import_kml(self):
        self._import("kml")

    def export_csv(self):
        self._flush_pending_edits()
        points, result = self._validated()
        if result.has_errors():
            self._show_validation_dialog(result)
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if path:
            try:
                from cycloneaid.csvio import export_csv
                export_csv(points, path)
                self._set_status(f"CSV exported: {path}")
            except Exception as exc:
                messagebox.showerror("Export Error", str(exc))

    def save_session(self, event=None):
        self._flush_pending_edits()
        path = self._project_path or filedialog.asksaveasfilename(
            defaultextension=".cycloneaid.json", filetypes=[("CycloneAid project", "*.cycloneaid.json"), ("JSON", "*.json")])
        if not path:
            return False
        try:
            save_project(self.controller.session, path)
            self._project_path = path
            self.controller.mark_saved()
            self._update_project_status()
            recovery_path().unlink(missing_ok=True)
            self._set_status(f"Project saved: {Path(path).name}")
            return True
        except Exception as exc:
            messagebox.showerror("Project save", str(exc))
            return False

    def save_session_as(self):
        previous = self._project_path
        self._project_path = None
        if not self.save_session():
            self._project_path = previous

    def open_session(self, event=None):
        self._flush_pending_edits()
        path = filedialog.askopenfilename(filetypes=[("CycloneAid project", "*.json")])
        if not path:
            return
        try:
            session = load_project(path)
            if self._confirm_leave():
                self._replace_project(session, path)
                self._set_status(f"Opened {Path(path).name}")
        except Exception as exc:
            messagebox.showerror("Open project", str(exc), parent=self)

    def new_session(self, event=None):
        if self._confirm_leave():
            self._replace_project(ForecastSession(settings=SessionSettings(storm_name="")))
            self._set_status("New forecast project")

    def open_sample(self):
        from importlib.resources import files, as_file
        try:
            with as_file(files('cycloneaid').joinpath('data/sample.cycloneaid.json')) as path:
                session = load_project(path)
            if self._confirm_leave():
                self._replace_project(session)
                self._set_status("Opened synthetic TEST PALAU sample")
        except Exception as exc:
            messagebox.showerror("Open sample", str(exc), parent=self)

    def _replace_project(self, session, path=None):
        self._close_session_details()
        self._project_generation += 1
        self._clear_outputs()
        self.controller.reset(session)
        self._project_path = str(path) if path is not None else None
        self._discard = False
        self._sync_name_from_session(force=True)
        self._session_changed(fit=True)

    def _update_project_status(self):
        if not hasattr(self, '_project_status_var'):
            return
        filename = Path(self._project_path).name if self._project_path else 'Untitled project'
        dirty = self.controller.dirty or self._has_pending_name_edit()
        status = 'Unsaved changes' if dirty else 'Saved' if self._project_path else 'Not saved'
        self._project_status_var.set(f"{filename} · {status} · {len(self.controller.session.rows)} rows")

    def _text_input_has_focus(self):
        focus = self.focus_get()
        return isinstance(focus, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox, tk.Spinbox, ttk.Spinbox))

    def _flush_pending_edits(self):
        editor = getattr(self, 'cell_editor', None)
        if editor is not None and editor.frame is not None:
            editor.commit()
        self._flush_name_edit()

    def _recovery_session(self):
        session = self.controller.session
        if self._has_pending_name_edit():
            session = replace(session, settings=replace(session.settings, storm_name=self.storm_name_var.get()))
        return session

    def _autosave(self):
        identifier = getattr(self, '_autosave_after', None)
        if identifier is not None:
            self.after_cancel(identifier)
            self._autosave_after = None
        if self.controller.dirty or self._has_pending_name_edit():
            try:
                save_project(self._recovery_session(), recovery_path())
            except Exception as exc:
                self._set_status(f"Recovery save failed: {exc}", '#ff8080')
        self._autosave_after = self.after(30000, self._autosave)

    def _offer_recovery(self):
        path = recovery_path()
        if path.exists():
            try:
                session = load_project(path)
                if messagebox.askyesno("Recover session", "Restore the recovery copy from the previous session?"):
                    self._close_session_details()
                    self._project_generation += 1
                    self._name_pending = False
                    self._commit(rows=session.rows, settings=session.settings, fit=True, infer_issue_time=False)
                    self._sync_name_from_session(force=True)
                else:
                    path.unlink(missing_ok=True)
            except Exception as exc:
                messagebox.showerror("Recovery", str(exc))

    def _close_session_details(self):
        window = getattr(self, '_settings_window', None)
        if window is not None and window.winfo_exists():
            window.destroy()
        self._settings_window = None

    def session_settings(self):
        self._flush_pending_edits()
        previous = getattr(self, '_settings_window', None)
        if previous is not None and previous.winfo_exists():
            previous.lift()
            return
        window = tk.Toplevel(self)
        self._settings_window = window
        window.title("Session details")
        values = {}
        settings = self.controller.session.settings
        project_generation = self._project_generation
        for i, (field, label) in enumerate((("issue_time", "Issue time (UTC)"), ("source", "Source agency"),
                                           ("wind_averaging_period", "Wind averaging period"),
                                           ("geography_mode", "Chart maps"))):
            ttk.Label(window, text=label).grid(row=i, column=0, padx=14, pady=8, sticky='w')
            variable = tk.StringVar(value=getattr(settings, field))
            values[field] = variable
            if field == "geography_mode":
                variable.set("Full maps" if settings.geography_mode == 'full' else "Without basemap")
                widget = ttk.Combobox(window, textvariable=variable,
                                     values=("Full maps", "Without basemap"), state="readonly")
            else:
                widget = ttk.Entry(window, textvariable=variable, width=36)
            widget.grid(row=i, column=1, padx=10, pady=6)
        mask_qc = tk.BooleanVar(value=settings.landmask_qc)
        ttk.Checkbutton(window, text="Optional land-mask point QC (loads ~1 GB)", variable=mask_qc).grid(
            row=4, column=0, columnspan=2, padx=10, pady=6)
        def save():
            if project_generation != self._project_generation:
                self._close_session_details()
                return
            try:
                changes = {field: var.get().strip() for field, var in values.items()}
                changes['geography_mode'] = {'Full maps': 'full', 'Without basemap': 'degraded'}[changes['geography_mode']]
                if changes['geography_mode'] == 'degraded':
                    self._map_asset_enable_requested = False
                if changes['issue_time']:
                    timestamp = utc_timestamp(changes['issue_time'])
                    if pd.isna(timestamp):
                        raise ValueError("Issue time is invalid")
                    changes['issue_time'] = timestamp.isoformat()
                for field in ('source', 'wind_averaging_period'):
                    changes[field] = changes[field] or 'Unknown'
                self._commit(settings=replace(self.controller.session.settings, landmask_qc=mask_qc.get(), **changes),
                             infer_issue_time=False)
                window.destroy()
            except Exception as exc:
                messagebox.showerror("Session settings", str(exc), parent=window)
        ttk.Button(window, text="Apply", command=save, style="Accent.TButton").grid(row=5, column=1, padx=10, pady=14, sticky='e')
        window.transient(self.winfo_toplevel())
        style_widget_tree(window)

    def _start_plot(self, product, save=False):
        self._flush_pending_edits()
        try:
            request = RenderRequest.from_session(self.controller.session, product)
            if product != 'ri' and request.settings.geography_mode == 'full':
                from cycloneaid.geography import geography_readiness
                if geography_readiness():
                    raise ValueError("Map setup needed. Choose Prepare maps, or explicitly continue without basemap.")
            path, view_state = None, ()
            if save:
                path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG image", "*.png")])
                if not path:
                    return
                previous = self._previews.get(product)
                if previous and previous[2] == request.revision:
                    view_state = tuple((ax.get_xlim(), ax.get_ylim()) for ax in previous[0].axes)
            job_id = self.renderer.submit(request, path, view_state)
            self._chart_job_project = (job_id, self._project_generation)
            self._output_render_started(product, save=save)
            self._set_buttons_loading(True, f"{'Exporting' if save else 'Rendering'} {product}…")
        except Exception as exc:
            self._output_render_finished(product, error=str(exc))
            self._set_status("Review chart tab for details")
            error_message(f'{product} request', exc)

    def preview_track(self):
        self._start_plot('track')

    def save_track(self):
        self._start_plot('track', True)

    def preview_prognostic(self):
        self._start_plot('prognostic')

    def save_prognostic(self):
        self._start_plot('prognostic', True)

    def preview_ri(self):
        self._start_plot('ri')

    def save_ri(self):
        self._start_plot('ri', True)

    def _poll_renderer(self):
        result = self.renderer.poll()
        if result is not None:
            if self._handle_map_asset_result(result):
                self._poll_after = self.after(100, self._poll_renderer)
                return
            self._set_buttons_loading(False)
            owner = getattr(self, '_chart_job_project', None)
            if owner is not None and owner[0] == result.job_id:
                self._chart_job_project = None
                if owner[1] != self._project_generation:
                    if result.error:
                        error_message(f'Previous project {result.product} render', result.error, result.detail)
                        self._set_status("Previous project render failed; current project was kept")
                    elif result.path:
                        self._set_status(f"Saved earlier project snapshot: {Path(result.path).name}")
                    else:
                        self._set_status("Previous project preview discarded")
                    self._poll_after = self.after(100, self._poll_renderer)
                    return
            if result.error:
                diagnostic = error_message(f'{result.product} render (revision {result.revision})',
                                           result.error, result.detail)
                self._output_render_finished(result.product, error=diagnostic)
                self._set_status(f"{result.product.title()} failed — see chart tab")
            elif result.path:
                self._output_render_finished(result.product, exported=True)
                self._set_status(f"Saved {Path(result.path).name}")
            elif result.revision == self.controller.session.revision:
                figure = None
                try:
                    figure = pickle.loads(result.figure_bytes)
                    self._show_preview(figure, result.product, result.revision)
                    self._set_status("Preview ready")
                except Exception as exc:
                    if figure is not None and self._previews.get(result.product, (None,))[0] is not figure:
                        import matplotlib.pyplot as plt
                        plt.close(figure)
                    diagnostic = error_message(f'{result.product} preview', exc)
                    self._output_render_finished(result.product, error=diagnostic)
                    self._set_status("Preview failed — see chart tab")
            else:
                self._output_render_finished(result.product, obsolete=True)
                self._set_status("Obsolete preview discarded; refresh the edited forecast")
        self._poll_after = self.after(100, self._poll_renderer)

    def _show_validation_dialog(self, result, is_warning=False):
        text = "\n".join((*result.hard_errors, *result.soft_warnings))
        if result.has_errors():
            messagebox.showerror("Validation errors", text)
        elif text:
            messagebox.showwarning("Forecast notes", text)

    def _confirm_leave(self):
        self._flush_pending_edits()
        if self.controller.dirty:
            answer = messagebox.askyesnocancel("Unsaved project", "Save your project before leaving?")
            if answer is None or (answer and not self.save_session()):
                return False
            if not answer:
                self._discard = True
                recovery_path().unlink(missing_ok=True)
        return True

    def _on_back_guarded(self):
        if self._confirm_leave():
            self.on_back()

    def _on_delete_key(self, event):
        if self.focus_get() == self.tree:
            self.remove_row()
            return 'break'

    def destroy(self):
        if self._closing:
            return
        self._closing = True
        for name in ('_render_progress', '_map_preparation_progress'):
            progress = getattr(self, name, None)
            if progress is not None:
                progress.stop()
        if (self.controller.dirty or self._has_pending_name_edit()) and not self._discard:
            try:
                save_project(self._recovery_session(), recovery_path())
            except OSError:
                pass
        self.renderer.close()
        self._clear_outputs()
        for name in ('_map_after', '_poll_after', '_autosave_after', '_recovery_after', '_clock_after', '_split_after'):
            identifier = getattr(self, name, None)
            if identifier is not None:
                self.after_cancel(identifier)
        root = self.winfo_toplevel()
        for sequence, identifier in self._bindings:
            root.unbind(sequence, identifier)
        super().destroy()
