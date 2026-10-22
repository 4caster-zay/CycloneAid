# Select the project environment before importing scientific/GUI dependencies.
if __name__ == "__main__":
    from cycloneaid.launcher import main
    raise SystemExit(main())

import matplotlib
matplotlib.use('Agg')
import tkinter as tk
from tkinter import ttk
import sys
from datetime import datetime, timezone
from tkinter import BooleanVar

from cycloneaid.metadata import APP_NAME, CREATOR, DISPLAY_VERSION as VERSION
from cycloneaid.model import INTENSITY_THRESHOLDS
from cycloneaid.gui_session import SessionScreenMixin
from cycloneaid.ui_theme import (ThemeToggle, apply_theme, get_palette,
                                 load_theme_preference, register_widget, style_widget_tree)

# ─── Optional: tkintermapview ───
try:
    from cycloneaid.map_widget import ManagedMapView
    _HAS_MAP = True
except ImportError:
    _HAS_MAP = False

# Shared semantic styles also initialize ttk controls before the first switch.
CURRENT_THEME_NAME = "Typhoon Dark"
CURRENT_THEME = get_palette(CURRENT_THEME_NAME)


def _set_palette_globals(name):
    global CURRENT_THEME_NAME, CURRENT_THEME
    global PRIMARY_COLOR, DARK_BG, LIGHT_BG, WHITE, TEXT_MUTED, ACCENT, SURFACE, BORDER
    CURRENT_THEME_NAME = name
    CURRENT_THEME = get_palette(name)
    PRIMARY_COLOR, DARK_BG, LIGHT_BG = CURRENT_THEME.primary, CURRENT_THEME.background, CURRENT_THEME.panel
    WHITE, TEXT_MUTED, ACCENT = CURRENT_THEME.text, CURRENT_THEME.muted, CURRENT_THEME.accent
    SURFACE, BORDER = CURRENT_THEME.surface, CURRENT_THEME.border


_set_palette_globals(CURRENT_THEME_NAME)


def set_app_theme(theme_name, app_root, persist=True):
    _set_palette_globals(theme_name)
    apply_theme(app_root, theme_name, persist=persist)
    apply_dark_theme(app_root, dark=theme_name == "Typhoon Dark")


# ─── Intensity colour map (shared with storm_tracker.py) ───
INTENSITY_COLORS = {
    'TD': '#5ebaff', 'TS': '#00faf4', 'STS': '#00ef00',
    'C1': '#ffffcc', 'C2': '#ffe775', 'C3': '#ffc140',
    'C4': '#ff8f20', 'C5': '#ff6060',
}

