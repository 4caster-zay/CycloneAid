import matplotlib
matplotlib.use('Agg')
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import pandas as pd
import os
import importlib.util
import sys
import tempfile
from datetime import datetime, timezone, timedelta
import time as _time
from PIL import Image, ImageTk
from tkinter import BooleanVar
import threading
import xml.etree.ElementTree as ET

APP_NAME = "CycloneAid"
VERSION = "Alpha 0.9.1"
CREATOR = "Forecaster Zayed"

# ─── Dynamic Module Imports ───
_base_dir = os.path.dirname(os.path.abspath(__file__))

def _load_module(name, filename):
    """Load a sibling module by filename."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(_base_dir, filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

storm_tracker = _load_module("storm_tracker", "storm_tracker.py")
storm_prognostic = _load_module("storm_prognostic", "storm_prognostic.py")
storm_ri_plot = _load_module("storm_RI_plot", "storm_RI_plot.py")

try:
    from export_preset import get_preset
except ImportError:
    get_preset = None

# ─── Optional: landmask for auto landfall ───
try:
    from global_land_mask import globe as _globe
    _HAS_LANDMASK = True
except ImportError:
    _HAS_LANDMASK = False

# ─── Optional: tkintermapview ───
try:
    import tkintermapview
    _HAS_MAP = True
except ImportError:
    _HAS_MAP = False

# ─── Theme Tokens ───
PRIMARY_COLOR = "#00adb5"
DARK_BG = "#222831"
LIGHT_BG = "#393e46"
WHITE = "#eeeeee"
ACCENT = "#FFD700"
SURFACE = "#2b303b"
BORDER = "#444"

# ─── Intensity colour map (shared with storm_tracker.py) ───
INTENSITY_COLORS = {
    'TD': '#5ebaff', 'TS': '#00faf4', 'STS': '#00ef00',
    'C1': '#ffffcc', 'C2': '#ffe775', 'C3': '#ffc140',
    'C4': '#ff8f20', 'C5': '#ff6060',
}

# ─── Changelog entries (newest first) ───
CHANGELOG = [
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

class HomeScreen(tk.Frame):
    """Home screen with feature showcase, changelog, and launch button."""

    FEATURES = [
        {"icon": "🗺️", "title": "Storm Track Plot",
         "desc": "High-fidelity forecast track maps with\nuncertainty cones, city overlays, and\nintensity classification.",
         "color": "#00adb5"},
        {"icon": "📊", "title": "Prognostic Chart",
         "desc": "Intensity timelines with auto-detected\ncategory changes, landfall events, and\ncity proximity analysis.",
         "color": "#FF6B6B"},
        {"icon": "⚡", "title": "Rapid Intensification",
         "desc": "dV/dt intensity change rates with WMO RI\nthreshold highlighting and peak-event\nannotation.",
         "color": "#FFD700"},
        {"icon": "📋", "title": "Data Management",
         "desc": "Excel-like row management: insert,\nduplicate, reorder, edit cells with\ndropdowns. CSV / GPX / KML import.",
         "color": "#48CFAD"},
        {"icon": "🗺️", "title": "Live Map View",
         "desc": "Interactive slippy map with real-time\nmarker sync, right-click data entry,\nand auto landfall detection.",
         "color": "#FF9F43"},
        {"icon": "✅", "title": "Data Validation",
         "desc": "Automatic QC checks on coordinates,\nwind speed, time ordering, and\nintensity consistency.",
         "color": "#4FC1E9"},
    ]

    def __init__(self, master, on_start):
        super().__init__(master, bg=DARK_BG)
        self.on_start = on_start
        self._changelog_visible = False
        self._changelog_frame = None
        self._create_ui()

    # ── Build ──
    def _create_ui(self):
        # Bottom bar (pack first → stays at bottom)
        self._build_bottom_bar()

        # Scrollable content
        scroll_container = tk.Frame(self, bg=DARK_BG)
        scroll_container.pack(fill=tk.BOTH, expand=True)

        self._canvas = tk.Canvas(scroll_container, bg=DARK_BG, highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(scroll_container, orient=tk.VERTICAL, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._content = tk.Frame(self._canvas, bg=DARK_BG)
        self._cw_id = self._canvas.create_window((0, 0), window=self._content, anchor=tk.N)
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(self._cw_id, width=e.width))
        self._content.bind("<Configure>", lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind_all("<MouseWheel>", lambda e: self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        self._build_hero()
        self._build_story()
        self._build_feature_cards()
        self._build_changelog_toggle()

    # ── Bottom bar ──
    def _build_bottom_bar(self):
        bar = tk.Frame(self, bg="#1a1e25", bd=1, relief=tk.SUNKEN)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Label(bar, text="⚠️  ALPHA — For testing and development only. Not for operational use.  ⚠️",
                 font=("Segoe UI", 10, "bold"), fg=DARK_BG, bg=ACCENT, padx=10, pady=5).pack(fill=tk.X)
        tk.Label(bar, text=f"Created by {CREATOR}  •  {VERSION}  •  Report bugs and feedback",
                 font=("Segoe UI", 9), fg="#888", bg="#1a1e25", pady=4).pack(fill=tk.X)

    # ── Hero section ──
    def _build_hero(self):
        hero = tk.Frame(self._content, bg=DARK_BG)
        hero.pack(fill=tk.X, pady=(30, 10))

        tk.Label(hero, text="🌀", font=("Segoe UI Emoji", 56), bg=DARK_BG, fg=PRIMARY_COLOR).pack()
        try:
            name_font = ("Century Gothic", 42, "bold")
            tk.Label(hero, text=APP_NAME.upper(), font=name_font, fg=PRIMARY_COLOR, bg=DARK_BG).pack(pady=(0, 2))
        except Exception:
            tk.Label(hero, text=APP_NAME.upper(), font=("Segoe UI", 42, "bold"), fg=PRIMARY_COLOR, bg=DARK_BG).pack(pady=(0, 2))

        tk.Label(hero, text="Tropical Cyclone Forecast Track & Intensity Analysis Suite",
                 font=("Segoe UI", 13), fg="#aaa", bg=DARK_BG).pack(pady=(0, 4))

        ver_frame = tk.Frame(hero, bg=DARK_BG)
        ver_frame.pack(pady=(2, 12))
        tk.Label(ver_frame, text=f" {VERSION} ", font=("Consolas", 11, "bold"),
                 fg=DARK_BG, bg=ACCENT, padx=8, pady=2).pack(side=tk.LEFT, padx=4)

        # Launch button
        start_btn = tk.Button(
            hero, text="  🚀  Launch CycloneAid  ",
            font=("Segoe UI", 16, "bold"), bg=PRIMARY_COLOR, fg=DARK_BG,
            width=26, height=2, command=self.on_start, relief=tk.FLAT, bd=0,
            activebackground=ACCENT, activeforeground=DARK_BG, cursor="hand2",
        )
        start_btn.pack(pady=(4, 16))
        start_btn.configure(highlightthickness=0, borderwidth=0)
        start_btn.bind("<Enter>", lambda e: start_btn.config(bg=ACCENT))
        start_btn.bind("<Leave>", lambda e: start_btn.config(bg=PRIMARY_COLOR))

        # Divider
        sep = tk.Frame(hero, bg=DARK_BG)
        sep.pack(fill=tk.X, padx=80, pady=(0, 8))
        tk.Frame(sep, bg=LIGHT_BG, height=1).pack(fill=tk.X)

    # ── Origin story ──
    def _build_story(self):
        sf = tk.Frame(self._content, bg=LIGHT_BG, padx=20, pady=14,
                      highlightthickness=1, highlightbackground=BORDER)
        sf.pack(fill=tk.X, padx=60, pady=(4, 14))

        tk.Label(sf, text="💡  Why CycloneAid?", font=("Segoe UI", 13, "bold"),
                 fg=ACCENT, bg=LIGHT_BG, anchor=tk.W).pack(anchor=tk.W, pady=(0, 6))

        story = (
            "Forecaster Zayed built CycloneAid because he was absolutely tired of manually "
            "drawing storm track charts on Canva every single time a cyclone spun up. 😤🎨\n\n"
            "What started as \"there HAS to be a better way\" turned into a full forecast analysis "
            "suite — auto-generated track maps, prognostic timelines, RI analysis, and proper "
            "dark-mode cartography. No more dragging arrows around in a graphic design tool. "
            "Now the data does the drawing."
        )
        tk.Label(sf, text=story, font=("Segoe UI", 10), fg="#ccc", bg=LIGHT_BG,
                 justify=tk.LEFT, anchor=tk.W, wraplength=700).pack(anchor=tk.W)

    # ── Feature cards ──
    def _build_feature_cards(self):
        tk.Label(self._content, text="✦  Features  ✦", font=("Segoe UI", 14, "bold"),
                 fg=ACCENT, bg=DARK_BG).pack(pady=(4, 10))

        grid = tk.Frame(self._content, bg=DARK_BG)
        grid.pack(fill=tk.X, padx=40, pady=(0, 16))
        for i, feat in enumerate(self.FEATURES):
            row, col = divmod(i, 3)
            self._make_card(grid, feat, row, col)
        for c in range(3):
            grid.columnconfigure(c, weight=1)

    def _make_card(self, parent, feat, row, col):
        card = tk.Frame(parent, bg=LIGHT_BG, bd=0, padx=14, pady=12,
                        highlightthickness=1, highlightbackground=BORDER, highlightcolor=feat["color"])
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

        tk.Label(card, text=feat["icon"], font=("Segoe UI Emoji", 28), bg=LIGHT_BG, fg=feat["color"]).pack(anchor=tk.W)
        tk.Label(card, text=feat["title"], font=("Segoe UI", 12, "bold"), fg=feat["color"], bg=LIGHT_BG, anchor=tk.W).pack(anchor=tk.W, pady=(2, 4))
        tk.Label(card, text=feat["desc"], font=("Segoe UI", 9), fg="#ccc", bg=LIGHT_BG, justify=tk.LEFT, anchor=tk.W).pack(anchor=tk.W)

        def _enter(e, c=card, clr=feat["color"]):
            c.config(highlightbackground=clr, highlightthickness=2)
        def _leave(e, c=card):
            c.config(highlightbackground=BORDER, highlightthickness=1)
        for w in [card] + list(card.winfo_children()):
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)

    # ── Changelog toggle ──
    def _build_changelog_toggle(self):
        """A clickable bar that expands/collapses the full changelog."""
        self._cl_toggle_frame = tk.Frame(self._content, bg=DARK_BG)
        self._cl_toggle_frame.pack(fill=tk.X, padx=60, pady=(0, 4))

        self._cl_btn = tk.Button(
            self._cl_toggle_frame,
            text="📜  View Changelog  ▾",
            font=("Segoe UI", 11, "bold"), fg=PRIMARY_COLOR, bg=LIGHT_BG,
            activebackground=ACCENT, activeforeground=DARK_BG,
            relief=tk.FLAT, cursor="hand2", bd=0, padx=16, pady=6,
            command=self._toggle_changelog,
        )
        self._cl_btn.pack(fill=tk.X)
        self._cl_btn.bind("<Enter>", lambda e: self._cl_btn.config(bg=ACCENT, fg=DARK_BG))
        self._cl_btn.bind("<Leave>", lambda e: self._cl_btn.config(bg=LIGHT_BG, fg=PRIMARY_COLOR))

        # Container for changelog entries (initially hidden)
        self._changelog_container = tk.Frame(self._content, bg=DARK_BG)

    def _toggle_changelog(self):
        if self._changelog_visible:
            self._changelog_container.pack_forget()
            self._cl_btn.config(text="📜  View Changelog  ▾")
            self._changelog_visible = False
        else:
            # Build entries lazily on first open
            if not self._changelog_container.winfo_children():
                self._populate_changelog()
            self._changelog_container.pack(fill=tk.X, padx=60, pady=(0, 20))
            self._cl_btn.config(text="📜  Hide Changelog  ▴")
            self._changelog_visible = True
        # Refresh scroll region
        self._content.update_idletasks()
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _populate_changelog(self):
        for entry in CHANGELOG:
            ver_frame = tk.Frame(self._changelog_container, bg=SURFACE, padx=16, pady=10,
                                 highlightthickness=1, highlightbackground=BORDER)
            ver_frame.pack(fill=tk.X, pady=4)

            header = tk.Frame(ver_frame, bg=SURFACE)
            header.pack(fill=tk.X)
            tk.Label(header, text=entry["version"], font=("Segoe UI", 12, "bold"),
                     fg=PRIMARY_COLOR, bg=SURFACE).pack(side=tk.LEFT)
            tk.Label(header, text=entry["date"], font=("Consolas", 9),
                     fg="#888", bg=SURFACE).pack(side=tk.RIGHT)

            for line in entry["entries"]:
                tk.Label(ver_frame, text=f"  {line}", font=("Segoe UI", 9),
                         fg="#ccc", bg=SURFACE, anchor=tk.W, justify=tk.LEFT).pack(anchor=tk.W, pady=1)


# ═════════════════════════════════════════════════════════════════════════════
# CELL EDITOR
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
        self.editor = None
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
        save = lambda _=None: (self.on_save_callback(self.item, self.col_idx, var.get()) if var.get() else None, self.destroy())
        cb.bind('<Return>', save)
        cb.bind('<Escape>', lambda _: self.cancel())
        cb.bind('<FocusOut>', save)
        cb.event_generate('<Button-1>')

    # ── Storm Type dropdown ──
    def _dropdown_storm_type(self):
        options = ["Tropical", "Subtropical", "Extratropical", "Low"]
        var = tk.StringVar(value=self.old_value if self.old_value in options else 'Tropical')
        cb = ttk.Combobox(self.frame, textvariable=var, values=options, state="readonly", width=12)
        cb.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        cb.focus()
        save = lambda _=None: (self.on_save_callback(self.item, self.col_idx, var.get()) if var.get() else None, self.destroy())
        cb.bind('<Return>', save)
        cb.bind('<Escape>', lambda _: self.cancel())
        cb.bind('<FocusOut>', save)
        cb.event_generate('<Button-1>')

    # ── Landfall checkbox ──
    def _checkbox_landfall(self):
        var = BooleanVar(value=self.old_value in ("True", "true", "1"))
        cb = tk.Checkbutton(self.frame, text="Landfall", variable=var, bg=DARK_BG, fg=WHITE,
                            selectcolor=LIGHT_BG, font=("Segoe UI", 10, "bold"),
                            command=lambda: self._save_bool(var, "Landfall"))
        cb.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        cb.focus()
        self._resize_frame(120, 35)

    # ── Interpolated checkbox ──
    def _checkbox_interpolated(self):
        var = BooleanVar(value=self.old_value in ("True", "true", "1"))
        cb = tk.Checkbutton(self.frame, text="Interpolated", variable=var, bg=DARK_BG, fg=WHITE,
                            selectcolor=LIGHT_BG, font=("Segoe UI", 10, "bold"),
                            command=lambda: self._save_bool(var, "Interpolated"))
        cb.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        cb.focus()
        self._resize_frame(120, 35)

    def _save_bool(self, var, label):
        value = "True" if var.get() else "False"
        self.on_save_callback(self.item, self.col_idx, value)
        self.frame.after(150, self.destroy)

    # ── Generic text entry ──
    def _text_entry(self):
        var = tk.StringVar(value=self.old_value)
        entry = tk.Entry(self.frame, textvariable=var, font=("Segoe UI", 10))
        entry.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        entry.focus()
        entry.select_range(0, tk.END)
        save = lambda _=None: (self.on_save_callback(self.item, self.col_idx, var.get()), self.destroy())
        entry.bind('<Return>', save)
        entry.bind('<Escape>', lambda _: self.cancel())
        entry.bind('<FocusOut>', save)

    # ── Helpers ──
    def _resize_frame(self, min_w, min_h):
        self.frame.update_idletasks()
        self.frame.place(width=max(min_w, self.frame.winfo_reqwidth()), height=max(min_h, self.frame.winfo_reqheight()))
        self.frame.lift()

    def cancel(self):
        self.destroy()

    def destroy(self):
        if self.frame:
            self.frame.destroy()
            self.frame = None


# ═════════════════════════════════════════════════════════════════════════════
# DATA ENTRY SCREEN — COMMAND CENTER LAYOUT
# ═════════════════════════════════════════════════════════════════════════════

class DataEntryScreen(tk.Frame):
    """Split-pane command center: data table on the left, live map on the right."""

    INTENSITY_THRESHOLDS = [
        (137, 'C5'), (113, 'C4'), (96, 'C3'), (83, 'C2'),
        (64, 'C1'), (48, 'STS'), (34, 'TS'), (0, 'TD'),
    ]
    COLUMNS = [
        ("Time (UTC)", 18), ("Lead Time (h)", 10), ("Lat", 8), ("Lon", 8),
        ("Wind (kt)", 10), ("Landfall", 8), ("Storm Type", 12),
        ("Intensity", 10), ("Interpolated", 10),
    ]
    STORM_TYPE_OPTIONS = ["Tropical", "Subtropical", "Extratropical", "Low"]
    INTENSITY_OPTIONS = ['TD', 'TS', 'STS', 'C1', 'C2', 'C3', 'C4', 'C5']

    def __init__(self, master, on_back):
        super().__init__(master, bg=DARK_BG)
        self.on_back = on_back
        self.forecaster_confidence_var = tk.StringVar(value="Moderate")
        self.storm_name_var = tk.StringVar(value="CycloneAid")
        self.cell_editor = None
        self.intensity_overrides = set()
        self.last_fig = None
        self.last_prognostic_fig = None
        self.last_ri_fig = None
        self._map_markers = []
        self._map_path = None
        self._syncing_map = False
        self._create_ui()

    # ─────────────────────────────────────────────────────────
    # UI CONSTRUCTION
    # ─────────────────────────────────────────────────────────
    def _create_ui(self):
        self._build_topbar()

        # Main split — PanedWindow
        self._paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=DARK_BG,
                                     sashwidth=4, sashrelief=tk.RAISED, bd=0)
        self._paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 2))

        # LEFT pane — data table + controls
        left = tk.Frame(self._paned, bg=DARK_BG)
        self._build_table(left)
        self._build_row_toolbar(left)
        self._build_action_buttons(left)
        self._paned.add(left, minsize=520, stretch="always")

        # RIGHT pane — live map
        right = tk.Frame(self._paned, bg=DARK_BG)
        self._build_map_panel(right)
        self._paned.add(right, minsize=300, stretch="always")

        # Bottom clock
        self._build_clock_bar()

        # Initial row
        self.add_row()

    # ── Top bar ──
    def _build_topbar(self):
        topbar = tk.Frame(self, bg=DARK_BG)
        tk.Button(topbar, text="← Home", command=self._on_back_guarded, bg=LIGHT_BG, fg=WHITE,
                  font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=8, pady=8)
        tk.Label(topbar, text="🌀 Storm Data Entry", font=("Segoe UI", 18, "bold"),
                 fg=PRIMARY_COLOR, bg=DARK_BG).pack(side=tk.LEFT, padx=12)

        tk.Label(topbar, text="Storm Name:", font=("Segoe UI", 11, "bold"), fg=WHITE, bg=DARK_BG).pack(side=tk.LEFT, padx=(30, 2))
        tk.Entry(topbar, textvariable=self.storm_name_var, font=("Segoe UI", 11), width=16, justify="center").pack(side=tk.LEFT, padx=2)

        tk.Label(topbar, text="Confidence:", font=("Segoe UI", 11), fg=WHITE, bg=DARK_BG).pack(side=tk.LEFT, padx=(20, 2))
        ttk.Combobox(topbar, textvariable=self.forecaster_confidence_var,
                     values=["High", "Moderate", "Low"], state="readonly", width=10).pack(side=tk.LEFT, padx=2)

        tk.Label(topbar, text="Preset:", font=("Segoe UI", 11), fg=WHITE, bg=DARK_BG).pack(side=tk.LEFT, padx=(20, 2))
        self.export_preset_var = tk.StringVar(value="Forecaster")
        ttk.Combobox(topbar, textvariable=self.export_preset_var,
                     values=["Forecaster", "Media"], state="readonly", width=10).pack(side=tk.LEFT, padx=2)

        topbar.pack(fill=tk.X, pady=(0, 4))

    # ── Treeview table ──
    def _build_table(self, parent):
        self.table_frame = tk.Frame(parent, bg=DARK_BG)
        self.table_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        columns = [c[0] for c in self.COLUMNS]
        self.tree = ttk.Treeview(self.table_frame, columns=columns, show="headings", height=8)
        for col, w in self.COLUMNS:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w * 10, anchor="center")

        vsb = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.table_frame.grid_rowconfigure(0, weight=1)
        self.table_frame.grid_columnconfigure(0, weight=1)

        self.tree.bind('<Double-1>', self._on_double_click)
        self.tree.bind('<Button-3>', self._show_row_context_menu)

        self.tree.tag_configure('invalid', background='#4a1a1a', foreground='#ff8080')
        self.tree.tag_configure('warning', background='#3a3a00', foreground=ACCENT)
        self.tree.tag_configure('normal', background=DARK_BG, foreground=WHITE)

        self.bind_all("<Delete>", self._on_delete_key)
        self.bind_all("<Control-s>", lambda e: self.export_csv())

    # ── Row management toolbar ──
    def _build_row_toolbar(self, parent):
        bf = tk.Frame(parent, bg=DARK_BG)

        tk.Label(bf, text="Rows:", font=("Segoe UI", 10, "bold"), fg=ACCENT, bg=DARK_BG).pack(side=tk.LEFT, padx=(4, 8))
        self._tb(bf, "➕ Add", self.add_row, PRIMARY_COLOR, DARK_BG)
        self._tb(bf, "⬆ Above", self.insert_row_above, LIGHT_BG, WHITE)
        self._tb(bf, "⬇ Below", self.insert_row_below, LIGHT_BG, WHITE)
        self._tb(bf, "📋 Dup", self.duplicate_row, LIGHT_BG, WHITE)
        self._tb(bf, "➖ Del", self.remove_row, "#c0392b", WHITE)
        self._tb(bf, "🔼", self.move_row_up, LIGHT_BG, WHITE)
        self._tb(bf, "🔽", self.move_row_down, LIGHT_BG, WHITE)

        tk.Frame(bf, bg=DARK_BG, width=12).pack(side=tk.LEFT)
        tk.Label(bf, text="Table:", font=("Segoe UI", 10, "bold"), fg=ACCENT, bg=DARK_BG).pack(side=tk.LEFT, padx=(4, 8))
        self._tb(bf, "🗑️ Clear", self.clear_table, "#c0392b", WHITE)

        tk.Frame(bf, bg=DARK_BG, width=12).pack(side=tk.LEFT)
        tk.Label(bf, text="I/O:", font=("Segoe UI", 10, "bold"), fg=ACCENT, bg=DARK_BG).pack(side=tk.LEFT, padx=(4, 8))
        self._tb(bf, "📂 CSV", self.import_csv, LIGHT_BG, WHITE)
        self._tb(bf, "📡 GPX", self.import_gpx, LIGHT_BG, WHITE)
        self._tb(bf, "📂 KML", self.import_kml, LIGHT_BG, WHITE)
        self._tb(bf, "💾 Export", self.export_csv, LIGHT_BG, WHITE)

        bf.pack(fill=tk.X, padx=4, pady=4)

    def _tb(self, parent, text, cmd, bg, fg):
        """Create a styled toolbar button with hover."""
        btn = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                        font=("Segoe UI", 9, "bold"), relief=tk.FLAT, cursor="hand2",
                        padx=5, pady=2, bd=0)
        btn.bind("<Enter>", lambda e, b=btn: b.config(bg=ACCENT, fg=DARK_BG))
        btn.bind("<Leave>", lambda e, b=btn, _bg=bg, _fg=fg: b.config(bg=_bg, fg=_fg))
        btn.pack(side=tk.LEFT, padx=2, pady=2)
        return btn

    # ── Action buttons (Track / Prognostic / RI) ──
    def _build_action_buttons(self, parent):
        af = tk.Frame(parent, bg=DARK_BG)

        for label, preview_cmd, save_cmd in [
            ("Track Plot", self.preview_track, self.save_track),
            ("Prognostic Plot", self.preview_prognostic, self.save_prognostic),
            ("RI (dV/dt) Plot", self.preview_ri, self.save_ri),
        ]:
            grp = tk.LabelFrame(af, text=label, font=("Segoe UI", 9, "bold"),
                                fg=ACCENT, bg=DARK_BG, bd=1, relief=tk.GROOVE, padx=6, pady=4)
            prev = tk.Button(grp, text="👁️ Preview", command=preview_cmd, bg=PRIMARY_COLOR, fg=DARK_BG,
                             font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2")
            save = tk.Button(grp, text="🖼️ Save", command=save_cmd, bg=LIGHT_BG, fg=WHITE,
                             font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2")
            prev.pack(side=tk.LEFT, padx=3, pady=2)
            save.pack(side=tk.LEFT, padx=3, pady=2)
            grp.pack(side=tk.LEFT, padx=6, pady=4)

        af.pack(pady=4)

        # Collect action buttons for enabling/disabling
        self._action_btns = []
        for grp in af.winfo_children():
            for child in grp.winfo_children():
                if isinstance(child, tk.Button):
                    self._action_btns.append(child)
        self._update_action_buttons()

    # ── Live Map Panel ──
    def _build_map_panel(self, parent):
        header = tk.Frame(parent, bg=DARK_BG)
        tk.Label(header, text="🗺️ Live Map", font=("Segoe UI", 14, "bold"),
                 fg=PRIMARY_COLOR, bg=DARK_BG).pack(side=tk.LEFT, padx=8)

        if not _HAS_MAP:
            tk.Label(header, text="(tkintermapview not installed)", font=("Segoe UI", 9, "italic"),
                     fg="#ff8080", bg=DARK_BG).pack(side=tk.LEFT, padx=4)
        header.pack(fill=tk.X, pady=(4, 2))

        if _HAS_MAP:
            self.map_widget = tkintermapview.TkinterMapView(parent, corner_radius=0)
            self.map_widget.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            # Default centre — western Pacific
            self.map_widget.set_position(14.5, 121.0)
            self.map_widget.set_zoom(5)
            # Use OpenStreetMap tiles (default)
            self.map_widget.set_tile_server("https://tile.openstreetmap.org/{z}/{x}/{y}.png")
            # Right-click → add storm data point
            self.map_widget.add_right_click_menu_command(
                "📍 Add Storm Data Here", self._on_map_right_click, pass_coords=True
            )
        else:
            fallback = tk.Frame(parent, bg=SURFACE)
            fallback.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            tk.Label(fallback, text="🗺️", font=("Segoe UI Emoji", 48), bg=SURFACE, fg="#555").pack(expand=True)
            tk.Label(fallback, text="Install tkintermapview to enable\nthe live map panel.",
                     font=("Segoe UI", 11), fg="#888", bg=SURFACE, justify=tk.CENTER).pack()
            self.map_widget = None

    # ── Bottom Clock Bar ──
    def _build_clock_bar(self):
        bar = tk.Frame(self, bg="#1a1e25", bd=1, relief=tk.SUNKEN)
        bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(2, 0))

        left = tk.Frame(bar, bg="#1a1e25")
        left.pack(side=tk.LEFT, padx=12, pady=6)

        tk.Label(left, text="🕐", font=("Segoe UI Emoji", 16), bg="#1a1e25", fg=PRIMARY_COLOR).pack(side=tk.LEFT, padx=(0, 6))

        zf = tk.Frame(left, bg="#1a1e25")
        zf.pack(side=tk.LEFT)
        self._zulu_lbl = tk.Label(zf, text="", font=("Consolas", 14, "bold"), fg=PRIMARY_COLOR, bg="#1a1e25")
        self._zulu_lbl.pack(anchor=tk.W)
        self._zulu_date = tk.Label(zf, text="", font=("Consolas", 9), fg="#888", bg="#1a1e25")
        self._zulu_date.pack(anchor=tk.W)

        tk.Frame(left, bg=LIGHT_BG, width=2).pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=2)

        lf = tk.Frame(left, bg="#1a1e25")
        lf.pack(side=tk.LEFT)
        self._local_lbl = tk.Label(lf, text="", font=("Consolas", 12), fg=ACCENT, bg="#1a1e25")
        self._local_lbl.pack(anchor=tk.W)
        self._local_tz = tk.Label(lf, text="", font=("Consolas", 9), fg="#888", bg="#1a1e25")
        self._local_tz.pack(anchor=tk.W)

        right = tk.Frame(bar, bg="#1a1e25")
        right.pack(side=tk.RIGHT, padx=12, pady=6)
        self._row_count_lbl = tk.Label(right, text="Rows: 0", font=("Segoe UI", 10, "bold"), fg=WHITE, bg="#1a1e25")
        self._row_count_lbl.pack(side=tk.RIGHT, padx=(10, 0))
        self._status_lbl = tk.Label(right, text="Ready", font=("Segoe UI", 10), fg="#aaa", bg="#1a1e25")
        self._status_lbl.pack(side=tk.RIGHT)

        self._tick_clock()

    def _tick_clock(self):
        if not self.winfo_exists():
            return
        now_utc = datetime.now(timezone.utc)
        self._zulu_lbl.config(text=now_utc.strftime("%H:%M:%SZ"))
        self._zulu_date.config(text=now_utc.strftime("%Y-%m-%d  UTC+0 (Zulu)"))

        now_local = datetime.now()
        tz_name = _time.strftime("%Z")
        offset_sec = _time.timezone if _time.daylight == 0 else _time.altzone
        offset_hrs = -offset_sec / 3600
        sign = "+" if offset_hrs >= 0 else ""
        self._local_lbl.config(text=now_local.strftime("%H:%M:%S"))
        self._local_tz.config(text=f"{now_local.strftime('%Y-%m-%d')}  {tz_name} (UTC{sign}{offset_hrs:g})")

        self._row_count_lbl.config(text=f"Rows: {len(self.tree.get_children())}")
        self.after(1000, self._tick_clock)

    # ─────────────────────────────────────────────────────────
    # ROW MANAGEMENT
    # ─────────────────────────────────────────────────────────
    def _default_row(self):
        return ["", "0", "", "", "", "False", "Tropical", "TD", "False"]

    def add_row(self, values=None):
        if values is None:
            values = self._default_row()
        self.tree.insert("", "end", values=values)
        self._update_action_buttons()
        self._sync_map()

    def insert_row_above(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Insert Above", "Select a row first.")
            return
        self.tree.insert("", self.tree.index(sel[0]), values=self._default_row())
        self._update_action_buttons()
        self._sync_map()

    def insert_row_below(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Insert Below", "Select a row first.")
            return
        self.tree.insert("", self.tree.index(sel[-1]) + 1, values=self._default_row())
        self._update_action_buttons()
        self._sync_map()

    def duplicate_row(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Duplicate", "Select a row first.")
            return
        for item in sel:
            vals = self.tree.item(item, 'values')
            self.tree.insert("", self.tree.index(item) + 1, values=vals)
        self._update_action_buttons()
        self._sync_map()

    def move_row_up(self):
        for item in self.tree.selection():
            idx = self.tree.index(item)
            if idx > 0:
                self.tree.move(item, '', idx - 1)
        self._sync_map()

    def move_row_down(self):
        for item in reversed(self.tree.selection()):
            idx = self.tree.index(item)
            if idx < len(self.tree.get_children()) - 1:
                self.tree.move(item, '', idx + 1)
        self._sync_map()

    def remove_row(self):
        for item in self.tree.selection():
            self.tree.delete(item)
        self._update_action_buttons()
        self._sync_map()

    def clear_table(self):
        if not self.tree.get_children():
            return
        if messagebox.askyesno("Clear Table", "Are you sure you want to delete all rows?"):
            self.tree.delete(*self.tree.get_children())
            self.intensity_overrides.clear()
            self._update_action_buttons()
            self._sync_map()

    # ── Context menu ──
    def _show_row_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
        menu = tk.Menu(self, tearoff=0, bg=LIGHT_BG, fg=WHITE, font=("Segoe UI", 10),
                       activebackground=PRIMARY_COLOR, activeforeground=DARK_BG)
        menu.add_command(label="➕  Insert Above", command=self.insert_row_above)
        menu.add_command(label="➕  Insert Below", command=self.insert_row_below)
        menu.add_command(label="📋  Duplicate Row", command=self.duplicate_row)
        menu.add_separator()
        menu.add_command(label="🔼  Move Up", command=self.move_row_up)
        menu.add_command(label="🔽  Move Down", command=self.move_row_down)
        menu.add_separator()
        menu.add_command(label="➖  Delete Row", command=self.remove_row)
        menu.tk_popup(event.x_root, event.y_root)

    # ── Guard leaving ──
    def _on_back_guarded(self):
        if self.tree.get_children():
            if not messagebox.askyesno("Unsaved Data", "Going home will clear your current data. Continue?"):
                return
        self.on_back()

    def _on_delete_key(self, event):
        if self.focus_get() == self.tree:
            self.remove_row()

    # ─────────────────────────────────────────────────────────
    # CELL EDITING
    # ─────────────────────────────────────────────────────────
    def _on_double_click(self, event):
        if self.cell_editor:
            self.cell_editor.destroy()
            self.cell_editor = None

        item = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not item or not col:
            return
        col_idx = int(col.replace('#', '')) - 1
        col_name = self.COLUMNS[col_idx][0]
        old_value = self.tree.set(item, col_name)

        self.cell_editor = CellEditor(
            self.table_frame, self.tree, item, col, col_idx, col_name, old_value, self._on_cell_save
        )

    def _on_cell_save(self, item, col_idx, new_value):
        """Process saved cell value and cascade updates."""
        values = list(self.tree.item(item, 'values'))
        col_name = self.COLUMNS[col_idx][0]

        if col_name == "Intensity":
            values[col_idx] = new_value
            self.intensity_overrides.add(item)
            self.tree.item(item, values=values)
            self._sync_map()

        elif col_name == "Wind (kt)":
            values[col_idx] = new_value
            try:
                wind = int(float(new_value)) if new_value else 0
            except ValueError:
                wind = 0
            storm_type = values[6] if len(values) > 6 else "Tropical"
            if storm_type == "Tropical" and item not in self.intensity_overrides:
                values[7] = self._auto_intensity(wind)
            self.tree.item(item, values=values)
            self._sync_map()

        elif col_name == "Time (UTC)":
            values[col_idx] = new_value
            try:
                children = self.tree.get_children()
                if children:
                    t0 = pd.to_datetime(self.tree.item(children[0], 'values')[0])
                    t = pd.to_datetime(new_value)
                    values[1] = str(int((t - t0).total_seconds() // 3600))
            except Exception:
                pass
            self.tree.item(item, values=values)

        elif col_name == "Lead Time (h)":
            values[col_idx] = new_value
            try:
                children = self.tree.get_children()
                if children:
                    t0 = pd.to_datetime(self.tree.item(children[0], 'values')[0])
                    t = t0 + pd.Timedelta(hours=int(new_value))
                    values[0] = t.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
            self.tree.item(item, values=values)

        elif col_name in ("Lat", "Lon"):
            values[col_idx] = new_value
            # Auto-detect landfall if landmask available
            try:
                lat_val = float(values[2])
                lon_val = float(values[3])
                if _HAS_LANDMASK:
                    is_land = _globe.is_land(lat_val, lon_val)
                    children = list(self.tree.get_children())
                    cur_idx = children.index(item)
                    if cur_idx > 0:
                        prev = self.tree.item(children[cur_idx - 1], 'values')
                        try:
                            prev_land = _globe.is_land(float(prev[2]), float(prev[3]))
                            if is_land and not prev_land:
                                values[5] = "True"
                            elif not is_land:
                                values[5] = "False"
                        except (ValueError, IndexError):
                            pass
                    elif not is_land:
                        values[5] = "False"
            except (ValueError, IndexError):
                pass
            self.tree.item(item, values=values)
            self._sync_map()
        else:
            values[col_idx] = new_value
            self.tree.item(item, values=values)

        self._update_action_buttons()
        self.cell_editor = None

    # ─────────────────────────────────────────────────────────
    # MAP ↔ TABLE SYNC
    # ─────────────────────────────────────────────────────────
    def _sync_map(self):
        """Redraw map markers and track line from current table data."""
        if not _HAS_MAP or self.map_widget is None or self._syncing_map:
            return
        self._syncing_map = True
        try:
            # Clear old markers and path
            for m in self._map_markers:
                try:
                    m.delete()
                except Exception:
                    pass
            self._map_markers.clear()
            if self._map_path:
                try:
                    self._map_path.delete()
                except Exception:
                    pass
                self._map_path = None

            coords = []  # (lat, lon) list for track line
            for item in self.tree.get_children():
                vals = self.tree.item(item, 'values')
                try:
                    lat = float(vals[2])
                    lon = float(vals[3])
                except (ValueError, IndexError):
                    continue

                intensity = vals[7] if len(vals) > 7 else "TD"
                color = INTENSITY_COLORS.get(intensity, "#ffffff")
                landfall = vals[5] == "True" if len(vals) > 5 else False
                marker_text = f"{intensity}"
                if landfall:
                    marker_text += " ⛱"

                marker = self.map_widget.set_marker(
                    lat, lon, text=marker_text,
                    marker_color_circle=color,
                    marker_color_outside=color,
                )
                self._map_markers.append(marker)
                coords.append((lat, lon))

            # Draw track line
            if len(coords) >= 2:
                self._map_path = self.map_widget.set_path(
                    [c for c in coords], color="#ffffff", width=2
                )

            # Auto-fit map to track bounds
            if coords:
                lats = [c[0] for c in coords]
                lons = [c[1] for c in coords]
                if len(coords) == 1:
                    self.map_widget.set_position(lats[0], lons[0])
                    self.map_widget.set_zoom(8)
                else:
                    center_lat = (min(lats) + max(lats)) / 2
                    center_lon = (min(lons) + max(lons)) / 2
                    self.map_widget.set_position(center_lat, center_lon)
                    # Rough zoom estimate
                    span = max(max(lats) - min(lats), max(lons) - min(lons))
                    zoom = max(3, min(12, int(10 - span / 3)))
                    self.map_widget.set_zoom(zoom)
        finally:
            self._syncing_map = False

    def _on_map_right_click(self, coords):
        """Add a new row pre-filled with the clicked coordinates."""
        lat, lon = coords
        row = self._default_row()
        row[2] = f"{lat:.4f}"
        row[3] = f"{lon:.4f}"

        # Auto-detect landfall
        if _HAS_LANDMASK:
            is_land = _globe.is_land(lat, lon)
            # Check previous row
            children = self.tree.get_children()
            if children:
                prev = self.tree.item(children[-1], 'values')
                try:
                    prev_land = _globe.is_land(float(prev[2]), float(prev[3]))
                    if is_land and not prev_land:
                        row[5] = "True"
                except (ValueError, IndexError):
                    pass

        self.add_row(values=row)

    # ─────────────────────────────────────────────────────────
    # VALIDATION & HELPERS
    # ─────────────────────────────────────────────────────────
    def _set_status(self, text, color="#aaa"):
        self._status_lbl.config(text=text, fg=color)

    def _set_buttons_loading(self, loading, message=""):
        state = tk.DISABLED if loading else tk.NORMAL
        for btn in self._action_btns:
            btn.config(state=state)
        if loading:
            self._set_status(message, ACCENT)
        else:
            self._set_status("Ready")
            self._update_action_buttons()

    def _update_action_buttons(self, force_validation=True):
        if force_validation:
            valid = self._is_table_valid()
        else:
            # Quick check: just see if there's any row
            valid = len(self.tree.get_children()) > 0
        
        state = tk.NORMAL if valid else tk.DISABLED
        for btn in self._action_btns:
            btn.config(state=state)

    def _is_table_valid(self):
        is_valid = True
        for item in self.tree.get_children():
            vals = self.tree.item(item, 'values')
            ok = True
            try:
                pd.to_datetime(vals[0])
                lat, lon = float(vals[2]), float(vals[3])
                wind = int(vals[4])
                intensity = vals[7].strip() if len(vals) > 7 else ""
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 360) or wind < 0 or not intensity:
                    ok = False
            except Exception:
                ok = False
            self.tree.item(item, tags=('normal' if ok else 'invalid',))
            if not ok:
                is_valid = False
        return is_valid

    @staticmethod
    def _auto_intensity(wind):
        for threshold, label in DataEntryScreen.INTENSITY_THRESHOLDS:
            if wind >= threshold:
                return label
        return "TD"

    # ─────────────────────────────────────────────────────────
    # IMPORT / EXPORT
    # ─────────────────────────────────────────────────────────
    def import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if not path:
            return
        try:
            df = pd.read_csv(path, comment="#")
            self.tree.delete(*self.tree.get_children())
            self.intensity_overrides.clear()

            for _, row in df.iterrows():
                wind_val = row.get('wind_kt', '')
                try:
                    wind = int(float(wind_val)) if not pd.isna(wind_val) and str(wind_val).strip() else 0
                except (ValueError, TypeError):
                    wind = 0

                is_overridden = False
                if 'intensity_class' in df.columns and 'storm_type' in df.columns:
                    intensity = row.get('intensity_class')
                    if pd.isna(intensity) or not str(intensity).strip():
                        intensity = self._auto_intensity(wind)
                    else:
                        intensity = str(intensity).strip()
                        is_overridden = True
                    storm_type = row.get('storm_type')
                    storm_type = str(storm_type).strip() if not pd.isna(storm_type) and str(storm_type).strip() else 'Tropical'
                else:
                    cat_val = row.get('category')
                    if pd.isna(cat_val) or not str(cat_val).strip():
                        intensity = self._auto_intensity(wind)
                        storm_type = 'Tropical'
                    else:
                        category = str(cat_val).strip()
                        if category == 'L':
                            intensity, storm_type = 'TD', 'Low'
                        elif category == 'EX':
                            intensity, storm_type = self._auto_intensity(wind), 'Extratropical'
                        elif category in ('SD', 'SS'):
                            intensity = 'TS' if category == 'SS' else 'TD'
                            storm_type = 'Subtropical'
                        else:
                            intensity, storm_type = category, 'Tropical'
                            is_overridden = True

                item = self.tree.insert("", "end", values=[
                    str(row.get('time', '')), "0",
                    str(row.get('lat', '')), str(row.get('lon', '')),
                    str(wind_val) if not pd.isna(wind_val) else '',
                    str(row.get('landfall', False)), storm_type, intensity,
                    str(row.get('is_interpolated', False)),
                ])
                if is_overridden:
                    self.intensity_overrides.add(item)

            self._recalc_lead_times()
            self._update_action_buttons()
            self._sync_map()
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import CSV: {e}")

    def import_gpx(self):
        path = filedialog.askopenfilename(filetypes=[("GPX Files", "*.gpx")])
        if not path:
            return
        try:
            df = storm_tracker.read_gpx_to_dataframe(path)
            self.tree.delete(*self.tree.get_children())
            self.intensity_overrides.clear()

            for _, row in df.iterrows():
                try:
                    time_str = pd.to_datetime(row.get('time')).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    time_str = str(row.get('time', ''))

                wind_val = row.get('wind_kt', '')
                try:
                    wind = int(float(wind_val)) if not pd.isna(wind_val) and str(wind_val).strip() else 0
                except (ValueError, TypeError):
                    wind = 0

                storm_type = row.get('storm_type')
                storm_type = str(storm_type).strip() if not pd.isna(storm_type) and str(storm_type).strip() else 'Tropical'
                intensity = row.get('intensity_class')
                is_overridden = False
                if pd.isna(intensity) or not str(intensity).strip():
                    intensity = self._auto_intensity(wind) if storm_type == 'Tropical' else 'TD'
                else:
                    intensity = str(intensity).strip()
                    is_overridden = True

                item = self.tree.insert("", "end", values=[
                    time_str, "0",
                    str(row.get('lat', '')), str(row.get('lon', '')),
                    str(wind_val) if not pd.isna(wind_val) else '',
                    str(row.get('landfall', False)), storm_type, intensity,
                    str(row.get('is_interpolated', False)),
                ])
                if is_overridden:
                    self.intensity_overrides.add(item)

            self._recalc_lead_times()
            self._update_action_buttons()
            self._sync_map()

            has_interp = any(row.get('is_interpolated', False) for _, row in df.iterrows())
            if has_interp:
                messagebox.showwarning("GPX Import",
                    "This track contains interpolated points.\nTimestamps were missing and have been generated.")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import GPX: {e}")

    def import_kml(self):
        """Import a KML file and populate the table with coordinates."""
        path = filedialog.askopenfilename(filetypes=[("KML Files", "*.kml"), ("KMZ Files", "*.kmz")])
        if not path:
            return
        try:
            coords = self._parse_kml(path)
            if not coords:
                messagebox.showwarning("KML Import", "No coordinates found in the KML file.")
                return

            self.tree.delete(*self.tree.get_children())
            self.intensity_overrides.clear()
            base_time = pd.Timestamp.utcnow().floor('H')

            for i, (lon, lat, alt) in enumerate(coords):
                time_str = (base_time + pd.Timedelta(hours=i)).strftime("%Y-%m-%d %H:%M")
                # Auto-detect landfall
                landfall = "False"
                if _HAS_LANDMASK and i > 0:
                    prev_lon, prev_lat, _ = coords[i - 1]
                    try:
                        if _globe.is_land(lat, lon) and not _globe.is_land(prev_lat, prev_lon):
                            landfall = "True"
                    except Exception:
                        pass

                self.tree.insert("", "end", values=[
                    time_str, str(i), f"{lat:.4f}", f"{lon:.4f}",
                    "0", landfall, "Tropical", "TD", "True",
                ])

            self._recalc_lead_times()
            self._update_action_buttons()
            self._sync_map()
            messagebox.showinfo("KML Import", f"Imported {len(coords)} points from KML.\n"
                                "Timestamps are auto-generated (hourly). Edit as needed.")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import KML: {e}")

    @staticmethod
    def _parse_kml(path):
        """Extract coordinates from a KML file. Returns list of (lon, lat, alt)."""
        tree = ET.parse(path)
        root = tree.getroot()

        # Detect KML namespace
        ns = ''
        if '}' in root.tag:
            ns = root.tag.split('}')[0] + '}'

        coords_list = []
        # Find all <coordinates> elements
        for coord_elem in root.iter(f'{ns}coordinates'):
            text = coord_elem.text
            if not text:
                continue
            for token in text.strip().split():
                parts = token.strip().split(',')
                if len(parts) >= 2:
                    try:
                        lon, lat = float(parts[0]), float(parts[1])
                        alt = float(parts[2]) if len(parts) >= 3 else 0.0
                        coords_list.append((lon, lat, alt))
                    except ValueError:
                        continue
        return coords_list

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not path:
            return
        data = []
        for item in self.tree.get_children():
            v = self.tree.item(item, 'values')
            data.append({
                'time': v[0], 'lat': v[2], 'lon': v[3], 'wind_kt': v[4],
                'landfall': v[5],
                'storm_type': v[6] if len(v) > 6 else 'Tropical',
                'intensity_class': v[7] if len(v) > 7 else 'TD',
                'is_interpolated': v[8] if len(v) > 8 else 'False',
            })
        try:
            pd.DataFrame(data).to_csv(path, index=False)
            messagebox.showinfo("Exported", f"CSV exported to {path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export CSV: {e}")

    def _recalc_lead_times(self):
        children = self.tree.get_children()
        if not children:
            return
        try:
            t0 = pd.to_datetime(self.tree.item(children[0], 'values')[0])
            for item in children:
                t = pd.to_datetime(self.tree.item(item, 'values')[0])
                lead = int((t - t0).total_seconds() // 3600)
                vals = list(self.tree.item(item, 'values'))
                vals[1] = str(lead)
                self.tree.item(item, values=vals)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────
    # PLOT GENERATION (threaded)
    # ─────────────────────────────────────────────────────────
    def _get_forecast_points(self):
        """Build ForecastPoint objects from table data."""
        points, errors = [], []
        for i, item in enumerate(self.tree.get_children()):
            v = self.tree.item(item, 'values')
            try:
                points.append({
                    'time': pd.to_datetime(v[0], utc=True),
                    'lat': float(v[2]), 'lon': float(v[3]),
                    'wind_kt': int(v[4]),
                    'landfall': v[5] == "True",
                    'storm_type': v[6] if len(v) > 6 else "Tropical",
                    'intensity_class': v[7] if len(v) > 7 else "TD",
                    'is_interpolated': v[8] == "True" if len(v) > 8 else False,
                })
            except Exception as e:
                errors.append(f"Row {i + 1}: {e}")

        if errors:
            msg = "Invalid data found in rows:\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                msg += f"\n... and {len(errors) - 5} more."
            messagebox.showwarning("Input Error", msg)
        return points

    def _to_fp(self, pts):
        """Convert dict list to ForecastPoint list."""
        return [
            storm_tracker.ForecastPoint(
                time=p['time'], lat=p['lat'], lon=p['lon'], wind_kt=p['wind_kt'],
                intensity_class=p['intensity_class'], storm_type=p['storm_type'],
                landfall=p['landfall'], is_interpolated=p['is_interpolated'],
            ) for p in pts
        ]

    def _validate_data(self):
        from validation import validate_forecast_points
        return validate_forecast_points(self._to_fp(self._get_forecast_points()))

    def _show_validation_dialog(self, vr, is_warning=False):
        win = tk.Toplevel(self)
        win.title("Validation Warnings" if is_warning else "Validation Errors")
        win.configure(bg=DARK_BG)

        if vr.has_errors():
            tk.Label(win, text="❌ Validation Errors", font=("Segoe UI", 14, "bold"),
                     fg="#ff6060", bg=DARK_BG).pack(pady=10)
            tk.Label(win, text="\n".join(f"• {e}" for e in vr.hard_errors),
                     font=("Segoe UI", 10), fg=WHITE, bg=DARK_BG, justify=tk.LEFT, anchor='w').pack(padx=20, pady=10, fill=tk.BOTH, expand=True)

        if vr.has_warnings():
            if not vr.has_errors():
                tk.Label(win, text="⚠️ Validation Warnings", font=("Segoe UI", 14, "bold"),
                         fg=ACCENT, bg=DARK_BG).pack(pady=10)
            tk.Label(win, text="\n".join(f"• {w}" for w in vr.soft_warnings),
                     font=("Segoe UI", 10), fg=WHITE, bg=DARK_BG, justify=tk.LEFT, anchor='w').pack(padx=20, pady=10, fill=tk.BOTH, expand=True)

        bf = tk.Frame(win, bg=DARK_BG)
        bf.pack(pady=10)
        if vr.has_errors():
            tk.Button(bf, text="Close", command=win.destroy, bg=LIGHT_BG, fg=WHITE,
                      font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2", width=12).pack(side=tk.LEFT, padx=5)
        else:
            tk.Button(bf, text="Continue Anyway", command=win.destroy, bg=PRIMARY_COLOR, fg=DARK_BG,
                      font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2", width=15).pack(side=tk.LEFT, padx=5)

    # ── Track plot ──
    def preview_track(self):
        try:
            vr = self._validate_data()
            if vr.has_errors():
                self._show_validation_dialog(vr)
                return

            points = self._get_forecast_points()
            pts = self._to_fp(points)
            confidence = self.forecaster_confidence_var.get()
            name = self.storm_name_var.get().strip() or "CycloneAid"

            self._set_buttons_loading(True, "Generating track plot… ⏳")

            def _run():
                try:
                    rc = None
                    if get_preset is not None:
                        preset = get_preset(self.export_preset_var.get())
                        rc = preset.build_render_context({
                            "forecast_points": pts, "issue_time": pts[0].time,
                            "valid_until": pts[-1].time, "has_interpolated": any(p['is_interpolated'] for p in points),
                            "forecaster_confidence": confidence, "validation_result": vr,
                            "validation_warning_count": len(vr.soft_warnings),
                        })
                    fig = storm_tracker.plot_storm_track(pts, storm_name=name, issue_time=pts[0].time,
                                                         forecaster_confidence=confidence, render_context=rc)
                    self.last_fig = fig
                    self.after(0, lambda: self._finish_preview(fig, f"Track Preview — {name}", vr))
                except Exception as e:
                    self.after(0, lambda: messagebox.showerror("Preview Error", str(e)))
                    self.after(0, lambda: self._set_buttons_loading(False))

            threading.Thread(target=_run, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Preview Error", str(e))

    def save_track(self):
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png")])
        if not path:
            return
        try:
            vr = self._validate_data()
            if vr.has_errors():
                self._show_validation_dialog(vr)
                return
            points = self._get_forecast_points()
            pts = self._to_fp(points)
            name = self.storm_name_var.get().strip() or "CycloneAid"
            confidence = self.forecaster_confidence_var.get()
            rc = None
            if get_preset is not None:
                preset = get_preset(self.export_preset_var.get())
                rc = preset.build_render_context({
                    "forecast_points": pts, "issue_time": pts[0].time,
                    "valid_until": pts[-1].time, "has_interpolated": any(p['is_interpolated'] for p in points),
                    "forecaster_confidence": confidence, "validation_result": vr,
                    "validation_warning_count": len(vr.soft_warnings),
                })
            fig = storm_tracker.plot_storm_track(pts, storm_name=name, issue_time=pts[0].time,
                                                  forecaster_confidence=confidence, render_context=rc)
            fig.savefig(path, dpi=300, bbox_inches='tight', pad_inches=0.2)
            messagebox.showinfo("Saved", f"Track image saved to {path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    # ── Prognostic plot ──
    def preview_prognostic(self):
        try:
            vr = self._validate_data()
            if vr.has_errors():
                self._show_validation_dialog(vr)
                return
            pts = self._to_fp(self._get_forecast_points())
            name = self.storm_name_var.get().strip() or "CycloneAid"
            self._set_buttons_loading(True, "Generating prognostic plot… ⏳")

            def _run():
                try:
                    fig = storm_prognostic.plot_storm_prognostic(pts, storm_name=name, issue_time=pts[0].time)
                    self.last_prognostic_fig = fig
                    self.after(0, lambda: self._finish_preview(fig, f"Prognostic Preview — {name}", vr))
                except Exception as e:
                    self.after(0, lambda: messagebox.showerror("Preview Error", str(e)))
                    self.after(0, lambda: self._set_buttons_loading(False))

            threading.Thread(target=_run, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Preview Error", str(e))

    def save_prognostic(self):
        if not self.last_prognostic_fig:
            messagebox.showwarning("No Plot", "Please generate a preview first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png")])
        if not path:
            return
        try:
            self.last_prognostic_fig.savefig(path, dpi=300, bbox_inches='tight', pad_inches=0.2)
            messagebox.showinfo("Saved", f"Prognostic image saved to {path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    # ── RI plot ──
    def preview_ri(self):
        try:
            vr = self._validate_data()
            if vr.has_errors():
                self._show_validation_dialog(vr)
                return
            pts = self._to_fp(self._get_forecast_points())
            name = self.storm_name_var.get().strip() or "CycloneAid"
            self._set_buttons_loading(True, "Generating RI plot… ⏳")

            def _run():
                try:
                    fig = storm_ri_plot.plot_ri_from_forecast_points(pts, window_hours=24, storm_name=name)
                    self.last_ri_fig = fig
                    self.after(0, lambda: self._finish_preview(fig, f"RI (dV/dt) Preview — {name}", vr))
                except Exception as e:
                    self.after(0, lambda: messagebox.showerror("RI Preview Error", str(e)))
                    self.after(0, lambda: self._set_buttons_loading(False))

            threading.Thread(target=_run, daemon=True).start()
        except Exception as e:
            messagebox.showerror("RI Preview Error", str(e))

    def save_ri(self):
        if not self.last_ri_fig:
            messagebox.showwarning("No Plot", "Please generate an RI preview first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png")])
        if not path:
            return
        try:
            self.last_ri_fig.savefig(path, dpi=300, bbox_inches='tight', pad_inches=0.2,
                                      facecolor=self.last_ri_fig.get_facecolor())
            messagebox.showinfo("Saved", f"RI plot saved to {path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    # ── Common preview finish ──
    def _finish_preview(self, fig, title, vr):
        self._set_buttons_loading(False)
        self._set_status(f"{title.split(' — ')[0]} ready ✓", PRIMARY_COLOR)
        if vr.has_warnings():
            self._show_validation_dialog(vr, is_warning=True)
        self._show_preview(fig, title=title)

    def _show_preview(self, fig, title="Preview"):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("900x700")
        win.configure(bg=DARK_BG)

        pf = tk.Frame(win, bg=DARK_BG)
        pf.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        canvas = FigureCanvasTkAgg(fig, master=pf)
        canvas.draw()

        tf = tk.Frame(win, bg=DARK_BG)
        tf.pack(fill=tk.X, side=tk.BOTTOM, pady=5)
        NavigationToolbar2Tk(canvas, tf).update()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        tk.Button(tf, text="Close Preview", command=win.destroy, bg=LIGHT_BG, fg=WHITE,
                  font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT, padx=10, pady=2)


# ═════════════════════════════════════════════════════════════════════════════
# APPLICATION ROOT
# ═════════════════════════════════════════════════════════════════════════════

class StormTrackerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} — {VERSION}")
        self.geometry("1300x750")
        self.minsize(1000, 650)
        self.configure(bg=DARK_BG)
        self.current_frame = None
        self.after(100, self._maximize)
        self.show_home()

    def _maximize(self):
        try:
            self.state('zoomed')
        except Exception:
            self.attributes('-zoomed', True)

    def show_home(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = HomeScreen(self, self.show_data_entry)
        self.current_frame.pack(fill=tk.BOTH, expand=True)

    def show_data_entry(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = DataEntryScreen(self, self.show_home)
        self.current_frame.pack(fill=tk.BOTH, expand=True)


if __name__ == "__main__":
    app = StormTrackerApp()
    app.mainloop()