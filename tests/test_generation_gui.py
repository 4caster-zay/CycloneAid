from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from cycloneaid.generation import generate_rows
from cycloneaid.session import load_project


@unittest.skipUnless(os.environ.get("CYCLONEAID_GUI_TESTS") == "1",
                     "Set CYCLONEAID_GUI_TESTS=1 with a working X display")
class GenerateRowsDialogTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        import storm_tracker_gui as ui
        self.tmp = TemporaryDirectory()
        self.patches = [patch("cycloneaid.gui_session.recovery_path", return_value=Path(self.tmp.name)/"recovery.json"),
                        patch.object(ui, "_HAS_MAP", False)]
        for item in self.patches:
            item.start()
        self.root = tk.Tk()
        self.root.withdraw()
        self.callback_errors = []
        self.root.report_callback_exception = lambda *args: self.callback_errors.append(args)
        self.screen = ui.DataEntryScreen(self.root, lambda: None)
        self.screen.pack()
        self.root.update()

    def tearDown(self):
        self.screen._discard = True
        self.screen.destroy()
        self.root.update()
        self.root.destroy()
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()
        self.assertEqual(self.callback_errors, [])

    def test_empty_table_start_is_deliberate_preview_cancel_and_validation(self):
        screen = self.screen
        self.assertEqual(screen.controller.session.rows, ())
        before = screen.controller.session
        dialog = screen.generate_rows()
        self.root.update()
        self.assertEqual(dialog.start_var.get(), "")
        self.assertEqual(dialog.interval_var.get(), "6")
        self.assertEqual(dialog.horizon_var.get(), "120")
        self.assertEqual(str(dialog.apply_button["state"]), "disabled")
        dialog.start_var.set("2026-01-01 00:00")
        self.assertIn("Rows to append: 21", dialog.preview_var.get())
        self.assertIn("2026-01-06T00:00:00+00:00", dialog.preview_var.get())
        self.assertEqual(screen.controller.session, before)
        dialog.horizon_var.set("121")
        self.assertIn("exact multiple", dialog.error_var.get())
        self.assertEqual(str(dialog.apply_button["state"]), "disabled")
        dialog.destroy()
        self.assertEqual(screen.controller.session, before)
        self.assertFalse(screen.controller.dirty)

    def test_apply_one_step_undo_recovery_and_render_becomes_available_after_entry(self):
        screen = self.screen
        before = screen.controller.session
        dialog = screen.generate_rows()
        dialog.start_var.set("2026-01-01 00:00")
        dialog.horizon_var.set("6")
        dialog._apply()
        self.root.update()
        self.assertEqual(len(screen.controller.session.rows), 2)
        self.assertEqual(screen.controller.session.settings, before.settings)
        self.assertTrue(screen.controller.dirty)
        self.assertTrue(all(str(button["state"]) == "disabled" for button in screen._action_btns))
        screen._autosave()
        restored = load_project(Path(self.tmp.name)/"recovery.json")
        self.assertEqual(restored.rows, screen.controller.session.rows)
        screen.undo()
        self.assertEqual(screen.controller.session.rows, before.rows)
        self.assertFalse(screen.controller.dirty)
        screen.redo()
        completed = tuple(replace(row, values=(row.values[0], "", "10", "125", "40",
                                               "False", "Tropical", "TS", "False"))
                          for row in screen.controller.session.rows)
        screen._commit(rows=completed, infer_issue_time=False)
        self.assertTrue(screen._is_table_valid())
        self.assertTrue(all(str(button["state"]) == "normal" for button in screen._action_btns))

    def test_existing_rows_suggest_start_follow_interval_and_preserve_manual_start(self):
        rows = generate_rows("2026-01-01 00:00", 6, 6)
        self.screen._commit(rows=rows, infer_issue_time=False)
        before = self.screen.controller.session
        dialog = self.screen.generate_rows()
        self.assertEqual(dialog.start_var.get(), "2026-01-01T12:00:00+00:00")
        dialog.interval_var.set(".5")
        self.assertEqual(dialog.start_var.get(), "2026-01-01T06:30:00+00:00")
        dialog.start_var.set("2026-01-02 00:00")
        dialog.interval_var.set("1")
        self.assertEqual(dialog.start_var.get(), "2026-01-02 00:00")
        dialog.horizon_var.set("1")
        self.assertEqual(self.screen.controller.session, before)
        dialog._apply()
        self.assertEqual(self.screen.controller.session.rows[:2], rows)
        self.assertEqual(self.screen.controller.session.settings, before.settings)
        self.screen.undo()
        self.assertEqual(self.screen.controller.session.rows, rows)

    def test_invalid_existing_rows_and_overlap_never_apply(self):
        self.screen.add_row()
        before = self.screen.controller.session
        dialog = self.screen.generate_rows()
        dialog.start_var.set("2026-01-01 00:00")
        self.assertIn("Existing row 1", dialog.error_var.get())
        dialog._apply()
        self.assertEqual(self.screen.controller.session, before)
        dialog.destroy()
        rows = generate_rows("2026-01-01 00:00", 6, 6)
        self.screen._commit(rows=rows, infer_issue_time=False)
        dialog = self.screen.generate_rows()
        dialog.start_var.set("2026-01-01 06:00")
        self.assertIn("later than the final", dialog.error_var.get())
        before = self.screen.controller.session
        dialog._apply()
        self.assertEqual(self.screen.controller.session, before)
        dialog.destroy()

    def test_fractional_timestamps_survive_display_and_unchanged_cell_edit(self):
        screen = self.screen
        rows = generate_rows("2026-01-01 00:00", ".000025", ".000075")
        completed = tuple(replace(row, values=(row.values[0], "", "10", "125", "40",
                                               "False", "Tropical", "TS", "False")) for row in rows)
        screen._commit(rows=completed, infer_issue_time=False)
        displayed = tuple(screen.tree.item(row.row_id, "values")[0] for row in completed)
        self.assertEqual(len(set(displayed)), len(rows))
        self.assertEqual(displayed[1], "2026-01-01 00:00:00.090000")
        for row, text in zip(completed, displayed):
            screen._on_cell_save(row.row_id, 0, text)
        self.assertEqual(tuple(point.time for point in screen._validated()[0]),
                         tuple(pd.Timestamp(row.values[0]) for row in rows))

    def test_append_invalidates_renderer_and_marks_existing_preview_as_previous(self):
        screen = self.screen
        revision = screen.controller.session.revision
        preview_window = Mock()
        screen._previews["track"] = (None, preview_window, revision)
        with patch.object(screen.renderer, "invalidate", wraps=screen.renderer.invalidate) as invalidate:
            dialog = screen.generate_rows()
            dialog.start_var.set("2026-01-01 00:00")
            dialog.horizon_var.set("6")
            dialog._apply()
        invalidate.assert_called_once_with(screen.controller.session.revision)
        preview_window.title.assert_called_once_with("Track Preview — previous session state")
        screen._previews.clear()


if __name__ == "__main__":
    unittest.main()
