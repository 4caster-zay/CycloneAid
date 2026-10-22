"""Appearance persistence and atomic storm-name draft regressions."""
from dataclasses import replace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cycloneaid.gui_name import NameEditingMixin, display_storm_name
from cycloneaid.session import SessionController, load_project, save_project
from cycloneaid.ui_theme import (DEFAULT_THEME, apply_theme, get_palette,
                                 load_theme_preference, preference_path,
                                 register_widget, ThemeToggle)


class AppearancePreferenceTests(unittest.TestCase):
    def test_missing_corrupt_and_unrecognized_preferences_use_default(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)/"appearance.json"
            self.assertEqual(load_theme_preference(path), DEFAULT_THEME)
            for value in ("not json", '[]', '{"theme": "obsolete"}', '{"theme": []}'):
                path.write_text(value)
                self.assertEqual(load_theme_preference(path), DEFAULT_THEME)
            path.write_text('{"theme": "Sky Light"}')
            self.assertEqual(load_theme_preference(path), "Sky Light")

    def test_preferences_use_app_state_outside_project(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_STATE_HOME": directory,
                                                                       "LOCALAPPDATA": directory}):
            self.assertEqual(preference_path(), Path(directory)/"cycloneaid"/"appearance.json")

    def test_display_name_fallback_does_not_rewrite_input(self):
        for value in ("", "  ", None):
            self.assertEqual(display_storm_name(value), "Untitled storm")
        self.assertEqual(display_storm_name("  Haiyan  "), "Haiyan")


@unittest.skipUnless(os.environ.get("CYCLONEAID_GUI_TESTS") == "1",
                     "Set CYCLONEAID_GUI_TESTS=1 with a working X display")
class ThemeNameTkTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from tkinter import ttk

        class Harness(NameEditingMixin, ttk.Frame):
            def __init__(self, master):
                super().__init__(master)
                self.controller = SessionController()
                self._init_name_editing()
                self.status_updates = 0
                self.storm_name_var = tk.StringVar(self, value="CycloneAid")
                self.entry = tk.Entry(self, textvariable=self.storm_name_var)
                register_widget(self.entry, "entry")
                self.entry.pack()
                self.other_entry = ttk.Entry(self)
                self.other_entry.pack()
                self._bind_name_entry(self.entry)

            def _commit(self, **kwargs):
                changed = self.controller.commit(**kwargs)
                if changed:
                    self._sync_name_from_session()
                return changed

            def _update_project_status(self):
                self.status_updates += 1

        self.tk = tk
        self.root = tk.Tk()
        self.root.geometry("600x240")
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.tmp = TemporaryDirectory()
        self.preference = Path(self.tmp.name)/"appearance.json"
        apply_theme(self.root, DEFAULT_THEME, persist=False)
        self.screen = Harness(self.root)
        self.screen.pack(fill="both", expand=True)
        self.root.update()

    def tearDown(self):
        self.root.destroy()
        self.tmp.cleanup()
        self.assertEqual(self.errors, [])

    def test_clearing_and_retyping_is_one_undo_and_preserves_cursor(self):
        screen = self.screen
        screen.entry.focus_force()
        screen.entry.delete(0, "end")
        self.assertEqual(screen.storm_name_var.get(), "")
        self.assertEqual(screen.controller.session.settings.storm_name, "CycloneAid")
        self.assertTrue(screen._has_pending_name_edit())
        screen.entry.insert(0, "New name")
        screen.entry.icursor(3)
        screen._commit(settings=replace(screen.controller.session.settings, confidence="Low"))
        self.assertEqual(screen.entry.get(), "New name")
        self.assertEqual(screen.entry.index("insert"), 3)
        before = len(screen.controller._undo)
        screen.entry.event_generate("<Return>")
        self.root.update()
        self.assertEqual(screen.controller.session.settings.storm_name, "New name")
        self.assertEqual(len(screen.controller._undo), before+1)
        self.assertFalse(screen._has_pending_name_edit())
        screen.controller.undo()
        screen._sync_name_from_session()
        self.assertEqual(screen.entry.get(), "CycloneAid")
        self.assertEqual(screen.controller.session.settings.confidence, "Low")
        screen.controller.redo()
        screen._sync_name_from_session()
        self.assertEqual(screen.entry.get(), "New name")

    def test_blank_name_focus_commit_and_save_round_trip(self):
        screen = self.screen
        screen.entry.focus_force()
        self.root.update()
        screen.entry.delete(0, "end")
        screen.other_entry.focus_force()
        self.root.update()
        self.assertEqual(screen.controller.session.settings.storm_name, "")
        self.assertFalse(screen._has_pending_name_edit())
        self.assertTrue(screen.controller.dirty)
        self.assertEqual(screen._name_placeholder.winfo_manager(), "place")
        path = Path(self.tmp.name)/"blank.json"
        save_project(screen.controller.session, path)
        self.assertEqual(load_project(path).settings.storm_name, "")
        self.assertEqual(display_storm_name(load_project(path).settings.storm_name), "Untitled storm")
        screen.entry.focus_force()
        self.root.update()
        self.assertEqual(screen._name_placeholder.winfo_manager(), "")
        self.assertEqual(screen.entry.get(), "")

    def test_pending_name_flush_and_forced_project_replacement(self):
        screen = self.screen
        screen.storm_name_var.set("  pending title  ")
        self.assertTrue(screen._has_pending_name_edit())
        self.assertFalse(screen.controller.dirty)
        self.assertTrue(screen._flush_name_edit())
        self.assertEqual(screen.controller.session.settings.storm_name, "  pending title  ")
        self.assertFalse(screen._flush_name_edit())
        screen.storm_name_var.set("unfinished")
        screen.controller.commit(settings=replace(screen.controller.session.settings, storm_name="Existing name"))
        screen._sync_name_from_session(force=True)
        self.assertEqual(screen.storm_name_var.get(), "Existing name")
        self.assertFalse(screen._has_pending_name_edit())
        self.assertGreater(screen.status_updates, 0)

    def test_theme_switch_selected_hover_focus_and_relaunch(self):
        from tkinter import ttk
        chosen = []

        def choose(name):
            chosen.append(name)
            apply_theme(self.root, name, path=self.preference)

        toggle = ThemeToggle(self.screen, command=choose)
        toggle.pack()
        self.root.update()
        toggle.buttons[0].invoke()
        self.root.update()
        palette = get_palette("Sky Light")
        style = ttk.Style(self.root)
        self.assertEqual(toggle.variable.get(), "Sky Light")
        self.assertEqual(load_theme_preference(self.preference), "Sky Light")
        self.assertEqual(json.loads(self.preference.read_text()), {"theme": "Sky Light"})
        for state in (("selected",), ("selected", "active"), ("selected", "pressed"),
                      ("selected", "focus")):
            self.assertEqual(style.lookup("Theme.TRadiobutton", "foreground", state), palette.on_primary)
            self.assertEqual(style.lookup("Theme.TRadiobutton", "background", state), palette.primary)
        toggle.buttons[0].focus_force()
        toggle.buttons[0].event_generate("<Right>")
        self.root.update()
        self.assertEqual(chosen[-1], "Typhoon Dark")
        self.assertEqual(toggle.variable.get(), "Typhoon Dark")
        toggle.buttons[0].focus_force()
        toggle.buttons[0].event_generate("<Return>")
        self.root.update()
        self.assertEqual(chosen[-1], "Sky Light")
        # Startup must initialize styles even when the saved theme is current.
        style.configure("TButton", foreground="magenta")
        apply_theme(self.root, load_theme_preference(self.preference), persist=False)
        self.assertEqual(style.lookup("TButton", "foreground"), palette.text)
        self.assertEqual(style.lookup("TButton", "foreground", ("disabled",)), palette.muted)

    def test_registered_roles_survive_theme_switch_without_color_matching(self):
        label = register_widget(self.tk.Label(self.screen, text="status", bg="magenta"), "muted")
        label.pack()
        for name in ("Sky Light", "Typhoon Dark"):
            palette = apply_theme(self.root, name, persist=False)
            self.root.update()
            self.assertEqual(label["background"], palette.background)
            self.assertEqual(label["foreground"], palette.muted)
            self.assertEqual(self.screen.entry["insertbackground"], palette.text)
        with patch("cycloneaid.session.atomic_json", side_effect=PermissionError("read-only")):
            apply_theme(self.root, "Sky Light", path=self.preference)
        self.assertEqual(getattr(self.root, "_cycloneaid_theme_name"), "Sky Light")


if __name__ == "__main__":
    unittest.main()
