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

APP_NAME = "CycloneAid"
VERSION = "Alpha 0.8.1"
CREATOR = "Forecaster Zayed"

# Import plot_storm_track and plot_storm_prognostic from the respective scripts
importlib_base_dir = os.path.dirname(os.path.abspath(__file__))
spec_tracker = importlib.util.spec_from_file_location("storm_tracker", os.path.join(importlib_base_dir, "storm_tracker.py"))
storm_tracker = importlib.util.module_from_spec(spec_tracker)
sys.modules["storm_tracker"] = storm_tracker
spec_tracker.loader.exec_module(storm_tracker)

spec_prognostic = importlib.util.spec_from_file_location("storm_prognostic", os.path.join(importlib_base_dir, "storm_prognostic.py"))
storm_prognostic = importlib.util.module_from_spec(spec_prognostic)
sys.modules["storm_prognostic"] = storm_prognostic
spec_prognostic.loader.exec_module(storm_prognostic)

spec_ri = importlib.util.spec_from_file_location("storm_RI_plot", os.path.join(importlib_base_dir, "storm_RI_plot.py"))
storm_ri_plot = importlib.util.module_from_spec(spec_ri)
sys.modules["storm_RI_plot"] = storm_ri_plot
spec_ri.loader.exec_module(storm_ri_plot)

try:
    from export_preset import get_preset
except ImportError:
    get_preset = None

PRIMARY_COLOR = "#00adb5"
DARK_BG = "#222831"
LIGHT_BG = "#393e46"
WHITE = "#eeeeee"
ACCENT = "#FFD700"

