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
                                save_project, load_project, recovery_path)
from cycloneaid.imports import read_tracks, prepare_track
from cycloneaid.rendering import RenderCoordinator, RenderRequest
from cycloneaid.diagnostics import error_message
from validation import validate_forecast_points


class _PreviewWindow(tk.Toplevel):
    figure_canvas = None

    def destroy(self):
        if self.figure_canvas is not None:
            canvas = self.figure_canvas
            # Embedded canvases have no Tk FigureManager to cancel these jobs.
            for name in ('_idle_draw_id', '_event_loop_id'):
                identifier = getattr(canvas, name, None)
                if identifier is not None:
                    canvas.get_tk_widget().after_cancel(identifier)
                    setattr(canvas, name, None)
        super().destroy()


class SessionScreenMixin:
    def _init_session(self):
        self.controller = SessionController()
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
        for variable in (self.storm_name_var, self.forecaster_confidence_var, self.export_preset_var):
            variable.trace_add("write", self._topbar_changed)
        root = self.winfo_toplevel()
        for sequence, action in (("<Control-s>", self.save_session), ("<Control-o>", self.open_session),
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
                           storm_name=self.storm_name_var.get().strip() or "CycloneAid",
                           confidence=self.forecaster_confidence_var.get(), preset=self.export_preset_var.get())
        self._commit(settings=settings)

    def _commit(self, *, rows=None, settings=None, fit=False, infer_issue_time=True):
        if self.controller.commit(rows=rows, settings=settings, infer_issue_time=infer_issue_time):
            self._session_changed(fit=fit)

    def _session_changed(self, fit=False):
        session = self.controller.session
        self.renderer.invalidate(session.revision)
        self._refreshing = True
        try:
            self.storm_name_var.set(session.settings.storm_name)
            self.forecaster_confidence_var.set(session.settings.confidence)
            self.export_preset_var.set(session.settings.preset)
        finally:
            self._refreshing = False
        self._display_session()
        self._update_action_buttons()
        self._sync_map(fit=fit)
        for product, (figure, window, revision) in self._previews.items():
            if revision != session.revision:
                window.title(f"{product.title()} Preview — previous session state")

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
                try:
                    point = parse_row(row)
                    if not pd.isna(point.time):
                        values[0] = point.time.tz_localize(None).isoformat(sep=" ")
                        values[1] = f"{(point.time-issue).total_seconds()/3600:g}" if not pd.isna(issue) else ""
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

    def _set_status(self, text, color="#aaa"):
        if hasattr(self, '_status_lbl'):
            self._status_lbl.config(text=text, fg=color)

    def _set_buttons_loading(self, loading, message=""):
        self._update_action_buttons()
        self._set_status(message if loading else "Ready")

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
        if self.cell_editor and self.cell_editor.frame is not None:
            return
        if self.controller.undo():
            self._session_changed()
        return 'break'

    def redo(self, event=None):
        if self.cell_editor and self.cell_editor.frame is not None:
            return
        if self.controller.redo():
            self._session_changed()
        return 'break'

    def _on_cell_save(self, item, col_idx, new_value):
        self.cell_editor = None
        rows = list(self.controller.session.rows)
        index = next((i for i, row in enumerate(rows) if row.row_id == item), None)
        if index is None:
            return
        row = rows[index]
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
        path = self._project_path or filedialog.asksaveasfilename(
            defaultextension=".cycloneaid.json", filetypes=[("CycloneAid project", "*.cycloneaid.json"), ("JSON", "*.json")])
        if not path:
            return False
        try:
            save_project(self.controller.session, path)
            self._project_path = path
            self.controller.mark_saved()
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
        path = filedialog.askopenfilename(filetypes=[("CycloneAid project", "*.json")])
        if not path:
            return
        try:
            session = load_project(path)
            self._commit(rows=session.rows, settings=session.settings, fit=True)
            self._project_path = path
            self.controller.mark_saved()
        except Exception as exc:
            messagebox.showerror("Open project", str(exc))

    def _autosave(self):
        identifier = getattr(self, '_autosave_after', None)
        if identifier is not None:
            self.after_cancel(identifier)
            self._autosave_after = None
        if self.controller.dirty:
            try:
                save_project(self.controller.session, recovery_path())
            except Exception as exc:
                self._set_status(f"Recovery save failed: {exc}", '#ff8080')
        self._autosave_after = self.after(30000, self._autosave)

    def _offer_recovery(self):
        path = recovery_path()
        if path.exists():
            try:
                session = load_project(path)
                if messagebox.askyesno("Recover session", "Restore the recovery copy from the previous session?"):
                    self._commit(rows=session.rows, settings=session.settings, fit=True)
                else:
                    path.unlink(missing_ok=True)
            except Exception as exc:
                messagebox.showerror("Recovery", str(exc))

    def session_settings(self):
        window = tk.Toplevel(self)
        window.title("Session settings")
        values = {}
        settings = self.controller.session.settings
        for i, (field, label) in enumerate((("issue_time", "Issue time (UTC)"), ("source", "Source agency"),
                                           ("wind_averaging_period", "Wind averaging period"),
                                           ("geography_mode", "Geography (full/degraded)"))):
            tk.Label(window, text=label).grid(row=i, column=0, padx=10, pady=6, sticky='w')
            variable = tk.StringVar(value=getattr(settings, field))
            values[field] = variable
            if field == "geography_mode":
                widget = ttk.Combobox(window, textvariable=variable, values=("full", "degraded"), state="readonly")
            else:
                widget = tk.Entry(window, textvariable=variable, width=36)
            widget.grid(row=i, column=1, padx=10, pady=6)
        mask_qc = tk.BooleanVar(value=settings.landmask_qc)
        tk.Checkbutton(window, text="Optional land-mask point QC (loads ~1 GB)", variable=mask_qc).grid(
            row=4, column=0, columnspan=2, padx=10, pady=6)
        def save():
            try:
                changes = {field: var.get().strip() for field, var in values.items()}
                if changes['issue_time']:
                    timestamp = utc_timestamp(changes['issue_time'])
                    if pd.isna(timestamp):
                        raise ValueError("Issue time is invalid")
                    changes['issue_time'] = timestamp.isoformat()
                for field in ('source', 'wind_averaging_period'):
                    changes[field] = changes[field] or 'Unknown'
                self._commit(settings=replace(settings, landmask_qc=mask_qc.get(), **changes))
                window.destroy()
            except Exception as exc:
                messagebox.showerror("Session settings", str(exc), parent=window)
        tk.Button(window, text="Apply", command=save).grid(row=5, column=1, pady=10)
        window.transient(self.winfo_toplevel())

    def prepare_assets(self):
        from cycloneaid.geography import geography_readiness
        missing = geography_readiness()
        if not missing:
            messagebox.showinfo("Map assets", "All required Natural Earth assets are cached. OSM tiles still require connectivity.")
            return
        if messagebox.askyesno("Prepare map assets", f"Download {len(missing)} missing Natural Earth datasets for offline charts?"):
            try:
                self.renderer.submit("assets")
                self._set_buttons_loading(True, "Preparing map assets…")
            except Exception as exc:
                messagebox.showerror("Map assets", str(exc))

    def _start_plot(self, product, save=False):
        try:
            request = RenderRequest.from_session(self.controller.session, product)
            path = None
            view_state = ()
            if save:
                path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG image", "*.png")])
                if not path:
                    return
                previous = self._previews.get(product)
                if previous and previous[2] == request.revision:
                    view_state = tuple((ax.get_xlim(), ax.get_ylim()) for ax in previous[0].axes)
            self.renderer.submit(request, path, view_state)
            self._set_buttons_loading(True, f"{'Exporting' if save else 'Rendering'} {product}…")
        except Exception as exc:
            messagebox.showerror("Chart error", error_message(f'{product} request', exc))

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
            self._set_buttons_loading(False)
            if result.error:
                messagebox.showerror("Chart error", error_message(
                    f'{result.product} render (revision {result.revision})', result.error, result.detail))
            elif result.product == 'assets':
                self._set_status("Map assets ready for offline charts")
            elif result.path:
                self._set_status(f"Saved {result.product}: {result.path}")
            elif result.revision == self.controller.session.revision:
                figure = None
                try:
                    figure = pickle.loads(result.figure_bytes)  # Same-build, local child-process IPC only.
                    self._show_preview(figure, result.product, result.revision)
                    validation = self._validate_data()
                    if validation.has_warnings():
                        self._show_validation_dialog(validation)
                except Exception as exc:
                    if figure is not None and self._previews.get(result.product, (None,))[0] is not figure:
                        import matplotlib.pyplot as plt
                        plt.close(figure)
                    messagebox.showerror("Preview error", error_message(f'{result.product} preview', exc))
            else:
                self._set_status("Obsolete preview discarded; generate a preview of the edited forecast")
        self._poll_after = self.after(100, self._poll_renderer)

    def _show_validation_dialog(self, result, is_warning=False):
        text = "\n".join((*result.hard_errors, *result.soft_warnings))
        if result.has_errors():
            messagebox.showerror("Validation errors", text)
        elif text:
            messagebox.showwarning("Forecast notes", text)

    def _show_preview(self, figure, product, revision):
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        window = None
        try:
            window = _PreviewWindow(self)
            window.title(f"{product.title()} Preview — {self.controller.session.settings.storm_name}")
            window.geometry('1000x750')
            self._theme().apply_dark_theme(window)
            canvas = FigureCanvasTkAgg(figure, master=window)
            window.figure_canvas = canvas
            screen = self
            class Toolbar(NavigationToolbar2Tk):
                def save_figure(self, *args):
                    screen._start_plot(product, save=True)
            toolbar = Toolbar(canvas, window, pack_toolbar=False)
            toolbar.pack(side=tk.BOTTOM, fill=tk.X)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            canvas.draw_idle()
        except Exception:
            if window is not None:
                window.destroy()
            plt.close(figure)
            raise
        if product in self._previews:
            self._previews[product][1].destroy()
        self._previews[product] = (figure, window, revision)
        def closed(event):
            if event.widget is window:
                plt.close(figure)
                if self._previews.get(product, (None,))[0] is figure:
                    self._previews.pop(product, None)
        window.bind('<Destroy>', closed)

    def _confirm_leave(self):
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
        if self.controller.dirty and not self._discard:
            try:
                save_project(self.controller.session, recovery_path())
            except OSError:
                pass
        self.renderer.close()
        for figure, window, revision in list(self._previews.values()):
            window.destroy()
        for name in ('_map_after', '_poll_after', '_autosave_after', '_recovery_after', '_clock_after'):
            identifier = getattr(self, name, None)
            if identifier is not None:
                self.after_cancel(identifier)
        root = self.winfo_toplevel()
        for sequence, identifier in self._bindings:
            root.unbind(sequence, identifier)
        super().destroy()