# ─── Changelog entries (newest first) ───
CHANGELOG = [
    {
        "version": VERSION,
        "date": "2026-10-22",
        "entries": [
            "Open directly into a forecast workspace with embedded chart tabs.",
            "Use explicit map readiness and setup, with independent OSM tile status.",
            "Switch Sky/Typhoon appearance with accessible controls and edit unnamed drafts naturally.",
            "Keep fitted previews, keyboard editing, and project state stable while rendering."
        ],
    },
    {
        "version": "0.10.0a2 (Alpha 2)",
        "date": "2026-10-22",
        "entries": [
            "Generate UTC forecast timestamps with a range preview and one-step undo.",
            "Keep draft coordinates and winds blank; distinguish generated times from interpolated values.",
            "Stabilize preview cleanup, retain diagnostics, and organize alpha testing and repository maintenance."
        ],
    },
    {
        "version": "0.10.0a1 (Alpha 1)",
        "date": "2026-10-21",
        "entries": [
            "Shared validated sessions with atomic project files, recovery, and undo/redo.",
            "Exact-window RI, geodesic heuristic envelopes, and approximate coastline landfall.",
            "Isolated rendering and exports, indexed cities, and incremental map updates."
        ],
    },
    {
        "version": "Alpha 0.9.3",
        "date": "2026-06-08",
        "entries": [
            "🎨 Theme Overhaul — Sleek dynamic toggle buttons for Sky and Typhoon modes.",
            "🖌️ Contrast Fixes — Text in Sky Light mode is now true black, and muted text contrast is fixed.",
            "🔧 Linter Cleanup — Suppressed false-positive IDE warnings for optional modules."
        ],
    },
    {
        "version": "Alpha 0.9.2",
        "date": "2026-05-31",
        "entries": [
            "🎨 Dynamic Theming — Sky Light and Typhoon Dark modes added.",
            "📜 Custom Scrollbars — Themed scrollbars matching the active theme.",
            "🐛 Bug Fix — Addressed internal Tkinter layout warnings for Data Table."
        ],
    },
    {
        "version": "Alpha 0.9.1",
        "date": "2026-05-31",
        "entries": [
            "🚀 Major Optimization — Implemented spatial indexing (R-tree) for city searches",
            "💾 Faster Loading — Cached geography and demographic data across modules",
            "🏗️ Refined Codebase — Decoupled plotting from data fetching for better stability",
            "🏝️ Precision Landfall — Fixed coordinate detection via high-res mask validation",
            "📊 UI Performance — Smoother table interactions via batched validation checks",
        ],
    },
    {
        "version": "Alpha 0.9",
        "date": "2026-05-30",
        "entries": [
            "🗺️ Live Map — Command-center split layout with TkinterMapView",
            "🔗 Two-way sync — Table edits update map markers in real time",
            "📍 Right-click map to add a storm data point with pre-filled coordinates",
            "🏝️ Auto-landfall detection via global-land-mask",
            "📂 KML import support alongside existing CSV / GPX importers",
            "📜 Changelog viewer on the home screen",
            "🎨 Intensity-coloured map markers with storm-type shapes",
        ],
    },
    {
        "version": "Alpha 0.8.1",
        "date": "2026-04-10",
        "entries": [
            "🧵 Threaded rendering — UI no longer freezes during plot generation",
            "📊 Interactive matplotlib preview windows with navigation toolbar",
            "🛡️ Navigation guard — warns before discarding unsaved data",
            "✅ Real-time data validation with visual row highlighting",
        ],
    },
    {
        "version": "Alpha 0.8.0",
        "date": "2026-04-08",
        "entries": [
            "🌀 Rebranded from StormSnitch to CycloneAid",
            "🏠 Redesigned home screen with feature-showcase cards",
            "🎨 Dark-mode UI polish and consistent theming",
        ],
    },
    {
        "version": "Alpha 0.7",
        "date": "2026-04-07",
        "entries": [
            "📋 Export presets (Forecaster / Media) for layer control",
            "⚡ Rapid Intensification (dV/dt) analysis plot",
            "📡 GPX track import with auto-interpolation",
        ],
    },
    {
        "version": "Alpha 0.6",
        "date": "2026-03-28",
        "entries": [
            "📊 Prognostic intensity timeline chart",
            "🌊 Landfall detection with nearest-city lookup",
            "🔄 Row management toolbar (insert, duplicate, reorder)",
        ],
    },
    {
        "version": "Alpha 0.5",
        "date": "2026-03-15",
        "entries": [
            "🗺️ Forecast track plot with uncertainty cone",
            "📈 Wind-speed auto-intensity classification",
            "💾 CSV import / export",
        ],
    },
]


# ═════════════════════════════════════════════════════════════════════════════
# HOME SCREEN
# ═════════════════════════════════════════════════════════════════════════════