class HomeScreen(tk.Frame):
    """Redesigned home screen with feature showcase and polished layout."""

    FEATURES = [
        {
            "icon": "🗺️",
            "title": "Storm Track Plot",
            "desc": "Generate high-fidelity forecast track maps with\n"
                    "uncertainty cones, city overlays, and intensity\n"
                    "classification on Cartopy dark-mode charts.",
            "color": "#00adb5",
        },
        {
            "icon": "📊",
            "title": "Prognostic Chart",
            "desc": "Visualize intensity timelines with auto-detected\n"
                    "category changes, landfall events, and nearby\n"
                    "city proximity analysis.",
            "color": "#FF6B6B",
        },
        {
            "icon": "⚡",
            "title": "Rapid Intensification",
            "desc": "Analyze dV/dt intensity change rates with WMO RI\n"
                    "threshold highlighting and peak-event annotation\n"
                    "on dark-mode time-series plots.",
            "color": "#FFD700",
        },
        {
            "icon": "📋",
            "title": "Data Management",
            "desc": "Excel-like row management: insert, duplicate,\n"
                    "reorder, and edit cells with dropdowns. Import\n"
                    "from CSV / GPX and export with one click.",
            "color": "#48CFAD",
        },
        {
            "icon": "🎨",
            "title": "Export Presets",
            "desc": "Switch between Forecaster and Media presets to\n"
                    "control layer visibility, label density, and\n"
                    "metadata footers per audience.",
            "color": "#AC92EC",
        },
        {
            "icon": "✅",
            "title": "Data Validation",
            "desc": "Automatic QC checks on coordinates, wind speed,\n"
                    "time ordering, and intensity consistency with\n"
                    "hard-error / soft-warning classification.",
            "color": "#4FC1E9",
        },
    ]

    def __init__(self, master, on_start):
        super().__init__(master)
        self.master = master
        self.on_start = on_start
        self.configure(bg=DARK_BG)
        self.create_widgets()

    def create_widgets(self):
        # ─── Bottom bar (pack first so it stays at bottom) ───
        bottom_bar = tk.Frame(self, bg="#1a1e25", bd=1, relief=tk.SUNKEN)
        bottom_bar.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Label(
            bottom_bar,
            text="⚠️  ALPHA — For testing and development only. Not for operational use.  ⚠️",
            font=("Segoe UI", 10, "bold"), fg=DARK_BG, bg=ACCENT, padx=10, pady=5,
        ).pack(fill=tk.X)
        tk.Label(
            bottom_bar,
            text=f"Created by {CREATOR}  •  {VERSION}  •  Report bugs and feedback",
            font=("Segoe UI", 9), fg="#888", bg="#1a1e25", pady=4,
        ).pack(fill=tk.X)

        # ─── Scrollable content area ───
        scroll_container = tk.Frame(self, bg=DARK_BG)
        scroll_container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(scroll_container, bg=DARK_BG, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(scroll_container, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Inner frame that holds all content
        content = tk.Frame(canvas, bg=DARK_BG)
        content_window = canvas.create_window((0, 0), window=content, anchor=tk.N)

        # Resize inner frame width to match canvas
        def _on_canvas_configure(event):
            canvas.itemconfig(content_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Update scroll region when content changes size
        def _on_content_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        content.bind("<Configure>", _on_content_configure)

        # Mousewheel scrolling (Windows)
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ─── Hero Section ───
        hero = tk.Frame(content, bg=DARK_BG)
        hero.pack(fill=tk.X, pady=(30, 10))

        # Icon row
        icon_label = tk.Label(hero, text="🌀", font=("Segoe UI Emoji", 56), bg=DARK_BG, fg=PRIMARY_COLOR)
        icon_label.pack()

        # App name
        try:
            name_font = ("Century Gothic", 42, "bold")
            name_lbl = tk.Label(hero, text=APP_NAME.upper(), font=name_font, fg=PRIMARY_COLOR, bg=DARK_BG)
            name_lbl.pack(pady=(0, 2))
        except Exception:
            tk.Label(hero, text=APP_NAME.upper(), font=("Segoe UI", 42, "bold"), fg=PRIMARY_COLOR, bg=DARK_BG).pack(pady=(0, 2))

        # Tagline
        tk.Label(
            hero,
            text="Tropical Cyclone Forecast Track & Intensity Analysis Suite",
            font=("Segoe UI", 13), fg="#aaa", bg=DARK_BG,
        ).pack(pady=(0, 4))

        # Version badge
        ver_frame = tk.Frame(hero, bg=DARK_BG)
        ver_frame.pack(pady=(2, 12))
        tk.Label(ver_frame, text=f" {VERSION} ", font=("Consolas", 11, "bold"),
                 fg=DARK_BG, bg=ACCENT, padx=8, pady=2).pack(side=tk.LEFT, padx=4)

        # ─── Start Button ───
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

        # ─── Separator ───
        sep_frame = tk.Frame(hero, bg=DARK_BG)
        sep_frame.pack(fill=tk.X, padx=80, pady=(0, 8))
        tk.Frame(sep_frame, bg=LIGHT_BG, height=1).pack(fill=tk.X)

        # ─── Origin Story ───
        story_frame = tk.Frame(content, bg=LIGHT_BG, padx=20, pady=14,
                               highlightthickness=1, highlightbackground="#444")
        story_frame.pack(fill=tk.X, padx=60, pady=(4, 14))

        tk.Label(
            story_frame, text="💡  Why CycloneAid?",
            font=("Segoe UI", 13, "bold"), fg=ACCENT, bg=LIGHT_BG, anchor=tk.W,
        ).pack(anchor=tk.W, pady=(0, 6))

        story_text = (
            "Forecaster Zayed built CycloneAid because he was absolutely tired of manually "
            "drawing storm track charts on Canva every single time a cyclone spun up. 😤🎨\n\n"
            "What started as \"there HAS to be a better way\" turned into a full forecast analysis "
            "suite — auto-generated track maps, prognostic timelines, RI analysis, and proper "
            "dark-mode cartography. No more dragging arrows around in a graphic design tool. "
            "Now the data does the drawing."
        )
        tk.Label(
            story_frame, text=story_text,
            font=("Segoe UI", 10), fg="#ccc", bg=LIGHT_BG,
            justify=tk.LEFT, anchor=tk.W, wraplength=700,
        ).pack(anchor=tk.W)

        # ─── Feature Cards Section ───
        section_label = tk.Label(
            content, text="✦  Features  ✦",
            font=("Segoe UI", 14, "bold"), fg=ACCENT, bg=DARK_BG,
        )
        section_label.pack(pady=(4, 10))

        cards_frame = tk.Frame(content, bg=DARK_BG)
        cards_frame.pack(fill=tk.X, padx=40, pady=(0, 30))

        # 3 columns x 2 rows of feature cards
        for i, feat in enumerate(self.FEATURES):
            row, col = divmod(i, 3)
            self._create_feature_card(cards_frame, feat, row, col)

        # Make columns expand equally
        for c in range(3):
            cards_frame.columnconfigure(c, weight=1)

    def _create_feature_card(self, parent, feat, row, col):
        """Create a single feature card widget."""
        card = tk.Frame(
            parent, bg=LIGHT_BG, bd=0, relief=tk.FLAT,
            padx=14, pady=12, highlightthickness=1,
            highlightbackground="#444", highlightcolor=feat["color"],
        )
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

        # Icon
        tk.Label(
            card, text=feat["icon"], font=("Segoe UI Emoji", 28),
            bg=LIGHT_BG, fg=feat["color"],
        ).pack(anchor=tk.W)

        # Title
        tk.Label(
            card, text=feat["title"],
            font=("Segoe UI", 12, "bold"), fg=feat["color"], bg=LIGHT_BG,
            anchor=tk.W,
        ).pack(anchor=tk.W, pady=(2, 4))

        # Description
        tk.Label(
            card, text=feat["desc"],
            font=("Segoe UI", 9), fg="#ccc", bg=LIGHT_BG,
            justify=tk.LEFT, anchor=tk.W,
        ).pack(anchor=tk.W)

        # Hover glow effect
        def on_enter(e, c=card, color=feat["color"]):
            c.config(highlightbackground=color, highlightthickness=2)

        def on_leave(e, c=card):
            c.config(highlightbackground="#444", highlightthickness=1)

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)
        # Also bind children so hover works anywhere on the card
        for child in card.winfo_children():
            child.bind("<Enter>", on_enter)
            child.bind("<Leave>", on_leave)

class StormTrackerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} - {VERSION}")
        self.geometry("1100x700")
        self.minsize(900, 600)
        self.configure(bg=DARK_BG)
        self.current_frame = None
        self.after(100, self.maximize_window)
        self.show_home()

    def maximize_window(self):
        try:
            self.state('zoomed')  # Windows
        except Exception:
            self.attributes('-zoomed', True)  # Linux/Mac

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

class CellEditor:
    """Custom cell editor for Treeview cells with dropdowns and checkboxes"""
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
        
        # Get cell position relative to treeview
        bbox = tree.bbox(item, column)
        if not bbox:
            return
        
        x, y, width, height = bbox
        
        # Get treeview position relative to parent
        tree_x = tree.winfo_x()
        tree_y = tree.winfo_y()
        
        # Create frame for editor (position relative to parent of treeview)
        self.frame = tk.Frame(parent, bg=DARK_BG, relief=tk.SOLID, borderwidth=2)
        
        # Position relative to parent widget
        abs_x = tree_x + x
        abs_y = tree_y + y
        
        self.frame.place(x=abs_x, y=abs_y, width=width, height=max(height, 30))
        self.frame.lift()  # Bring to front
        self.frame.focus_set()
        
        if col_name == "Intensity":
            self.create_intensity_dropdown()
        elif col_name == "Storm Type":
            self.create_storm_type_dropdown()
        elif col_name == "Landfall":
            self.create_landfall_checkbox()
        elif col_name == "Interpolated":
            self.create_interpolated_checkbox()
        else:
            self.create_text_entry()
    
    def create_intensity_dropdown(self):
        """Create dropdown for intensity class selection"""
        intensities = ['TD', 'TS', 'STS', 'C1', 'C2', 'C3', 'C4', 'C5']
        var = tk.StringVar(value=self.old_value if self.old_value in intensities else 'TD')
        
        self.editor = ttk.Combobox(self.frame, textvariable=var, values=intensities, 
                                   state="readonly", width=10)
        self.editor.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.editor.focus()
        self.editor.bind('<Return>', lambda e: self.save_intensity(var.get()))
        self.editor.bind('<Escape>', lambda e: self.cancel())
        self.editor.bind('<FocusOut>', lambda e: self.save_intensity(var.get()))
        self.editor.event_generate('<Button-1>')
    
    def create_storm_type_dropdown(self):
        """Create dropdown for storm type selection"""
        storm_types = ["Tropical", "Subtropical", "Extratropical", "Low"]
        var = tk.StringVar(value=self.old_value if self.old_value in storm_types else 'Tropical')
        
        self.editor = ttk.Combobox(self.frame, textvariable=var, values=storm_types, 
                                   state="readonly", width=12)
        self.editor.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.editor.focus()
        self.editor.bind('<Return>', lambda e: self.save_storm_type(var.get()))
        self.editor.bind('<Escape>', lambda e: self.cancel())
        self.editor.bind('<FocusOut>', lambda e: self.save_storm_type(var.get()))
        self.editor.event_generate('<Button-1>')
    
    def create_interpolated_checkbox(self):
        """Create checkbox for interpolated flag"""
        current_value = self.old_value if self.old_value else "False"
        is_checked = current_value == "True" or current_value == "true" or current_value == "1"
        
        self.var_interpolated = BooleanVar(value=is_checked)
        
        cb = tk.Checkbutton(
            self.frame, text="Interpolated", variable=self.var_interpolated,
            bg=DARK_BG, fg=WHITE, selectcolor=LIGHT_BG,
            font=("Segoe UI", 10, "bold"),
            command=self.save_interpolated
        )
        cb.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        cb.focus()
        
        self.frame.update_idletasks()
        req_width = max(120, self.frame.winfo_reqwidth())
        req_height = max(35, self.frame.winfo_reqheight())
        self.frame.place(width=req_width, height=req_height)
        self.frame.lift()
    
    def save_interpolated(self):
        """Save interpolated value"""
        value = "True" if self.var_interpolated.get() else "False"
        self.on_save_callback(self.item, self.col_idx, value)
        self.frame.after(150, self.destroy)
    
    def create_override_checkboxes(self):
        """Create checkboxes for override options"""
        # Parse current override value
        current_override = self.old_value if self.old_value else "NONE"
        
        # Create variables for checkboxes
        self.var_subtropical = BooleanVar(value=current_override == "SS")
        self.var_l = BooleanVar(value=current_override == "L")
        self.var_ex = BooleanVar(value=current_override == "EX")
        self.var_none = BooleanVar(value=current_override == "NONE")
        
        # Helper function to make checkboxes mutually exclusive
        def on_checkbox_change(var_to_set, *other_vars):
            """Uncheck other checkboxes when one is checked"""
            if var_to_set.get():
                for other_var in other_vars:
                    other_var.set(False)
        
        # Create checkboxes with mutual exclusivity
        cb_subtropical = tk.Checkbutton(
            self.frame, text="Subtropical (SS)", variable=self.var_subtropical,
            bg=DARK_BG, fg=WHITE, selectcolor=LIGHT_BG,
            font=("Segoe UI", 9),
            command=lambda: on_checkbox_change(self.var_subtropical, self.var_l, self.var_ex, self.var_none)
        )
        cb_subtropical.pack(anchor=tk.W, padx=5, pady=2)
        
        cb_l = tk.Checkbutton(
            self.frame, text="Low (L)", variable=self.var_l,
            bg=DARK_BG, fg=WHITE, selectcolor=LIGHT_BG,
            font=("Segoe UI", 9),
            command=lambda: on_checkbox_change(self.var_l, self.var_subtropical, self.var_ex, self.var_none)
        )
        cb_l.pack(anchor=tk.W, padx=5, pady=2)
        
        cb_ex = tk.Checkbutton(
            self.frame, text="Post-tropical (EX)", variable=self.var_ex,
            bg=DARK_BG, fg=WHITE, selectcolor=LIGHT_BG,
            font=("Segoe UI", 9),
            command=lambda: on_checkbox_change(self.var_ex, self.var_subtropical, self.var_l, self.var_none)
        )
        cb_ex.pack(anchor=tk.W, padx=5, pady=2)
        
        cb_none = tk.Checkbutton(
            self.frame, text="None (Auto)", variable=self.var_none,
            bg=DARK_BG, fg=WHITE, selectcolor=LIGHT_BG,
            font=("Segoe UI", 9),
            command=lambda: on_checkbox_change(self.var_none, self.var_subtropical, self.var_l, self.var_ex)
        )
        cb_none.pack(anchor=tk.W, padx=5, pady=2)
        
        # Buttons
        btn_frame = tk.Frame(self.frame, bg=DARK_BG)
        btn_frame.pack(fill=tk.X, pady=2)
        tk.Button(btn_frame, text="OK", command=self.save_override,
                 bg=PRIMARY_COLOR, fg=DARK_BG, font=("Segoe UI", 9, "bold"),
                 relief=tk.FLAT, cursor="hand2", width=6).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Cancel", command=self.cancel,
                 bg=LIGHT_BG, fg=WHITE, font=("Segoe UI", 9),
                 relief=tk.FLAT, cursor="hand2", width=6).pack(side=tk.LEFT, padx=2)
        
        # Expand frame to fit checkboxes
        self.frame.update_idletasks()
        req_width = max(200, self.frame.winfo_reqwidth())
        req_height = max(140, self.frame.winfo_reqheight())
        self.frame.place(width=req_width, height=req_height)
        self.frame.lift()  # Ensure it's on top
    
    def create_landfall_checkbox(self):
        """Create checkbox for landfall (True/False)"""
        # Parse current landfall value
        current_value = self.old_value if self.old_value else "False"
        is_checked = current_value == "True" or current_value == "true" or current_value == "1"
        
        # Create variable for checkbox
        self.var_landfall = BooleanVar(value=is_checked)
        
        # Create checkbox that auto-saves on change
        cb = tk.Checkbutton(
            self.frame, text="Landfall", variable=self.var_landfall,
            bg=DARK_BG, fg=WHITE, selectcolor=LIGHT_BG,
            font=("Segoe UI", 10, "bold"),
            command=self.save_landfall
        )
        cb.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        cb.focus()
        
        # Adjust frame size for checkbox
        self.frame.update_idletasks()
        req_width = max(120, self.frame.winfo_reqwidth())
        req_height = max(35, self.frame.winfo_reqheight())
        self.frame.place(width=req_width, height=req_height)
        self.frame.lift()
    
    def save_landfall(self):
        """Save landfall value based on checkbox state"""
        value = "True" if self.var_landfall.get() else "False"
        self.on_save_callback(self.item, self.col_idx, value)
        # Close editor after a brief moment to show visual feedback
        self.frame.after(150, self.destroy)
    
    def create_text_entry(self):
        """Create text entry for other columns"""
        var = tk.StringVar(value=self.old_value)
        self.editor = tk.Entry(self.frame, textvariable=var, font=("Segoe UI", 10))
        self.editor.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.editor.focus()
        self.editor.select_range(0, tk.END)
        self.editor.bind('<Return>', lambda e: self.save_text(var.get()))
        self.editor.bind('<Escape>', lambda e: self.cancel())
        self.editor.bind('<FocusOut>', lambda e: self.save_text(var.get()))
    
    def save_intensity(self, value):
        """Save intensity class value"""
        if value:
            self.on_save_callback(self.item, self.col_idx, value)
        self.destroy()
    
    def save_storm_type(self, value):
        """Save storm type value"""
        if value:
            self.on_save_callback(self.item, self.col_idx, value)
        self.destroy()
    
    def save_text(self, value):
        """Save text value"""
        if value is not None:
            self.on_save_callback(self.item, self.col_idx, value)
        self.destroy()
    
    def cancel(self):
        """Cancel editing"""
        self.destroy()
    
    def destroy(self):
        """Destroy the editor"""
        if self.frame:
            self.frame.destroy()

