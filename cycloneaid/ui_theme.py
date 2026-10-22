"""Semantic desktop themes and an accessible, persistent appearance switch.

Appearance belongs to the local application, never to a forecast project. Tk
widgets opt into roles; ttk widgets use the shared styles configured here.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from weakref import WeakKeyDictionary


@dataclass(frozen=True)
class ThemePalette:
    name: str
    primary: str
    background: str
    panel: str
    text: str
    muted: str
    accent: str
    surface: str
    border: str
    status: str
    invalid_background: str
    invalid_text: str
    warning_background: str
    on_primary: str
    hover: str

    # Compatibility for existing chart/dialog adapters during the workspace move.
    PRIMARY_COLOR = property(lambda self: self.primary)
    DARK_BG = property(lambda self: self.background)
    LIGHT_BG = property(lambda self: self.panel)
    WHITE = property(lambda self: self.text)
    TEXT_MUTED = property(lambda self: self.muted)
    ACCENT = property(lambda self: self.accent)
    SURFACE = property(lambda self: self.surface)
    BORDER = property(lambda self: self.border)
    BOTTOM_BAR_BG = property(lambda self: self.status)
    INVALID_BG = property(lambda self: self.invalid_background)
    INVALID_FG = property(lambda self: self.invalid_text)
    WARNING_BG = property(lambda self: self.warning_background)


THEMES = {
    "Typhoon Dark": ThemePalette("Typhoon Dark", "#22c6d0", "#0f172a", "#1e293b", "#f1f5f9",
                                 "#a5b4c8", "#fbbf24", "#27364b", "#475569", "#111d31",
                                 "#4a1a28", "#fda4af", "#4b3b17", "#082f36", "#34475f"),
    "Sky Light": ThemePalette("Sky Light", "#036b9d", "#eff6fa", "#e1edf4", "#10283c",
                              "#50677b", "#a35a00", "#ffffff", "#b8ccd9", "#dfedf5",
                              "#fee2e2", "#a91b35", "#fef3c7", "#ffffff", "#d0e5f0"),
}
DEFAULT_THEME = "Typhoon Dark"
_ROLES = WeakKeyDictionary()


def get_palette(name=DEFAULT_THEME):
    """Return a known palette, falling back safely for obsolete preferences."""
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def preference_path():
    base = os.environ.get("LOCALAPPDATA") if os.name == "nt" else os.environ.get("XDG_STATE_HOME")
    return Path(base or Path.home()/".local"/"state")/"cycloneaid"/"appearance.json"


def load_theme_preference(path=None):
    try:
        data = json.loads(Path(path or preference_path()).read_text(encoding="utf-8"))
        name = data.get("theme") if isinstance(data, dict) else None
        return name if name in THEMES else DEFAULT_THEME
    except (OSError, ValueError, TypeError):
        return DEFAULT_THEME


def current_theme_name(widget):
    return getattr(widget._root(), "_cycloneaid_theme_name", DEFAULT_THEME)


def _save_preference(name, path):
    # Atomic persistence avoids a half-written preference after a forced exit.
    from cycloneaid.session import atomic_json
    try:
        atomic_json(path or preference_path(), {"theme": name})
    except OSError:
        # A read-only home directory must not prevent changing appearance.
        pass


def _styles(root, palette):
    p = palette
    style = ttk.Style(root)
    if "clam" in style.theme_names() and style.theme_use() != "clam":
        style.theme_use("clam")
    style.configure(".", background=p.background, foreground=p.text, bordercolor=p.border,
                    troughcolor=p.background, focuscolor=p.primary, font=("Segoe UI", 10))
    for name in ("TFrame", "Workspace.TFrame"):
        style.configure(name, background=p.background)
    style.configure("Card.TFrame", background=p.panel)
    for name in ("TLabel", "Workspace.TLabel", "Property.TLabel"):
        style.configure(name, background=p.background, foreground=p.text)
    style.configure("Card.TLabel", background=p.panel, foreground=p.text)
    style.configure("Muted.TLabel", background=p.background, foreground=p.muted)
    style.configure("Error.TLabel", background=p.background, foreground=p.invalid_text)
    style.map("Error.TLabel", background=[("disabled", p.background), ("active", p.background)],
              foreground=[("disabled", p.muted), ("active", p.invalid_text)])
    style.configure("Status.TLabel", background=p.status, foreground=p.muted)
    style.configure("Title.TLabel", background=p.background, foreground=p.text,
                    font=("Segoe UI", 14, "bold"))
    style.configure("TButton", background=p.panel, foreground=p.text, bordercolor=p.border,
                    lightcolor=p.border, darkcolor=p.border, relief="flat", borderwidth=1,
                    focusthickness=2, focuscolor=p.primary, padding=(10, 6), anchor="center", width=0)
    style.map("TButton", background=[("disabled", p.background), ("pressed", p.border),
                                    ("active", p.hover)],
              foreground=[("disabled", p.muted), ("pressed", p.text), ("active", p.text)],
              bordercolor=[("focus", p.primary), ("active", p.primary)])
    for name in ("TMenubutton", "Workspace.TMenubutton"):
        style.configure(name, background=p.panel, foreground=p.text, bordercolor=p.border,
                        lightcolor=p.border, darkcolor=p.border, relief="flat", borderwidth=1,
                        focusthickness=2, focuscolor=p.primary, arrowcolor=p.text, padding=(10, 6), width=0)
        style.map(name, background=[("disabled", p.background), ("pressed", p.border),
                                    ("active", p.hover)],
                  foreground=[("disabled", p.muted), ("pressed", p.text), ("active", p.text)],
                  arrowcolor=[("disabled", p.muted), ("active", p.text)],
                  bordercolor=[("focus", p.primary), ("active", p.primary)])
    style.configure("Accent.TButton", background=p.primary, foreground=p.on_primary)
    style.map("Accent.TButton", background=[("disabled", p.panel), ("pressed", p.primary),
                                           ("active", p.primary)],
              foreground=[("disabled", p.muted), ("pressed", p.on_primary),
                          ("active", p.on_primary)])
    for name in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(name, fieldbackground=p.surface, background=p.panel, foreground=p.text,
                        insertcolor=p.text, bordercolor=p.border, lightcolor=p.border, darkcolor=p.border,
                        arrowcolor=p.text, padding=5)
        style.map(name, fieldbackground=[("disabled", p.panel), ("readonly", p.surface)],
                  foreground=[("disabled", p.muted), ("readonly", p.text)],
                  background=[("disabled", p.panel), ("pressed", p.hover), ("active", p.hover)],
                  arrowcolor=[("disabled", p.muted), ("active", p.text)],
                  bordercolor=[("focus", p.primary)])
    for name in ("TCheckbutton", "TRadiobutton"):
        style.configure(name, background=p.background, foreground=p.text, focuscolor=p.primary)
        style.map(name, background=[("active", p.background)],
                  foreground=[("disabled", p.muted), ("active", p.text)])
    style.configure("Theme.TRadiobutton", indicatoron=False, background=p.panel,
                    foreground=p.text, padding=(10, 5), borderwidth=1, relief="flat",
                    focusthickness=2, focuscolor=p.primary)
    # Selected precedes active so hover cannot erase the visible active mode.
    style.map("Theme.TRadiobutton",
              background=[("disabled", p.background), ("selected", p.primary),
                          ("pressed", p.hover), ("active", p.hover)],
              foreground=[("disabled", p.muted), ("selected", p.on_primary),
                          ("pressed", p.text), ("active", p.text)],
              bordercolor=[("focus", p.primary), ("selected", p.primary), ("active", p.border)])
    style.layout("Theme.TRadiobutton", [("Radiobutton.padding", {"sticky": "nswe", "children": [
        ("Radiobutton.focus", {"sticky": "nswe", "children": [
            ("Radiobutton.label", {"sticky": "nswe"})]})]})])
    style.configure("Treeview", background=p.surface, fieldbackground=p.surface,
                    foreground=p.text, bordercolor=p.border, lightcolor=p.border, darkcolor=p.border, rowheight=27)
    style.map("Treeview", background=[("selected", p.primary)],
              foreground=[("selected", p.on_primary)])
    style.configure("Treeview.Heading", background=p.panel, foreground=p.text, padding=(5, 6),
                    relief="flat", lightcolor=p.border, darkcolor=p.border, bordercolor=p.border)
    style.map("Treeview.Heading", background=[("active", p.hover)])
    for name in ("TNotebook", "Workspace.TNotebook"):
        style.configure(name, background=p.background, bordercolor=p.border,
                        lightcolor=p.border, darkcolor=p.border, tabmargins=(0, 4, 0, 0))
    for name in ("TNotebook.Tab", "Workspace.TNotebook.Tab"):
        style.configure(name, background=p.panel, foreground=p.muted, padding=(12, 8),
                        lightcolor=p.border, darkcolor=p.border, bordercolor=p.border)
        style.map(name, background=[("selected", p.surface), ("active", p.hover)],
                  foreground=[("selected", p.text), ("active", p.text)])
    for name in ("Horizontal.TScrollbar", "Vertical.TScrollbar"):
        style.configure(name, background=p.panel, troughcolor=p.background,
                        bordercolor=p.border, arrowcolor=p.text)
        style.map(name, background=[("active", p.hover), ("pressed", p.primary)])
    style.configure("TPanedwindow", background=p.border)
    style.configure("TProgressbar", background=p.primary, troughcolor=p.panel)
    style.configure("TLabelframe", background=p.background, bordercolor=p.border)
    style.configure("TLabelframe.Label", background=p.background, foreground=p.muted)
    style.configure("MapStatus.TLabel", background=p.background, foreground=p.primary,
                    font=("Segoe UI", 10, "bold"))
    style.configure("MapWarning.TLabel", background=p.background, foreground=p.accent,
                    font=("Segoe UI", 10, "bold"))
    return style


def _role_options(role, palette):
    p = palette
    roles = {
        "background": {"background": p.background},
        "surface": {"background": p.background},
        "panel": {"background": p.panel},
        "card": {"background": p.panel},
        "text": {"background": p.background, "foreground": p.text},
        "heading": {"background": p.background, "foreground": p.text},
        "muted": {"background": p.background, "foreground": p.muted},
        "status": {"background": p.status, "foreground": p.muted},
        "placeholder": {"background": p.surface, "foreground": p.muted},
        "button": {"background": p.panel, "foreground": p.text,
                   "activebackground": p.hover, "activeforeground": p.text,
                   "disabledforeground": p.muted, "highlightbackground": p.border,
                   "highlightcolor": p.primary},
        "primary": {"background": p.primary, "foreground": p.on_primary,
                    "activebackground": p.primary, "activeforeground": p.on_primary,
                    "disabledforeground": p.muted, "highlightbackground": p.border,
                    "highlightcolor": p.primary},
        "entry": {"background": p.surface, "foreground": p.text,
                  "insertbackground": p.text, "selectbackground": p.primary,
                  "selectforeground": p.on_primary, "disabledbackground": p.panel,
                  "disabledforeground": p.muted, "readonlybackground": p.panel,
                  "highlightbackground": p.border, "highlightcolor": p.primary},
        "menu": {"background": p.surface, "foreground": p.text,
                 "activebackground": p.primary, "activeforeground": p.on_primary,
                 "disabledforeground": p.muted},
        "canvas": {"background": p.background, "highlightbackground": p.border},
        "checkbutton": {"background": p.background, "foreground": p.text,
                        "activebackground": p.background, "activeforeground": p.text,
                        "selectcolor": p.surface, "disabledforeground": p.muted},
    }
    return roles.get(role, roles["surface"]).copy()


def _apply_role(widget, role, overrides, palette):
    options = _role_options(role, palette)
    options.update({key: getattr(palette, value, value) for key, value in overrides.items()})
    supported = widget.keys()
    widget.configure(**{key: value for key, value in options.items() if key in supported})


def register_widget(widget, role="surface", **overrides):
    """Assign a Tk role; overrides map widget options to palette fields or literals."""
    _ROLES[widget] = (role, overrides)
    _apply_role(widget, role, overrides, get_palette(current_theme_name(widget)))
    return widget


def style_widget_tree(widget):
    """Theme legacy Tk dialogs by widget type, without matching previous colors."""
    palette = get_palette(current_theme_name(widget))
    if widget in _ROLES:
        _apply_role(widget, *_ROLES[widget], palette)
    elif not isinstance(widget, ttk.Widget):
        roles = ((tk.Menu, "menu"), (tk.Button, "button"), (tk.Entry, "entry"),
                 (tk.Text, "entry"), (tk.Listbox, "entry"), (tk.Checkbutton, "checkbutton"),
                 (tk.Radiobutton, "checkbutton"), (tk.Label, "text"), (tk.Canvas, "canvas"))
        role = next((name for klass, name in roles if isinstance(widget, klass)), "surface")
        register_widget(widget, role)
    if isinstance(widget, ttk.Treeview):
        widget.tag_configure("invalid", background=palette.invalid_background, foreground=palette.invalid_text)
        widget.tag_configure("warning", background=palette.warning_background, foreground=palette.accent)
        widget.tag_configure("normal", background=palette.surface, foreground=palette.text)
    for child in widget.winfo_children():
        style_widget_tree(child)


def apply_theme(root, name, persist=True, path=None):
    """Apply all styles even when reapplying the current theme at startup."""
    if name not in THEMES:
        raise ValueError(f"Unknown application theme: {name}")
    root = root._root()
    root._cycloneaid_theme_name = name
    _styles(root, THEMES[name])
    style_widget_tree(root)
    if persist:
        _save_preference(name, path)
    root.event_generate("<<CycloneAidThemeChanged>>", when="tail")
    return THEMES[name]


class ThemeToggle(ttk.Frame):
    """Two labeled choices with visible selection and normal keyboard navigation."""
    def __init__(self, parent, command=None, **kwargs):
        super().__init__(parent, style="Workspace.TFrame", **kwargs)
        self.command = command
        self.variable = tk.StringVar(self, value=current_theme_name(self))
        self.buttons = []
        for index, (label, name) in enumerate((("Sky", "Sky Light"), ("Typhoon", "Typhoon Dark"))):
            button = ttk.Radiobutton(self, text=label, value=name, variable=self.variable,
                                     style="Theme.TRadiobutton", command=self._choose, takefocus=True)
            button.grid(row=0, column=index, sticky="nsew")
            button.bind("<Left>", lambda event, i=index: self._step(i, -1))
            button.bind("<Right>", lambda event, i=index: self._step(i, 1))
            button.bind("<Return>", lambda event, n=name: self._activate(n))
            self.buttons.append(button)
        self._theme_binding = self._root().bind("<<CycloneAidThemeChanged>>", self._sync, add="+")
        self.bind("<Destroy>", self._destroy_binding, add="+")

    def _sync(self, event=None):
        self.variable.set(current_theme_name(self))

    def _choose(self):
        if self.command:
            self.command(self.variable.get())
        else:
            apply_theme(self._root(), self.variable.get())

    def _activate(self, name):
        self.variable.set(name)
        self._choose()
        return "break"

    def _step(self, index, direction):
        button = self.buttons[(index+direction) % len(self.buttons)]
        button.focus_set()
        return self._activate(str(button["value"]))

    def _destroy_binding(self, event):
        if event.widget is self:
            self._root().unbind("<<CycloneAidThemeChanged>>", self._theme_binding)