class CellEditor:
    """Inline cell editor for Treeview cells — dropdowns, checkboxes, text."""

    def __init__(self, parent, tree, item, column, col_idx, col_name, old_value, on_save_callback):
        self.tree = tree
        self.item = item
        self.column = column
        self.col_idx = col_idx
        self.col_name = col_name
        self.old_value = old_value
        self.on_save_callback = on_save_callback
        self._saving = False
        self.editor = None
        self._value_var = None
        self.frame = None

        bbox = tree.bbox(item, column)
        if not bbox:
            return
        x, y, width, height = bbox
        tree_x, tree_y = tree.winfo_x(), tree.winfo_y()

        self.frame = tk.Frame(parent, bg=DARK_BG, relief=tk.SOLID, borderwidth=2)
        self.frame.place(x=tree_x + x, y=tree_y + y, width=width, height=max(height, 30))
        self.frame.lift()
        self.frame.focus_set()

        editor_map = {
            "Intensity": self._dropdown_intensity,
            "Storm Type": self._dropdown_storm_type,
            "Landfall": self._checkbox_landfall,
            "Interpolated": self._checkbox_interpolated,
        }
        editor_map.get(col_name, self._text_entry)()

    # ── Intensity dropdown ──
    def _dropdown_intensity(self):
        options = ['TD', 'TS', 'STS', 'C1', 'C2', 'C3', 'C4', 'C5']
        var = tk.StringVar(value=self.old_value if self.old_value in options else 'TD')
        cb = ttk.Combobox(self.frame, textvariable=var, values=options, state="readonly", width=10)
        cb.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        cb.focus()
        self._bind_editor(cb, var)
        cb.bind('<<ComboboxSelected>>', lambda event: self._finish())

    # ── Storm Type dropdown ──
    def _dropdown_storm_type(self):
        options = ["Tropical", "Subtropical", "Extratropical", "Low"]
        var = tk.StringVar(value=self.old_value if self.old_value in options else 'Tropical')
        cb = ttk.Combobox(self.frame, textvariable=var, values=options, state="readonly", width=12)
        cb.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        cb.focus()
        self._bind_editor(cb, var)
        cb.bind('<<ComboboxSelected>>', lambda event: self._finish())

    # ── Landfall checkbox ──
    def _checkbox_landfall(self):
        var = BooleanVar(value=self.old_value in ("True", "true", "1"))
        cb = tk.Checkbutton(self.frame, text="Landfall", variable=var, bg=DARK_BG, fg=WHITE,
                            selectcolor=LIGHT_BG, font=("Segoe UI", 10, "bold"),
                            command=lambda: self._save_bool(var, "Landfall"))
        cb.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        cb.focus()
        self._resize_frame(120, 35)
        self._bind_editor(cb, var)

    # ── Interpolated checkbox ──
    def _checkbox_interpolated(self):
        var = BooleanVar(value=self.old_value in ("True", "true", "1"))
        cb = tk.Checkbutton(self.frame, text="Interpolated", variable=var, bg=DARK_BG, fg=WHITE,
                            selectcolor=LIGHT_BG, font=("Segoe UI", 10, "bold"),
                            command=lambda: self._save_bool(var, "Interpolated"))
        cb.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        cb.focus()
        self._resize_frame(120, 35)
        self._bind_editor(cb, var)

    def _save_bool(self, var, label):
        value = "True" if var.get() else "False"
        self._commit_value(value)

    # ── Generic text entry ──
    def _text_entry(self):
        var = tk.StringVar(value=self.old_value)
        entry = tk.Entry(self.frame, textvariable=var, font=("Segoe UI", 10))
        entry.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        entry.focus()
        entry.select_range(0, tk.END)
        self._bind_editor(entry, var)
        entry.bind('<FocusOut>', lambda event: self.commit() if entry.focus_get() is not entry else None)

    # ── Helpers ──
    def _bind_editor(self, widget, variable):
        self.editor, self._value_var = widget, variable
        if isinstance(widget, tk.Entry):
            register_widget(widget, "entry")
        elif isinstance(widget, tk.Checkbutton):
            register_widget(widget, "checkbutton")
        widget.bind('<Return>', self._finish)
        widget.bind('<Escape>', lambda event: self.cancel())
        widget.bind('<Tab>', lambda event: self._navigate(1))
        widget.bind('<Shift-Tab>', lambda event: self._navigate(-1))
        widget.bind('<ISO_Left_Tab>', lambda event: self._navigate(-1))

    def commit(self):
        if self._value_var is not None and self.frame is not None:
            self._commit_value(str(self._value_var.get()))

    def _finish(self, event=None):
        self.commit()
        self.tree.focus_set()
        return 'break'

    def _navigate(self, direction):
        screen = getattr(self.on_save_callback, '__self__', None)
        self.commit()
        if screen is not None:
            screen._edit_adjacent(self.item, self.col_idx, direction)
        return 'break'

    def _resize_frame(self, min_w, min_h):
        self.frame.update_idletasks()
        self.frame.place(width=max(min_w, self.frame.winfo_reqwidth()), height=max(min_h, self.frame.winfo_reqheight()))
        self.frame.lift()

    def _commit_value(self, value):
        if self._saving or self.frame is None:
            return
        self._saving = True
        self.destroy()
        self.on_save_callback(self.item, self.col_idx, value)

    def cancel(self):
        self._saving = True
        self.destroy()
        self.tree.focus_set()
        return 'break'

    def destroy(self):
        if self.frame:
            self.frame.destroy()
            self.frame = None