class DataEntryScreen(tk.Frame):
    INTENSITY_THRESHOLDS = [
        (137, 'C5'), (113, 'C4'), (96, 'C3'), (83, 'C2'), (64, 'C1'), (48, 'STS'), (34, 'TS'), (0, 'TD')
    ]
    COLUMNS = [
        ("Time (UTC)", 18), ("Lead Time (h)", 10), ("Lat", 8), ("Lon", 8), ("Wind (kt)", 10),
        ("Landfall", 8), ("Storm Type", 12), ("Intensity", 10), ("Interpolated", 10)
    ]
    STORM_TYPE_OPTIONS = ["Tropical", "Subtropical", "Extratropical", "Low"]
    INTENSITY_OPTIONS = ['TD', 'TS', 'STS', 'C1', 'C2', 'C3', 'C4', 'C5']
    
    def __init__(self, master, on_back):
        super().__init__(master)
        self.master = master
        self.on_back = on_back
        self.configure(bg=DARK_BG)
        self.forecaster_confidence_var = tk.StringVar(value="Moderate")
        self.storm_name_var = tk.StringVar(value="CycloneAid")
        self.cell_editor = None
        self.create_widgets()

    def create_widgets(self):
        # Top bar with icon and heading
        topbar = tk.Frame(self, bg=DARK_BG)
        tk.Button(topbar, text="← Home", command=self.on_back_guarded, bg=LIGHT_BG, fg=WHITE, font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=8, pady=8)
        tk.Label(topbar, text="🌀 Storm Data Entry", font=("Segoe UI", 18, "bold"), fg=PRIMARY_COLOR, bg=DARK_BG).pack(side=tk.LEFT, padx=12)
        # Storm Name entry
        tk.Label(topbar, text="Storm Name:", font=("Segoe UI", 11, "bold"), fg=WHITE, bg=DARK_BG).pack(side=tk.LEFT, padx=(30,2))
        storm_name_entry = tk.Entry(topbar, textvariable=self.storm_name_var, font=("Segoe UI", 11), width=16, justify="center")
        storm_name_entry.pack(side=tk.LEFT, padx=2)
        tk.Label(topbar, text="Forecaster Confidence:", font=("Segoe UI", 11), fg=WHITE, bg=DARK_BG).pack(side=tk.LEFT, padx=(30,2))
        conf_menu = ttk.Combobox(topbar, textvariable=self.forecaster_confidence_var, values=["High", "Moderate", "Low"], state="readonly", width=10)
        conf_menu.pack(side=tk.LEFT, padx=2)
        tk.Label(topbar, text="(heuristic cone scaling)", font=("Segoe UI", 8, "italic"), fg=WHITE, bg=DARK_BG).pack(side=tk.LEFT, padx=(2, 0))
        tk.Label(topbar, text="Export Preset:", font=("Segoe UI", 11), fg=WHITE, bg=DARK_BG).pack(side=tk.LEFT, padx=(24, 2))
        self.export_preset_var = tk.StringVar(value="Forecaster")
        preset_combo = ttk.Combobox(topbar, textvariable=self.export_preset_var, values=["Forecaster", "Media"], state="readonly", width=10)
        preset_combo.pack(side=tk.LEFT, padx=2)
        topbar.pack(fill=tk.X, pady=(0, 10))

        # Table
        self.table_frame = tk.Frame(self, bg=DARK_BG)
        self.table_frame.pack(pady=10, fill=tk.BOTH, expand=True)
        columns = [c[0] for c in self.COLUMNS]
        self.tree = ttk.Treeview(self.table_frame, columns=columns, show="headings", height=8)
        for i, (col, w) in enumerate(self.COLUMNS):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w*10, anchor="center")
        vsb = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.table_frame.grid_rowconfigure(0, weight=1)
        self.table_frame.grid_columnconfigure(0, weight=1)
        self.tree.bind('<Double-1>', self.on_double_click)
        # Right-click context menu for rows
        self.tree.bind('<Button-3>', self.show_row_context_menu)
        
        self.tree.tag_configure('invalid', background='#4a1a1a', foreground='#ff8080')
        self.tree.tag_configure('warning', background='#3a3a00', foreground=ACCENT)
        self.tree.tag_configure('normal', background=DARK_BG, foreground=WHITE)
        
        # Keyboard shortcuts
        self.bind_all("<Delete>", self._on_delete_key)
        self.bind_all("<Control-s>", lambda e: self.export_csv())

        # ─── Row Management Toolbar ───
        btn_frame = tk.Frame(self, bg=DARK_BG)

        # Separator label
        tk.Label(btn_frame, text="Rows:", font=("Segoe UI", 10, "bold"), fg=ACCENT, bg=DARK_BG).pack(side=tk.LEFT, padx=(4, 8))

        self._make_toolbar_btn(btn_frame, "➕ Add", self.add_row, PRIMARY_COLOR, DARK_BG)
        self._make_toolbar_btn(btn_frame, "⬆ Insert Above", self.insert_row_above, LIGHT_BG, WHITE)
        self._make_toolbar_btn(btn_frame, "⬇ Insert Below", self.insert_row_below, LIGHT_BG, WHITE)
        self._make_toolbar_btn(btn_frame, "📋 Duplicate", self.duplicate_row, LIGHT_BG, WHITE)
        self._make_toolbar_btn(btn_frame, "➖ Remove", self.remove_row, "#c0392b", WHITE)
        self._make_toolbar_btn(btn_frame, "🔼 Move Up", self.move_row_up, LIGHT_BG, WHITE)
        self._make_toolbar_btn(btn_frame, "🔽 Move Down", self.move_row_down, LIGHT_BG, WHITE)

        # Spacer
        tk.Frame(btn_frame, bg=DARK_BG, width=20).pack(side=tk.LEFT)

        # Separator label
        tk.Label(btn_frame, text="Table:", font=("Segoe UI", 10, "bold"), fg=ACCENT, bg=DARK_BG).pack(side=tk.LEFT, padx=(4, 8))
        self._make_toolbar_btn(btn_frame, "🗑️ Clear All", self.clear_table, "#c0392b", WHITE)

        # Spacer
        tk.Frame(btn_frame, bg=DARK_BG, width=20).pack(side=tk.LEFT)

        # Separator label
        tk.Label(btn_frame, text="I/O:", font=("Segoe UI", 10, "bold"), fg=ACCENT, bg=DARK_BG).pack(side=tk.LEFT, padx=(4, 8))
        self._make_toolbar_btn(btn_frame, "📂 Import CSV", self.import_csv, LIGHT_BG, WHITE)
        self._make_toolbar_btn(btn_frame, "📡 Import GPX", self.import_gpx, LIGHT_BG, WHITE)
        self._make_toolbar_btn(btn_frame, "💾 Export CSV", self.export_csv, LIGHT_BG, WHITE)
        btn_frame.pack(pady=5, fill=tk.X, padx=8)

        # ─── Save/Preview buttons (track, prognostic, RI) ───
        action_frame = tk.Frame(self, bg=DARK_BG)

        # Track group
        track_group = tk.LabelFrame(action_frame, text="Track Plot", font=("Segoe UI", 9, "bold"), fg=ACCENT, bg=DARK_BG, bd=1, relief=tk.GROOVE, padx=6, pady=4)
        self.btn_preview_track = tk.Button(track_group, text="👁️ Preview", command=self.preview_track, bg=PRIMARY_COLOR, fg=DARK_BG, font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2")
        self.btn_save_track = tk.Button(track_group, text="🖼️ Save", command=self.save_track, bg=LIGHT_BG, fg=WHITE, font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2")
        self.btn_preview_track.pack(side=tk.LEFT, padx=3, pady=2)
        self.btn_save_track.pack(side=tk.LEFT, padx=3, pady=2)
        track_group.pack(side=tk.LEFT, padx=6, pady=4)

        # Prognostic group
        prog_group = tk.LabelFrame(action_frame, text="Prognostic Plot", font=("Segoe UI", 9, "bold"), fg=ACCENT, bg=DARK_BG, bd=1, relief=tk.GROOVE, padx=6, pady=4)
        self.btn_preview_prognostic = tk.Button(prog_group, text="👁️ Preview", command=self.preview_prognostic, bg=PRIMARY_COLOR, fg=DARK_BG, font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2")
        self.btn_save_prognostic = tk.Button(prog_group, text="🖼️ Save", command=self.save_prognostic, bg=LIGHT_BG, fg=WHITE, font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2")
        self.btn_preview_prognostic.pack(side=tk.LEFT, padx=3, pady=2)
        self.btn_save_prognostic.pack(side=tk.LEFT, padx=3, pady=2)
        prog_group.pack(side=tk.LEFT, padx=6, pady=4)

        # RI Plot group
        ri_group = tk.LabelFrame(action_frame, text="RI (dV/dt) Plot", font=("Segoe UI", 9, "bold"), fg=ACCENT, bg=DARK_BG, bd=1, relief=tk.GROOVE, padx=6, pady=4)
        self.btn_preview_ri = tk.Button(ri_group, text="👁️ Preview", command=self.preview_ri, bg=PRIMARY_COLOR, fg=DARK_BG, font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2")
        self.btn_save_ri = tk.Button(ri_group, text="🖼️ Save", command=self.save_ri, bg=LIGHT_BG, fg=WHITE, font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2")
        self.btn_preview_ri.pack(side=tk.LEFT, padx=3, pady=2)
        self.btn_save_ri.pack(side=tk.LEFT, padx=3, pady=2)
        ri_group.pack(side=tk.LEFT, padx=6, pady=4)

        action_frame.pack(pady=8)
        self.update_action_buttons()

        # ─── Bottom Status Bar with Live Clock ───
        self._create_clock_bar()

        # Add initial row
        self.add_row()
        self.last_fig = None
        self.last_prognostic_fig = None
        self.last_ri_fig = None

    # ─── Helper: make a styled toolbar button with hover ───
    def _make_toolbar_btn(self, parent, text, cmd, bg, fg):
        btn = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                        font=("Segoe UI", 9, "bold"), relief=tk.FLAT, cursor="hand2",
                        padx=6, pady=2, bd=0)
        default_bg = bg
        btn.bind("<Enter>", lambda e, b=btn: b.config(bg=ACCENT, fg=DARK_BG))
        btn.bind("<Leave>", lambda e, b=btn, dbg=default_bg, dfg=fg: b.config(bg=dbg, fg=dfg))
        btn.pack(side=tk.LEFT, padx=2, pady=2)
        return btn

    # ─── Live UTC / Local Clock Bar ───
    def _create_clock_bar(self):
        """Create a status bar at the bottom with live Zulu and local clocks."""
        clock_bar = tk.Frame(self, bg="#1a1e25", bd=1, relief=tk.SUNKEN)
        clock_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(4, 0))

        # Clock icon + Zulu time (left side)
        clock_left = tk.Frame(clock_bar, bg="#1a1e25")
        clock_left.pack(side=tk.LEFT, padx=12, pady=6)

        tk.Label(clock_left, text="🕐", font=("Segoe UI Emoji", 16), bg="#1a1e25", fg=PRIMARY_COLOR).pack(side=tk.LEFT, padx=(0, 6))

        zulu_frame = tk.Frame(clock_left, bg="#1a1e25")
        zulu_frame.pack(side=tk.LEFT)

        self.zulu_time_label = tk.Label(zulu_frame, text="", font=("Consolas", 14, "bold"), fg=PRIMARY_COLOR, bg="#1a1e25")
        self.zulu_time_label.pack(anchor=tk.W)
        self.zulu_date_label = tk.Label(zulu_frame, text="", font=("Consolas", 9), fg="#888", bg="#1a1e25")
        self.zulu_date_label.pack(anchor=tk.W)

        # Separator  
        tk.Frame(clock_left, bg=LIGHT_BG, width=2).pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=2)

        # Local time (right of Zulu)
        local_frame = tk.Frame(clock_left, bg="#1a1e25")
        local_frame.pack(side=tk.LEFT)

        self.local_time_label = tk.Label(local_frame, text="", font=("Consolas", 12), fg=ACCENT, bg="#1a1e25")
        self.local_time_label.pack(anchor=tk.W)
        self.local_tz_label = tk.Label(local_frame, text="", font=("Consolas", 9), fg="#888", bg="#1a1e25")
        self.local_tz_label.pack(anchor=tk.W)

        # Right side: row count + status
        status_right = tk.Frame(clock_bar, bg="#1a1e25")
        status_right.pack(side=tk.RIGHT, padx=12, pady=6)
        self.row_count_label = tk.Label(status_right, text="Rows: 0", font=("Segoe UI", 10, "bold"), fg=WHITE, bg="#1a1e25")
        self.row_count_label.pack(side=tk.RIGHT, padx=(10, 0))
        self.status_label = tk.Label(status_right, text="Ready", font=("Segoe UI", 10), fg="#aaaaaa", bg="#1a1e25")
        self.status_label.pack(side=tk.RIGHT)

        # Start the clock tick
        self._tick_clock()

    def _tick_clock(self):
        """Update the clock labels every second."""
        if not self.winfo_exists():
            return
        now_utc = datetime.now(timezone.utc)
        self.zulu_time_label.config(text=now_utc.strftime("%H:%M:%SZ"))
        self.zulu_date_label.config(text=now_utc.strftime("%Y-%m-%d  UTC+0 (Zulu)"))

        now_local = datetime.now()
        # Get local timezone abbreviation
        local_tz_name = _time.strftime("%Z")
        utc_offset_sec = _time.timezone if _time.daylight == 0 else _time.altzone
        utc_offset_hrs = -utc_offset_sec / 3600
        sign = "+" if utc_offset_hrs >= 0 else ""
        self.local_time_label.config(text=now_local.strftime("%H:%M:%S"))
        self.local_tz_label.config(text=f"{now_local.strftime('%Y-%m-%d')}  {local_tz_name} (UTC{sign}{utc_offset_hrs:g})")

        # Update row count
        num_rows = len(self.tree.get_children())
        self.row_count_label.config(text=f"Rows: {num_rows}")

        self.after(1000, self._tick_clock)

    def on_back_guarded(self):
        if len(self.tree.get_children()) > 0:
            if not messagebox.askyesno("Unsaved Data", "Going home will clear your current data. Continue?"):
                return
        self.on_back()

    def _on_delete_key(self, event):
        # Only delete row if treeview has focus
        if self.focus_get() == self.tree:
            self.remove_row()

    def _set_buttons_loading(self, loading, message=""):
        state = tk.DISABLED if loading else tk.NORMAL
        for btn in [self.btn_preview_track, self.btn_save_track,
                    self.btn_preview_prognostic, self.btn_save_prognostic,
                    self.btn_preview_ri, self.btn_save_ri]:
            btn.config(state=state)
        
        if loading:
            self.status_label.config(text=message, fg=ACCENT)
        else:
            self.status_label.config(text="Ready", fg="#aaaaaa")
            if not loading:
                self.update_action_buttons()

    def add_row(self, values=None):
        # Default: time, lead, lat, lon, wind, landfall, storm_type, intensity, interpolated
        if values is None:
            values = ["", "0", "", "", "", "False", "Tropical", "TD", "False"]
        self.tree.insert("", "end", values=values)
        self.update_action_buttons()

    def insert_row_above(self):
        """Insert a blank row above the selected row."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Insert Above", "Select a row first.")
            return
        idx = self.tree.index(selected[0])
        values = ["", "0", "", "", "", "False", "Tropical", "TD", "False"]
        self.tree.insert("", idx, values=values)
        self.update_action_buttons()

    def insert_row_below(self):
        """Insert a blank row below the selected row."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Insert Below", "Select a row first.")
            return
        idx = self.tree.index(selected[-1]) + 1
        values = ["", "0", "", "", "", "False", "Tropical", "TD", "False"]
        self.tree.insert("", idx, values=values)
        self.update_action_buttons()

    def duplicate_row(self):
        """Duplicate the selected row(s) below themselves."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Duplicate", "Select a row first.")
            return
        for item in selected:
            values = self.tree.item(item, 'values')
            idx = self.tree.index(item) + 1
            self.tree.insert("", idx, values=values)
        self.update_action_buttons()

    def move_row_up(self):
        """Move the selected row up by one position."""
        selected = self.tree.selection()
        if not selected:
            return
        for item in selected:
            idx = self.tree.index(item)
            if idx > 0:
                self.tree.move(item, '', idx - 1)

    def move_row_down(self):
        """Move the selected row down by one position."""
        selected = self.tree.selection()
        if not selected:
            return
        for item in reversed(selected):
            idx = self.tree.index(item)
            if idx < len(self.tree.get_children()) - 1:
                self.tree.move(item, '', idx + 1)

    def clear_table(self):
        """Clear all rows after confirmation."""
        if not self.tree.get_children():
            return
        if messagebox.askyesno("Clear Table", "Are you sure you want to delete all rows?"):
            self.tree.delete(*self.tree.get_children())
            self.update_action_buttons()

    def show_row_context_menu(self, event):
        """Show a right-click context menu for row operations."""
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

    def remove_row(self):
        selected = self.tree.selection()
        for item in selected:
            self.tree.delete(item)
        self.update_action_buttons()

    def on_double_click(self, event):
        # Destroy any existing editor
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
        
        parent_widget = self.table_frame if hasattr(self, "table_frame") else self
        
        # Create appropriate editor based on column type
        self.cell_editor = CellEditor(
            parent_widget, self.tree, item, col, col_idx, col_name, old_value,
            self.on_cell_save
        )
    
    def on_cell_save(self, item, col_idx, new_value):
        """Handle saving cell value after editing"""
        values = list(self.tree.item(item, 'values'))
        col_name = self.COLUMNS[col_idx][0]
        
        if col_name == "Intensity":
            values[col_idx] = new_value
            if not hasattr(self, 'intensity_overrides'):
                self.intensity_overrides = set()
            self.intensity_overrides.add(item)
            self.tree.item(item, values=values)
        elif col_name == "Storm Type":
            values[col_idx] = new_value
            self.tree.item(item, values=values)
        elif col_name == "Wind (kt)":
            values[col_idx] = new_value
            try:
                wind = int(float(new_value)) if new_value else 0
            except ValueError:
                wind = 0
                
            storm_type = values[6] if len(values) > 6 else "Tropical"
            overrides = getattr(self, 'intensity_overrides', set())
            
            if storm_type == "Tropical" and item not in overrides:
                # Auto-derive intensity from wind
                intensity = self.auto_intensity(wind)
                try:
                    if len(values) > 7:
                        values[7] = intensity
                except Exception:
                    pass
            self.tree.item(item, values=values)
        elif col_name == "Time (UTC)":
            # Time edited — recalculate lead time from first row
            values[col_idx] = new_value
            try:
                children = self.tree.get_children()
                if children:
                    t0 = pd.to_datetime(self.tree.item(children[0], 'values')[0])
                    t = pd.to_datetime(new_value)
                    lead = int((t - t0).total_seconds() // 3600)
                    values[1] = str(lead)
            except Exception:
                pass
            self.tree.item(item, values=values)
        elif col_name == "Lead Time (h)":
            # Lead time edited — recalculate time from first row
            values[col_idx] = new_value
            try:
                children = self.tree.get_children()
                if children:
                    t0 = pd.to_datetime(self.tree.item(children[0], 'values')[0])
                    lead = int(new_value)
                    t = t0 + pd.Timedelta(hours=lead)
                    values[0] = t.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
            self.tree.item(item, values=values)
        else:
            # Generic columns (Lat, Lon, Landfall, Interpolated, etc.)
            values[col_idx] = new_value
            self.tree.item(item, values=values)
        
        self.update_action_buttons()
        self.cell_editor = None

    def update_action_buttons(self):
        valid = self.is_table_valid()
        state = tk.NORMAL if valid else tk.DISABLED
        for btn in [self.btn_preview_track, self.btn_save_track,
                    self.btn_preview_prognostic, self.btn_save_prognostic,
                    self.btn_preview_ri, self.btn_save_ri]:
            btn.config(state=state)

    def is_table_valid(self):
        # Check all required fields in all rows
        is_valid = True
        for item in self.tree.get_children():
            values = self.tree.item(item, 'values')
            row_ok = True
            try:
                time_str = values[0]
                pd.to_datetime(time_str)
                lead = int(values[1])
                lat_str = values[2]
                lon_str = values[3]
                lat, lon = float(lat_str), float(lon_str)
                wind = int(values[4])
                intensity = values[7].strip() if len(values) > 7 else ""
                
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 360) or wind < 0 or not intensity:
                    row_ok = False
            except Exception:
                row_ok = False
                
            if row_ok:
                self.tree.item(item, tags=('normal',))
            else:
                self.tree.item(item, tags=('invalid',))
                is_valid = False
                
        return is_valid

    def auto_intensity(self, wind):
        """Derive intensity class from wind speed."""
        for threshold, label in self.INTENSITY_THRESHOLDS:
            if wind >= threshold:
                return label
        return "TD"

    def import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if not path:
            return
        try:
            df = pd.read_csv(path, comment="#")
            self.tree.delete(*self.tree.get_children())
            if not hasattr(self, 'intensity_overrides'):
                self.intensity_overrides = set()
            else:
                self.intensity_overrides.clear()
                
            for _, row in df.iterrows():
                wind_val = row.get('wind_kt', '')
                try:
                    wind = int(float(wind_val)) if not pd.isna(wind_val) and str(wind_val).strip() else 0
                except (ValueError, TypeError):
                    wind = 0
                    
                is_overridden = False
                
                # Handle new format (intensity_class, storm_type) or legacy (category)
                if 'intensity_class' in df.columns and 'storm_type' in df.columns:
                    intensity = row.get('intensity_class')
                    if pd.isna(intensity) or not str(intensity).strip():
                        intensity = self.auto_intensity(wind)
                    else:
                        intensity = str(intensity).strip()
                        is_overridden = True
                        
                    storm_type = row.get('storm_type')
                    if pd.isna(storm_type) or not str(storm_type).strip():
                        storm_type = 'Tropical'
                    else:
                        storm_type = str(storm_type).strip()
                else:
                    # Legacy format - parse category
                    cat_val = row.get('category')
                    if pd.isna(cat_val) or not str(cat_val).strip():
                        intensity = self.auto_intensity(wind)
                        storm_type = 'Tropical'
                    else:
                        category = str(cat_val).strip()
                        if category == 'L':
                            intensity = 'TD'
                            storm_type = 'Low'
                        elif category == 'EX':
                            intensity = self.auto_intensity(wind)
                            storm_type = 'Extratropical'
                        elif category in ['SD', 'SS']:
                            intensity = 'TS' if category == 'SS' else 'TD'
                            storm_type = 'Subtropical'
                        else:
                            intensity = category
                            storm_type = 'Tropical'
                            is_overridden = True
                            
                is_interpolated = row.get('is_interpolated', False)
                item = self.tree.insert("", "end", values=[
                    str(row.get('time', '')),
                    "0",
                    str(row.get('lat', '')),
                    str(row.get('lon', '')),
                    str(wind_val) if not pd.isna(wind_val) else '',
                    str(row.get('landfall', False)),
                    storm_type,
                    intensity,
                    str(is_interpolated)
                ])
                if is_overridden:
                    self.intensity_overrides.add(item)
                    
            # Recalculate lead times
            children = self.tree.get_children()
            if children:
                t0 = pd.to_datetime(self.tree.item(children[0], 'values')[0])
                for i, item in enumerate(children):
                    t = pd.to_datetime(self.tree.item(item, 'values')[0])
                    lead = int((t - t0).total_seconds() // 3600)
                    values = list(self.tree.item(item, 'values'))
                    values[1] = str(lead)
                    self.tree.item(item, values=values)
            self.update_action_buttons()
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import CSV: {e}")

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not path:
            return
        data = []
        for item in self.tree.get_children():
            values = self.tree.item(item, 'values')
            row = {
                'time': values[0],
                'lat': values[2],
                'lon': values[3],
                'wind_kt': values[4],
                'landfall': values[5],
                'storm_type': values[6] if len(values) > 6 else 'Tropical',
                'intensity_class': values[7] if len(values) > 7 else 'TD',
                'is_interpolated': values[8] if len(values) > 8 else 'False'
            }
            data.append(row)
        df = pd.DataFrame(data)
        try:
            df.to_csv(path, index=False)
            messagebox.showinfo("Exported", f"CSV exported to {path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export CSV: {e}")

    def import_gpx(self):
        """Import a GPX track and populate the table with its lat/lon (and times if present)."""
        path = filedialog.askopenfilename(filetypes=[("GPX Files", "*.gpx")])
        if not path:
            return
        try:
            # Use the same converter already used by the CLI
            df = storm_tracker.read_gpx_to_dataframe(path)
            self.tree.delete(*self.tree.get_children())
            if not hasattr(self, 'intensity_overrides'):
                self.intensity_overrides = set()
            else:
                self.intensity_overrides.clear()

            for _, row in df.iterrows():
                # Format time for display
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
                if pd.isna(storm_type) or not str(storm_type).strip():
                    storm_type = 'Tropical'
                else:
                    storm_type = str(storm_type).strip()

                is_overridden = False
                intensity = row.get('intensity_class')
                if pd.isna(intensity) or not str(intensity).strip():
                    intensity = self.auto_intensity(wind) if storm_type == 'Tropical' else 'TD'
                else:
                    intensity = str(intensity).strip()
                    is_overridden = True

                item = self.tree.insert("", "end", values=[
                    time_str,
                    "0",  # Lead time will be recalculated below
                    str(row.get('lat', '')),
                    str(row.get('lon', '')),
                    str(wind_val) if not pd.isna(wind_val) else '',
                    str(row.get('landfall', False)),
                    storm_type,
                    intensity,
                    str(row.get('is_interpolated', False))
                ])
                if is_overridden:
                    self.intensity_overrides.add(item)

            # Recalculate lead times just like in CSV import
            children = self.tree.get_children()
            if children:
                t0 = pd.to_datetime(self.tree.item(children[0], 'values')[0])
                for item in children:
                    t = pd.to_datetime(self.tree.item(item, 'values')[0])
                    lead = int((t - t0).total_seconds() // 3600)
                    values = list(self.tree.item(item, 'values'))
                    values[1] = str(lead)
                    self.tree.item(item, values=values)

            self.update_action_buttons()
            
            # Show warning if interpolated points detected
            has_interpolated = any(row.get('is_interpolated', False) for _, row in df.iterrows())
            if has_interpolated:
                messagebox.showwarning("GPX Import", 
                    "This track contains interpolated points derived from GPX data.\n"
                    "Timestamps were missing and have been generated.")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import GPX: {e}")

    def preview_track(self):
        try:
            # Validate before preview
            validation_result = self.validate_data()
            if validation_result.has_errors():
                self.show_validation_dialog(validation_result)
                return
            
            points = self.get_forecast_points()
            forecaster_confidence = self.forecaster_confidence_var.get()
            storm_name = self.storm_name_var.get().strip() or "CycloneAid"
            pts = [
                storm_tracker.ForecastPoint(
                    time=p['time'],
                    lat=p['lat'],
                    lon=p['lon'],
                    wind_kt=p['wind_kt'],
                    intensity_class=p['intensity_class'],
                    storm_type=p['storm_type'],
                    landfall=p['landfall'],
                    is_interpolated=p['is_interpolated']
                ) for p in points
            ]
            
            self._set_buttons_loading(True, "Generating track plot… ⏳")
            
            def _run():
                try:
                    render_context = None
                    if get_preset is not None:
                        preset = get_preset(self.export_preset_var.get())
                        storm_data = {
                            "forecast_points": pts,
                            "issue_time": pts[0].time,
                            "valid_until": pts[-1].time if pts else None,
                            "has_interpolated": any(p.get("is_interpolated") for p in points),
                            "forecaster_confidence": forecaster_confidence,
                            "validation_result": validation_result,
                            "validation_warning_count": len(validation_result.soft_warnings),
                        }
                        render_context = preset.build_render_context(storm_data)
                    fig = storm_tracker.plot_storm_track(pts, storm_name=storm_name,
                                                         issue_time=pts[0].time,
                                                         forecaster_confidence=forecaster_confidence,
                                                         render_context=render_context)
                    self.last_fig = fig
                    self.last_pts = pts
                    self.last_storm_name = storm_name
                    self.last_forecaster_confidence = forecaster_confidence
                    self.last_render_context = render_context
                    
                    self.after(0, lambda: self._on_preview_track_ready(fig, storm_name, validation_result))
                except Exception as e:
                    self.after(0, lambda e=e: messagebox.showerror("Preview Error", str(e)))
                    self.after(0, lambda: self._set_buttons_loading(False))
            
            threading.Thread(target=_run, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Preview Error", str(e))

    def _on_preview_track_ready(self, fig, storm_name, validation_result):
        self._set_buttons_loading(False)
        self.status_label.config(text="Track plot ready ✓")
        # Show warnings if any
        if validation_result.has_warnings():
            self.show_validation_dialog(validation_result, is_warning=True)
        self.show_preview(fig, title=f"Track Preview - {storm_name}")

    def save_track(self):
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png")])
        if not path:
            return
        try:
            # Use last preview data if available; else build from table (so preset still applies)
            pts = getattr(self, "last_pts", None)
            if pts is None:
                validation_result = self.validate_data()
                if validation_result.has_errors():
                    self.show_validation_dialog(validation_result)
                    return
                points = self.get_forecast_points()
                pts = [
                    storm_tracker.ForecastPoint(
                        time=p['time'], lat=p['lat'], lon=p['lon'], wind_kt=p['wind_kt'],
                        intensity_class=p['intensity_class'], storm_type=p['storm_type'],
                        landfall=p['landfall'], is_interpolated=p['is_interpolated']
                    ) for p in points
                ]
                validation_result = self.validate_data()
            storm_name = getattr(self, "last_storm_name", None) or self.storm_name_var.get().strip() or "CycloneAid"
            forecaster_confidence = getattr(self, "last_forecaster_confidence", None) or self.forecaster_confidence_var.get()
            if not pts:
                messagebox.showwarning("No Plot", "No valid forecast points.")
                return
            validation_result = self.validate_data()
            render_context = None
            if get_preset is not None:
                preset = get_preset(self.export_preset_var.get())
                storm_data = {
                    "forecast_points": pts,
                    "issue_time": pts[0].time,
                    "valid_until": pts[-1].time if pts else None,
                    "has_interpolated": any(getattr(p, "is_interpolated", False) for p in pts),
                    "forecaster_confidence": forecaster_confidence,
                    "validation_result": validation_result,
                    "validation_warning_count": len(validation_result.soft_warnings),
                }
                render_context = preset.build_render_context(storm_data)
            fig = storm_tracker.plot_storm_track(pts, storm_name=storm_name, issue_time=pts[0].time,
                                                 forecaster_confidence=forecaster_confidence, render_context=render_context)
            fig.savefig(path, dpi=300, bbox_inches='tight', pad_inches=0.2)
            messagebox.showinfo("Saved", f"Track image saved to {path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def preview_prognostic(self):
        try:
            # Validate before preview
            validation_result = self.validate_data()
            if validation_result.has_errors():
                self.show_validation_dialog(validation_result)
                return
            
            points = self.get_forecast_points()
            storm_name = self.storm_name_var.get().strip() or "CycloneAid"
            pts = [
                storm_tracker.ForecastPoint(
                    time=p['time'],
                    lat=p['lat'],
                    lon=p['lon'],
                    wind_kt=p['wind_kt'],
                    intensity_class=p['intensity_class'],
                    storm_type=p['storm_type'],
                    landfall=p['landfall'],
                    is_interpolated=p['is_interpolated']
                ) for p in points
            ]
            
            self._set_buttons_loading(True, "Generating prognostic plot… ⏳")
            
            def _run():
                try:
                    fig = storm_prognostic.plot_storm_prognostic(pts, storm_name=storm_name, issue_time=pts[0].time)
                    self.last_prognostic_fig = fig
                    self.after(0, lambda: self._on_preview_prog_ready(fig, storm_name, validation_result))
                except Exception as e:
                    self.after(0, lambda e=e: messagebox.showerror("Preview Error", str(e)))
                    self.after(0, lambda: self._set_buttons_loading(False))
                    
            threading.Thread(target=_run, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Preview Error", str(e))

    def _on_preview_prog_ready(self, fig, storm_name, validation_result):
        self._set_buttons_loading(False)
        self.status_label.config(text="Prognostic plot ready ✓")
        if validation_result.has_warnings():
            self.show_validation_dialog(validation_result, is_warning=True)
        self.show_preview(fig, title=f"Prognostic Preview - {storm_name}")

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

    # ─── RI (Rapid Intensification) Plot ───
    def preview_ri(self):
        """Preview the RI (dV/dt) plot using the current table data."""
        try:
            validation_result = self.validate_data()
            if validation_result.has_errors():
                self.show_validation_dialog(validation_result)
                return

            points = self.get_forecast_points()
            storm_name = self.storm_name_var.get().strip() or "CycloneAid"
            pts = [
                storm_tracker.ForecastPoint(
                    time=p['time'],
                    lat=p['lat'],
                    lon=p['lon'],
                    wind_kt=p['wind_kt'],
                    intensity_class=p['intensity_class'],
                    storm_type=p['storm_type'],
                    landfall=p['landfall'],
                    is_interpolated=p['is_interpolated']
                ) for p in points
            ]

            self._set_buttons_loading(True, "Generating RI plot… ⏳")
            
            def _run():
                try:
                    fig = storm_ri_plot.plot_ri_from_forecast_points(
                        pts, window_hours=24, storm_name=storm_name
                    )
                    self.last_ri_fig = fig
                    self.after(0, lambda: self._on_preview_ri_ready(fig, storm_name, validation_result))
                except Exception as e:
                    self.after(0, lambda e=e: messagebox.showerror("RI Preview Error", str(e)))
                    self.after(0, lambda: self._set_buttons_loading(False))

            threading.Thread(target=_run, daemon=True).start()
        except Exception as e:
            messagebox.showerror("RI Preview Error", str(e))

    def _on_preview_ri_ready(self, fig, storm_name, validation_result):
        self._set_buttons_loading(False)
        self.status_label.config(text="RI plot ready ✓")
        if validation_result.has_warnings():
            self.show_validation_dialog(validation_result, is_warning=True)
        self.show_preview(fig, title=f"RI (dV/dt) Preview — {storm_name}")

    def save_ri(self):
        """Save the RI plot to a PNG file."""
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

    def show_preview(self, fig, title="Preview"):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("900x700")
        win.configure(bg=DARK_BG)
        
        # Add frame for plotting area
        plot_frame = tk.Frame(win, bg=DARK_BG)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = FigureCanvasTkAgg(fig, master=plot_frame)
        canvas.draw()
        
        # Add toolbar
        toolbar_frame = tk.Frame(win, bg=DARK_BG)
        toolbar_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=5)
        
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.update()
        
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        tk.Button(toolbar_frame, text="Close Preview", command=win.destroy,
                  bg=LIGHT_BG, fg=WHITE, font=("Segoe UI", 10, "bold"),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT, padx=10, pady=2)

    def get_forecast_points(self):
        points = []
        errors = []
        for i, item in enumerate(self.tree.get_children()):
            values = self.tree.item(item, 'values')
            try:
                time = pd.to_datetime(values[0], utc=True)
                lat = float(values[2])
                lon = float(values[3])
                wind = int(values[4])
                landfall = values[5] == "True"
                storm_type = values[6] if len(values) > 6 else "Tropical"
                intensity_class = values[7] if len(values) > 7 else "TD"
                is_interpolated = values[8] == "True" if len(values) > 8 else False
                points.append({
                    'time': time,
                    'lat': lat,
                    'lon': lon,
                    'wind_kt': wind,
                    'landfall': landfall,
                    'storm_type': storm_type,
                    'intensity_class': intensity_class,
                    'is_interpolated': is_interpolated
                })
            except Exception as e:
                errors.append(f"Row {i+1}: {e}")
                
        if errors:
            msg = "Invalid data found in rows:\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                msg += f"\n... and {len(errors) - 5} more."
            messagebox.showwarning("Input Error", msg)
            
        return points
    
    def validate_data(self):
        """Validate forecast data using validation module."""
        from validation import validate_forecast_points
        points = self.get_forecast_points()
        forecast_points = [
            storm_tracker.ForecastPoint(
                time=p['time'],
                lat=p['lat'],
                lon=p['lon'],
                wind_kt=p['wind_kt'],
                intensity_class=p['intensity_class'],
                storm_type=p['storm_type'],
                landfall=p['landfall'],
                is_interpolated=p['is_interpolated']
            ) for p in points
        ]
        return validate_forecast_points(forecast_points)
    
    def show_validation_dialog(self, validation_result, is_warning=False):
        """Show validation results in a dialog."""
        win = tk.Toplevel(self)
        win.title("Validation Warnings" if is_warning else "Validation Errors")
        win.configure(bg=DARK_BG)
        
        if validation_result.has_errors():
            title = tk.Label(win, text="❌ Validation Errors", 
                           font=("Segoe UI", 14, "bold"), fg="#ff6060", bg=DARK_BG)
            title.pack(pady=10)
            
            error_text = "\n".join([f"• {err}" for err in validation_result.hard_errors])
            error_label = tk.Label(win, text=error_text, 
                                 font=("Segoe UI", 10), fg=WHITE, bg=DARK_BG,
                                 justify=tk.LEFT, anchor='w')
            error_label.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
        
        if validation_result.has_warnings():
            if not validation_result.has_errors():
                title = tk.Label(win, text="⚠️ Validation Warnings", 
                               font=("Segoe UI", 14, "bold"), fg=ACCENT, bg=DARK_BG)
                title.pack(pady=10)
            
            warning_text = "\n".join([f"• {warn}" for warn in validation_result.soft_warnings])
            warning_label = tk.Label(win, text=warning_text, 
                                   font=("Segoe UI", 10), fg=WHITE, bg=DARK_BG,
                                   justify=tk.LEFT, anchor='w')
            warning_label.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
        
        btn_frame = tk.Frame(win, bg=DARK_BG)
        btn_frame.pack(pady=10)
        
        if validation_result.has_errors():
            tk.Button(btn_frame, text="Close", command=win.destroy,
                     bg=LIGHT_BG, fg=WHITE, font=("Segoe UI", 10, "bold"),
                     relief=tk.FLAT, cursor="hand2", width=12).pack(side=tk.LEFT, padx=5)
        else:
            tk.Button(btn_frame, text="Continue Anyway", command=win.destroy,
                     bg=PRIMARY_COLOR, fg=DARK_BG, font=("Segoe UI", 10, "bold"),
                     relief=tk.FLAT, cursor="hand2", width=15).pack(side=tk.LEFT, padx=5)

if __name__ == "__main__":
    app = StormTrackerApp()
    app.mainloop() 