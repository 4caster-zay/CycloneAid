"""Storm-name editing through the real workspace, recovery, and chart pipeline."""
from dataclasses import replace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cycloneaid.model import ForecastPoint
from cycloneaid.rendering import RenderRequest, build_figure, export_figure
from cycloneaid.session import (ForecastSession, SessionSettings, load_project,
                                point_to_row, save_project)


def forecast_rows():
    return tuple(point_to_row(ForecastPoint(f"2026-01-0{day}T00:00Z", 10+day/10, 125,
                                            wind, intensity_class=intensity))
                 for day, wind, intensity in ((1, 40, "TS"), (2, 80, "C1")))


class UnnamedChartTests(unittest.TestCase):
    def tearDown(self):
        import matplotlib.pyplot as plt
        plt.close("all")

    def test_unnamed_chart_titles_and_png_preserve_blank_metadata(self):
        from PIL import Image
        from matplotlib.text import Text
        session = ForecastSession(forecast_rows(), SessionSettings(storm_name="", geography_mode="degraded"))
        for product in ("track", "prognostic", "ri"):
            with self.subTest(product=product):
                figure = build_figure(RenderRequest.from_session(session, product))
                text = " ".join(item.get_text() for item in figure.findobj(match=Text))
                self.assertIn("untitled storm", text.casefold())
                self.assertEqual(figure._cycloneaid_provenance["settings"]["storm_name"], "")
                self.assertEqual(session.settings.storm_name, "")
                if product == "ri":
                    with TemporaryDirectory() as directory:
                        path = Path(directory)/"untitled.png"
                        export_figure(figure, path, dpi=35)
                        with Image.open(path) as image:
                            metadata = json.loads(image.info["Description"])
                        self.assertEqual(metadata["settings"]["storm_name"], "")


@unittest.skipUnless(os.environ.get("CYCLONEAID_GUI_TESTS") == "1",
                     "Set CYCLONEAID_GUI_TESTS=1 with a working X display")
class WorkspaceNameIntegrationTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        import storm_tracker_gui as ui
        self.ui = ui
        self.tmp = TemporaryDirectory()
        self.recovery = Path(self.tmp.name)/"recovery.json"
        self.preference = Path(self.tmp.name)/"appearance.json"
        self.patches = [patch("cycloneaid.gui_session.recovery_path", return_value=self.recovery),
                        patch("cycloneaid.ui_theme.preference_path", return_value=self.preference),
                        patch.object(ui, "_HAS_MAP", False),
                        patch("cycloneaid.gui_session.messagebox.showwarning"),
                        patch("cycloneaid.gui_session.messagebox.showerror")]
        for item in self.patches:
            item.start()
        self.root = tk.Tk()
        self.root.geometry("1300x750")
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.screen = ui.DataEntryScreen(self.root, lambda: None)
        self.screen.pack(fill="both", expand=True)
        self.root.update()
        # Tests explicitly exercise recovery rather than the startup prompt.
        self.screen.after_cancel(self.screen._recovery_after)
        self.screen._recovery_after = None

    def tearDown(self):
        self.screen._discard = True
        self.screen.destroy()
        self.root.update()
        self.root.destroy()
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()
        self.assertEqual(self.errors, [])

    def test_new_blank_draft_survives_other_edits_and_undo_groups_name(self):
        screen = self.screen
        self.assertEqual(screen.name_entry.get(), "")
        self.assertEqual(screen.controller.session.settings.storm_name, "")
        self.assertFalse(screen.controller.dirty)
        self.assertEqual(screen._name_placeholder.winfo_manager(), "place")
        screen._commit(settings=replace(screen.controller.session.settings, storm_name="CycloneAid"))
        screen.controller.mark_saved()
        screen.name_entry.focus_force()
        screen.name_entry.delete(0, "end")
        self.assertEqual(screen.name_entry.get(), "")
        self.assertEqual(screen.controller.session.settings.storm_name, "CycloneAid")
        self.assertIn("Unsaved changes", screen._project_status_var.get())
        screen.name_entry.insert(0, "New storm")
        screen.name_entry.icursor(3)
        screen.add_row()
        self.assertEqual(screen.name_entry.get(), "New storm")
        self.assertEqual(screen.name_entry.index("insert"), 3)
        before = len(screen.controller._undo)
        screen.name_entry.event_generate("<Return>")
        self.root.update()
        self.assertEqual(screen.controller.session.settings.storm_name, "New storm")
        self.assertEqual(len(screen.controller._undo), before+1)
        screen.undo()
        self.assertEqual(screen.name_entry.get(), "CycloneAid")
        self.assertEqual(len(screen.controller.session.rows), 1)
        screen.redo()
        self.assertEqual(screen.name_entry.get(), "New storm")

    def test_save_flushes_pending_name_and_marks_saved(self):
        screen = self.screen
        screen.storm_name_var.set("  Draft storm  ")
        self.assertTrue(screen._has_pending_name_edit())
        self.assertFalse(screen.controller.dirty)
        screen._project_path = str(Path(self.tmp.name)/"project.json")
        self.assertTrue(screen.save_session())
        self.assertEqual(load_project(screen._project_path).settings.storm_name, "  Draft storm  ")
        self.assertFalse(screen._has_pending_name_edit())
        self.assertFalse(screen.controller.dirty)
        self.assertIn("Saved", screen._project_status_var.get())
        self.assertFalse(self.recovery.exists())

    def test_autosave_captures_draft_without_splitting_name_history(self):
        screen = self.screen
        screen.storm_name_var.set("Draft")
        before = len(screen.controller._undo)
        screen._autosave()
        self.assertEqual(load_project(self.recovery).settings.storm_name, "Draft")
        self.assertEqual(screen.controller.session.settings.storm_name, "")
        self.assertEqual(len(screen.controller._undo), before)
        self.assertTrue(screen._has_pending_name_edit())
        screen.storm_name_var.set("Completed draft")
        screen._flush_name_edit()
        self.assertEqual(len(screen.controller._undo), before+1)
        screen.undo()
        self.assertEqual(screen.storm_name_var.get(), "")

    def test_pending_name_triggers_leave_confirmation_and_new_starts_blank(self):
        screen = self.screen
        screen.storm_name_var.set("Unsaved draft")
        with patch("cycloneaid.gui_session.messagebox.askyesnocancel", return_value=None) as prompt:
            self.assertFalse(screen._confirm_leave())
        prompt.assert_called_once()
        self.assertEqual(screen.storm_name_var.get(), "Unsaved draft")
        self.assertTrue(screen.controller.dirty)
        with patch("cycloneaid.gui_session.messagebox.askyesnocancel", return_value=False):
            screen.new_session()
        self.assertEqual(screen.name_entry.get(), "")
        self.assertEqual(screen.controller.session.settings.storm_name, "")
        self.assertFalse(screen.controller.dirty)
        self.assertFalse(screen._has_pending_name_edit())

    def test_blank_existing_project_loads_unchanged_and_preview_flushes_draft(self):
        screen = self.screen
        project = Path(self.tmp.name)/"existing.json"
        settings = SessionSettings(storm_name="", geography_mode="degraded")
        save_project(ForecastSession(forecast_rows(), settings), project)
        with patch("cycloneaid.gui_session.filedialog.askopenfilename", return_value=str(project)):
            screen.open_session()
        self.assertEqual(screen.name_entry.get(), "")
        screen.storm_name_var.set("Preview draft")
        with patch.object(screen.renderer, "submit") as submit:
            screen.preview_track()
        request = submit.call_args.args[0]
        self.assertEqual(request.settings.storm_name, "Preview draft")
        self.assertEqual(request.revision, screen.controller.session.revision)
        self.assertFalse(screen._has_pending_name_edit())
        self.assertTrue(screen.controller.dirty)

    def test_text_keyboard_undo_does_not_undo_session_rows(self):
        from tkinter import ttk
        screen = self.screen
        screen.add_row()
        screen.session_settings()
        editor = next(child for child in screen._settings_window.winfo_children()
                      if isinstance(child, ttk.Entry) and int(child.grid_info()['row']) == 1)
        editor.focus_force()
        self.root.update()
        editor.delete(0, 'end')
        editor.insert(0, 'Editing')
        before = screen.controller.session
        screen.undo(SimpleNamespace())
        self.assertEqual(screen.controller.session, before)
        self.assertEqual(editor.get(), 'Editing')

    def test_relaunch_opens_editor_with_saved_theme_and_blank_name(self):
        self.preference.write_text('{"theme": "Sky Light"}')
        app = self.ui.StormTrackerApp()
        try:
            app.update_idletasks()
            self.assertIsInstance(app.current_frame, self.ui.DataEntryScreen)
            self.assertEqual(app.current_frame.theme_toggle.variable.get(), "Sky Light")
            self.assertEqual(app.current_frame.name_entry.get(), "")
            self.assertEqual(app.current_frame.controller.session.settings.preset, "Forecaster")
            self.assertFalse(app.current_frame.controller.dirty)
        finally:
            app.current_frame._discard = True
            app.current_frame.destroy()
            for identifier in app.tk.call("after", "info"):
                app.after_cancel(identifier)
            app.destroy()

    def test_real_toggle_and_menus_keep_contrast_and_preference(self):
        from tkinter import ttk
        screen = self.screen
        style = ttk.Style(self.root)
        for index, name in ((0, "Sky Light"), (1, "Typhoon Dark")):
            screen.theme_toggle.buttons[index].invoke()
            self.root.update()
            palette = self.ui.CURRENT_THEME
            self.assertEqual(screen.theme_toggle.variable.get(), name)
            self.assertEqual(json.loads(self.preference.read_text())["theme"], name)
            self.assertEqual(screen.controller.session.settings.preset, "Forecaster")
            for state in (("active",), ("pressed",), ("focus",)):
                self.assertEqual(style.lookup("Workspace.TMenubutton", "foreground", state), palette.text)
                self.assertEqual(style.lookup("Workspace.TMenubutton", "background", state),
                                 palette.hover if state == ("active",) else
                                 palette.border if state == ("pressed",) else palette.panel)
            self.assertEqual(style.lookup("Workspace.TMenubutton", "foreground", ("disabled",)), palette.muted)
            self.assertEqual(style.lookup("Theme.TRadiobutton", "foreground", ("selected", "active")),
                             palette.on_primary)


if __name__ == "__main__":
    unittest.main()