# ═════════════════════════════════════════════════════════════════════════════
# DATA ENTRY SCREEN — COMMAND CENTER LAYOUT
# ═════════════════════════════════════════════════════════════════════════════

class DataEntryScreen(SessionScreenMixin, tk.Frame):
    """Forecast editor with on-demand embedded chart outputs."""

    INTENSITY_THRESHOLDS = INTENSITY_THRESHOLDS
    COLUMNS = [
        ("Time (UTC)", 22), ("Lead Time (h)", 13), ("Lat", 8), ("Lon", 9),
        ("Wind (kt)", 10), ("Landfall", 9), ("Storm Type", 13),
        ("Intensity", 10), ("Interpolated", 14),
    ]
    STORM_TYPE_OPTIONS = ["Tropical", "Subtropical", "Extratropical", "Low"]
    INTENSITY_OPTIONS = ['TD', 'TS', 'STS', 'C1', 'C2', 'C3', 'C4', 'C5']

    def __init__(self, master, on_back):
        set_app_theme(CURRENT_THEME_NAME, master.winfo_toplevel(), persist=False)
        super().__init__(master, bg=DARK_BG)
        register_widget(self, "background")
        self.on_back = on_back
        self._init_session()
        self.forecaster_confidence_var = tk.StringVar(self, "Moderate")
        self.export_preset_var = tk.StringVar(self, "Forecaster")
        self.storm_name_var = tk.StringVar(self, "")
        self.cell_editor = None
        self._map_markers = {}
        self._map_path = None
        self._create_ui()
        self._start_session()
        self._update_project_status()
        self._refresh_map_readiness()

    def _create_ui(self):
        self._build_topbar()
        self._build_properties()
        self._build_clock_bar()
        self._paned = register_widget(tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=6,
                                                     sashrelief=tk.FLAT, bd=0), "background")
        self._paned.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 8))
        left = ttk.Frame(self._paned, style="Workspace.TFrame")
        self._build_row_toolbar(left)
        self._build_table(left)
        ttk.Label(left, text="Edit: double-click / Enter · Move: Tab · Cancel: Esc",
                  style="Muted.TLabel").pack(fill=tk.X, pady=(6, 0))
        self._paned.add(left, minsize=470, stretch="always")
        right = ttk.Frame(self._paned, style="Workspace.TFrame")
        readiness = ttk.Frame(right, style="Workspace.TFrame")
        readiness.pack(fill=tk.X, pady=(0, 5))
        map_frame = self._build_output_tabs(right)
        self._build_map_panel(map_frame)
        self._build_map_readiness(readiness, osm_parent=self._osm_info).pack(fill=tk.X)
        self._paned.add(right, minsize=330, stretch="always")
        self._pane_ratio = .55
        self._split_after = None
        self._paned.bind('<Configure>', self._initial_split, add='+')
        self._paned.bind('<ButtonRelease-1>', self._remember_split, add='+')
        self._update_action_buttons()

    def _initial_split(self, event):
        if self._split_after is not None:
            self.after_cancel(self._split_after)
        def place():
            self._split_after = None
            self._paned.sash_place(0, int(self._paned.winfo_width()*self._pane_ratio), 0)
        self._split_after = self.after_idle(place)

    def _remember_split(self, event):
        self._pane_ratio = self._paned.sash_coord(0)[0]/max(1, self._paned.winfo_width())

    def _menu_button(self, parent, text, entries):
        button = ttk.Menubutton(parent, text=text, style="Workspace.TMenubutton")
        menu = register_widget(tk.Menu(button, tearoff=0), "menu")
        for label, action in entries:
            if label is None:
                menu.add_separator()
            else:
                menu.add_command(label=label, command=action)
        button.configure(menu=menu)
        return button

    def _build_topbar(self):
        header = ttk.Frame(self, style="Workspace.TFrame", padding=(14, 10, 14, 8))
        header.pack(fill=tk.X)
        ttk.Label(header, text="CycloneAid", style="Title.TLabel").pack(side=tk.LEFT, padx=(0, 16))
        for text, command in (("New", self.new_session), ("Open…", self.open_session), ("Save", self.save_session)):
            ttk.Button(header, text=text, command=command).pack(side=tk.LEFT, padx=(0, 5))
        self._menu_button(header, "Project", [("Save as…", self.save_session_as),
                          ("Open sample", self.open_sample), (None, None),
                          ("Undo", self.undo), ("Redo", self.redo)]).pack(side=tk.LEFT)
        self.theme_toggle = ThemeToggle(header, command=lambda name: set_app_theme(name, self.winfo_toplevel()))
        self.theme_toggle.pack(side=tk.RIGHT)
        self._menu_button(header, "Help", [("About and release notes", self._show_about),
                          ("Validation details", lambda: self._show_validation_dialog(self._validate_data())),
                          ("Map setup", self.prepare_assets)]).pack(side=tk.RIGHT, padx=8)
        self._project_status_var = tk.StringVar(self, "Untitled project · Saved")
        self._project_label = ttk.Label(self, textvariable=self._project_status_var, style="Muted.TLabel")
        self._project_label.pack(fill=tk.X, padx=16, pady=(0, 4))

    def _show_about(self):
        root = self.winfo_toplevel()
        if hasattr(root, 'show_about'):
            root.show_about()
        else:
            from tkinter import messagebox
            messagebox.showinfo("About CycloneAid", f"CycloneAid {VERSION}\nExperimental alpha for testing only.", parent=self)

    def _build_properties(self):
        properties = ttk.Frame(self, style="Workspace.TFrame", padding=(14, 4, 14, 10))
        properties.pack(fill=tk.X)
        name_group = ttk.Frame(properties, style="Workspace.TFrame")
        ttk.Label(name_group, text="Storm name", style="Property.TLabel").pack(side=tk.LEFT, padx=(0, 8))
        self.name_entry = ttk.Entry(name_group, textvariable=self.storm_name_var, width=27)
        self.name_entry.pack(side=tk.LEFT)
        self._bind_name_entry(self.name_entry)
        options = ttk.Frame(properties, style="Workspace.TFrame")
        ttk.Label(options, text="Confidence", style="Property.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Combobox(options, textvariable=self.forecaster_confidence_var, values=["High", "Moderate", "Low"],
                     state="readonly", width=10).pack(side=tk.LEFT, padx=(0, 14))
        ttk.Label(options, text="Preset", style="Property.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Combobox(options, textvariable=self.export_preset_var, values=["Forecaster", "Media"],
                     state="readonly", width=11).pack(side=tk.LEFT, padx=(0, 14))
        ttk.Button(options, text="Session details…", command=self.session_settings).pack(side=tk.LEFT)
        self._properties_compact = None
        def arrange(event):
            compact = event.width < 1180
            if compact == self._properties_compact:
                return
            self._properties_compact = compact
            name_group.grid(row=0, column=0, sticky="w", pady=(0, 6 if compact else 0))
            options.grid(row=1 if compact else 0, column=0 if compact else 1,
                         sticky="w", padx=(0 if compact else 24, 0))
        properties.bind('<Configure>', arrange, add='+')

    def _build_row_toolbar(self, parent):
        toolbar = ttk.Frame(parent, style="Workspace.TFrame", padding=(0, 5, 8, 9))
        toolbar.pack(fill=tk.X)
        primary = ttk.Frame(toolbar, style="Workspace.TFrame")
        primary.grid(row=0, column=0, sticky="w")
        ttk.Label(primary, text="Forecast", style="Title.TLabel").pack(side=tk.LEFT, padx=(0, 12))
        ttk.Button(primary, text="Add", command=self.add_row).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(primary, text="Generate rows…", command=self.generate_rows).pack(side=tk.LEFT, padx=(0, 5))
        self._menu_button(primary, "Rows", [("Insert above", self.insert_row_above),
                          ("Insert below", self.insert_row_below), ("Duplicate", self.duplicate_row),
                          ("Move up", self.move_row_up), ("Move down", self.move_row_down),
                          (None, None), ("Delete selected", self.remove_row),
                          ("Clear all…", self.clear_table)]).pack(side=tk.LEFT, padx=(0, 5))
        self._row_io_button = self._menu_button(toolbar, "Import / Export", [("Import CSV…", self.import_csv),
                          ("Import GPX…", self.import_gpx), ("Import KML / KMZ…", self.import_kml),
                          (None, None), ("Export CSV…", self.export_csv)])
        self._row_io_button.grid(row=0, column=1, sticky="w")
        self._toolbar_compact = None
        def arrange(event):
            compact = event.width < 600
            if compact != self._toolbar_compact:
                self._toolbar_compact = compact
                self._row_io_button.grid_configure(row=1 if compact else 0, column=0 if compact else 1,
                                                   pady=(5 if compact else 0, 0))
        toolbar.bind('<Configure>', arrange, add='+')

    def _build_table(self, parent):
        from tkinter import font as tkfont
        self.table_frame = ttk.Frame(parent, style="Workspace.TFrame")
        self.table_frame.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(self.table_frame, columns=[c[0] for c in self.COLUMNS], show="headings", height=12)
        heading_font = tkfont.Font(root=self, font=ttk.Style(self).lookup('Treeview.Heading', 'font') or 'TkHeadingFont')
        for column, width in self.COLUMNS:
            self.tree.heading(column, text=column)
            self.tree.column(column, width=max(width*8, heading_font.measure(column)+24),
                             minwidth=55, stretch=False, anchor="center")
        vsb = ttk.Scrollbar(self.table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(self.table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.table_frame.rowconfigure(0, weight=1)
        self.table_frame.columnconfigure(0, weight=1)
        self.tree.bind('<Double-1>', self._on_double_click)
        self.tree.bind('<Button-3>', self._show_row_context_menu)
        self.tree.bind('<Return>', self._edit_selected)
        self.tree.bind('<F2>', self._edit_selected)
        self.tree.bind('<Tab>', self._edit_selected)
        self.tree.tag_configure('invalid', background=CURRENT_THEME.INVALID_BG, foreground=CURRENT_THEME.INVALID_FG)
        self.tree.tag_configure('warning', background=CURRENT_THEME.WARNING_BG, foreground=ACCENT)
        self.tree.tag_configure('normal', background=SURFACE, foreground=WHITE)

    def _build_map_panel(self, parent):
        header = ttk.Frame(parent, style="Workspace.TFrame", padding=(8, 8, 8, 4))
        header.pack(fill=tk.X)
        ttk.Label(header, text="Interactive map", style="Workspace.TLabel").pack(side=tk.LEFT)
        ttk.Button(header, text="Fit track", command=self.fit_map).pack(side=tk.RIGHT)
        self._osm_info = ttk.Frame(parent, style="Workspace.TFrame", padding=(8, 0, 8, 4))
        self._osm_info.pack(fill=tk.X)
        self._map_host = ttk.Frame(parent, style="Workspace.TFrame")
        self._map_host.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.map_widget = None
        self._retry_live_map()

    def _retry_live_map(self):
        position, zoom, cached_tiles = (14.5, 121.0), 5, {}
        previous = self.map_widget
        if previous is not None:
            position, zoom = previous.get_position(), previous.zoom
            cached_tiles = dict(previous.tile_image_cache)
            previous.destroy()
        for child in self._map_host.winfo_children():
            child.destroy()
        self._map_markers, self._map_state = {}, {}
        self._map_path, self._path_coordinates = None, ()
        self.map_widget = None
        failure = "Install the desktop extra; chart previews remain available."
        if _HAS_MAP:
            try:
                widget = ManagedMapView(self._map_host, corner_radius=0)
                self.map_widget = widget
                widget.set_tile_server("https://tile.openstreetmap.org/{z}/{x}/{y}.png")
                widget.tile_image_cache.update(cached_tiles)
                widget.pack(fill=tk.BOTH, expand=True)
                widget.set_position(*position)
                widget.set_zoom(zoom)
                widget.add_right_click_menu_command("Add forecast position here", self._on_map_right_click, pass_coords=True)
                self._refresh_osm_status("loading")
                self._sync_map()
                return
            except Exception as exc:
                from cycloneaid.diagnostics import error_message
                failure = error_message("Live map initialization", exc)
                if self.map_widget is not None:
                    self.map_widget.destroy()
                self.map_widget = None
        title = "Live map is unavailable" if _HAS_MAP else "Live map is not installed"
        ttk.Label(self._map_host, text=title, style="Title.TLabel", anchor=tk.CENTER).pack(pady=(12, 6))
        detail = ("Retry or check the desktop dependencies."
                  if _HAS_MAP else "Install the desktop extra, then relaunch.")
        ttk.Label(self._map_host, text=detail+"\nChart maps work independently.",
                  justify=tk.CENTER, style="Muted.TLabel", wraplength=300).pack(padx=12)
        self._refresh_osm_status("unavailable" if _HAS_MAP else "not_installed", failure if _HAS_MAP else "")

    def _build_clock_bar(self):
        bar = ttk.Frame(self, style="Workspace.TFrame", padding=(14, 5))
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        self._status_lbl = ttk.Label(bar, text="Ready", style="Muted.TLabel", width=32, anchor=tk.W)
        self._status_lbl.pack(side=tk.LEFT)
        self._render_progress = ttk.Progressbar(bar, mode="indeterminate", length=70)
        self._validation_var = tk.StringVar(self, "Add forecast rows to begin")
        self._validation_label = ttk.Label(bar, textvariable=self._validation_var, style="Muted.TLabel",
                                           cursor="hand2", takefocus=True)
        self._validation_label.pack(side=tk.LEFT, padx=8)
        self._validation_label.bind('<Button-1>', lambda event: self._show_validation_dialog(self._validate_data()))
        self._validation_label.bind('<Return>', lambda event: self._show_validation_dialog(self._validate_data()))
        self._clock_var = tk.StringVar(self, "")
        ttk.Label(bar, textvariable=self._clock_var, style="Muted.TLabel").pack(side=tk.RIGHT)
        ttk.Label(bar, text="Alpha · testing only", style="Muted.TLabel").pack(side=tk.RIGHT, padx=(0, 16))
        self._tick_clock()

    def _tick_clock(self):
        if not self.winfo_exists():
            return
        self._clock_var.set(datetime.now(timezone.utc).strftime("%H:%MZ"))
        widget = getattr(self, 'map_widget', None)
        if widget is not None and hasattr(widget, 'tile_availability'):
            state, detail = widget.tile_availability()
            self._refresh_osm_status(state, detail)
        self._clock_after = self.after(1000, self._tick_clock)

    def _show_row_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
        menu = register_widget(tk.Menu(self, tearoff=0), "menu")
        for label, action in [("Insert above", self.insert_row_above), ("Insert below", self.insert_row_below),
                              ("Duplicate", self.duplicate_row), ("Move up", self.move_row_up),
                              ("Move down", self.move_row_down), ("Delete", self.remove_row)]:
            menu.add_command(label=label, command=action)
        menu.tk_popup(event.x_root, event.y_root)

    def _on_double_click(self, event):
        item, column = self.tree.identify_row(event.y), self.tree.identify_column(event.x)
        if item and column:
            self._edit_cell(item, int(column[1:])-1)
        return 'break'

    def _edit_selected(self, event=None):
        selected = self.tree.selection()
        rows = self.tree.get_children()
        if selected or rows:
            self._edit_cell(selected[0] if selected else rows[0], 0)
        return 'break'

    def _edit_cell(self, item, column):
        if self.cell_editor and self.cell_editor.frame is not None:
            self.cell_editor.commit()
        self.tree.selection_set(item)
        self.tree.focus(item)
        self.tree.see(item)
        # Bring an off-screen column into view before placing its editor.
        columns = [name for name, _ in self.COLUMNS]
        total = sum(self.tree.column(name, 'width') for name in columns)
        offset = sum(self.tree.column(name, 'width') for name in columns[:column])
        visible = self.tree.winfo_width()
        current = self.tree.xview()[0]*total
        if offset < current or offset+self.tree.column(columns[column], 'width') > current+visible-20:
            self.tree.xview_moveto(max(0, min(1, offset/max(1, total))))
        self.tree.update_idletasks()
        name = columns[column]
        self.cell_editor = CellEditor(self.table_frame, self.tree, item, f'#{column+1}', column,
                                      name, self.tree.set(item, name), self._on_cell_save)

    def _edit_adjacent(self, item, column, direction):
        rows = self.tree.get_children()
        if item not in rows:
            return
        index = rows.index(item)*len(self.COLUMNS)+column+direction
        if 0 <= index < len(rows)*len(self.COLUMNS):
            self._edit_cell(rows[index//len(self.COLUMNS)], index % len(self.COLUMNS))
        else:
            self.tree.focus_set()


# ═════════════════════════════════════════════════════════════════════════════
# APPLICATION ROOT
# ═════════════════════════════════════════════════════════════════════════════

def apply_dark_theme(window, dark=True):
    """Enable immersive dark mode for Windows 10/11 titlebar."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            window.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
            if not hwnd:
                hwnd = window.winfo_id()
            
            rendering = ctypes.c_int(int(dark))
            # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Windows 11)
            res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(rendering), ctypes.sizeof(rendering)
            )
            if res != 0:
                # DWMWA_USE_IMMERSIVE_DARK_MODE = 19 (Windows 10)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 19, ctypes.byref(rendering), ctypes.sizeof(rendering)
                )
        except Exception:
            pass


class StormTrackerApp(tk.Tk):
    def report_callback_exception(self, exc, value, tb):
        import traceback
        from cycloneaid.diagnostics import error_message
        error_message('Tk callback', value, ''.join(traceback.format_exception(exc, value, tb)))

    def __init__(self):
        super().__init__()
        set_app_theme(load_theme_preference(), self, persist=False)
        self.title(f"{APP_NAME} — {VERSION}")
        self.geometry("1600x900")
        self.minsize(1000, 650)
        self.current_frame = None
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(100, self._maximize)
        self.show_data_entry()

    def _close(self):
        if isinstance(self.current_frame, DataEntryScreen) and not self.current_frame._confirm_leave():
            return
        if self.current_frame:
            self.current_frame.destroy()
        self.destroy()

    def _maximize(self):
        try:
            self.state('zoomed')
        except tk.TclError:
            try:
                self.attributes('-zoomed', True)
            except tk.TclError:
                pass

    def show_home(self):
        # Compatibility entry point; welcome content no longer replaces a forecast.
        return self.show_about()

    def show_about(self):
        window = tk.Toplevel(self)
        window.title("About CycloneAid")
        window.geometry("650x470")
        window.transient(self)
        body = ttk.Frame(window, padding=20)
        body.pack(fill=tk.BOTH, expand=True)
        ttk.Label(body, text=f"CycloneAid {VERSION}", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(body, text=f"Created by {CREATOR} · Experimental forecast graphics · Not for operational use", wraplength=600,
                  style="Muted.TLabel").pack(anchor=tk.W, pady=(8, 16))
        notes = register_widget(tk.Text(body, wrap=tk.WORD, height=12, relief=tk.FLAT, padx=8, pady=8), "entry")
        notes.pack(fill=tk.BOTH, expand=True)
        for release in CHANGELOG:
            notes.insert(tk.END, f"{release['version']} — {release['date']}\n")
            for line in release['entries']:
                notes.insert(tk.END, f"• {line}\n")
            notes.insert(tk.END, '\n')
        notes.configure(state=tk.DISABLED)
        ttk.Button(body, text="Close", command=window.destroy).pack(anchor=tk.E, pady=(12, 0))
        style_widget_tree(window)
        return window

    def show_data_entry(self):
        if self.current_frame:
            if not self.current_frame._confirm_leave():
                return
            self.current_frame.destroy()
        self.current_frame = DataEntryScreen(self, self.show_about)
        self.current_frame.pack(fill=tk.BOTH, expand=True)
