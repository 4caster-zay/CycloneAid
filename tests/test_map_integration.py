"""Workspace integration for explicit geography setup and project ownership."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from cycloneaid.rendering import RenderResult
from cycloneaid.session import ForecastSession, SessionSettings, point_to_row, save_project
from test_core import BASE, point


@unittest.skipUnless(os.environ.get("CYCLONEAID_GUI_TESTS") == "1", "Requires a working X display")
class WorkspaceMapIntegrationTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        import storm_tracker_gui as ui

        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.recovery = Path(self.tmp.name) / "recovery.json"
        self.readiness = Mock(return_value=())
        self.patches = [
            patch("cycloneaid.gui_session.recovery_path", return_value=self.recovery),
            patch("cycloneaid.gui_maps.geography_readiness", self.readiness),
            patch("cycloneaid.geography.geography_readiness", self.readiness),
            patch.object(ui, "_HAS_MAP", False),
            patch("cycloneaid.gui_maps.messagebox.askyesno", return_value=True),
            patch("cycloneaid.gui_session.messagebox.askyesnocancel", return_value=False),
            patch("cycloneaid.gui_session.messagebox.showerror"),
            patch("cycloneaid.gui_session.messagebox.showwarning"),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.root = tk.Tk()
        self.root.withdraw()
        self.callback_errors = []
        self.root.report_callback_exception = lambda *args: self.callback_errors.append(args)
        self.screen = ui.DataEntryScreen(self.root, lambda: None)
        self.screen.pack(fill="both", expand=True)
        self.root.update()

    def tearDown(self):
        self.screen._discard = True
        self.screen.destroy()
        self.root.update()
        self.root.destroy()
        self.assertEqual(self.callback_errors, [])

    @staticmethod
    def project(name="Map test", mode="degraded"):
        return ForecastSession(
            rows=tuple(point_to_row(item) for item in (point(), point(24, wind_kt=80))),
            settings=SessionSettings(storm_name=name, geography_mode=mode, issue_time=BASE.isoformat()))

    def start_preparation(self):
        self.screen._replace_project(self.project())
        self.readiness.return_value = ("land",)

        def submit(request, *args):
            self.assertEqual(request, "assets")
            self.screen.renderer._pending = (7, -1, "assets")
            return 7

        with patch.object(self.screen.renderer, "submit", side_effect=submit):
            self.screen.enable_maps()
        self.assertEqual(self.screen._map_asset_job_id, 7)

    def finish_preparation(self, error=""):
        self.readiness.return_value = () if not error else ("land",)
        self.screen.renderer._pending = None
        # Replace the scheduled poll with one deterministic completion, retaining
        # exactly one timer for the normal workspace shutdown to cancel.
        self.screen.after_cancel(self.screen._poll_after)
        with patch.object(self.screen.renderer, "poll", return_value=RenderResult(7, -1, "assets", error=error)):
            self.screen._poll_renderer()

    def test_startup_full_mode_and_loaded_mode_are_visible_without_auto_switching(self):
        screen = self.screen
        self.assertEqual(screen.controller.session.settings.geography_mode, "full")
        self.assertEqual(screen._chart_map_status, "Full maps ready")
        self.assertEqual(screen._map_readiness_label.cget("text"), "Full maps ready")
        self.assertEqual(screen.storm_name_var.get(), "")
        screen._replace_project(self.project(mode="degraded"))
        self.assertEqual(screen._chart_map_status, "Without basemap")
        self.assertEqual(screen.controller.session.settings.geography_mode, "degraded")
        self.readiness.return_value = ("land",)
        screen._replace_project(self.project(mode="full"))
        self.assertEqual(screen._chart_map_status, "Map setup needed")
        self.assertTrue(screen._enable_maps_button.grid_info())
        self.assertTrue(screen._without_basemap_button.grid_info())
        self.assertFalse(screen.renderer.busy)

    def test_missing_full_map_cache_blocks_chart_preview_and_export_before_worker_or_file_dialog(self):
        screen = self.screen
        self.readiness.return_value = ("land",)
        screen._replace_project(self.project(mode="full"))
        with patch.object(screen.renderer, "submit") as submit, \
                patch("cycloneaid.gui_session.filedialog.asksaveasfilename") as filename, \
                patch("cycloneaid.gui_session.error_message"):
            for product in ("track", "prognostic"):
                for exporting in (False, True):
                    with self.subTest(product=product, exporting=exporting):
                        screen._start_plot(product, exporting)
                        self.assertEqual(screen._output_state_kind[product], "failed")
                        self.assertIn("Map setup needed", screen._output_states[product].get())
                        self.assertIn("explicitly continue without basemap", screen._output_states[product].get())
            submit.assert_not_called()
            filename.assert_not_called()
        self.assertEqual(screen.controller.session.settings.geography_mode, "full")
        self.assertEqual(screen._chart_map_status, "Map setup needed")

    def test_explicit_degraded_preview_and_wind_change_do_not_require_chart_assets(self):
        screen = self.screen
        self.readiness.return_value = ("land",)
        screen._replace_project(self.project(mode="degraded"))
        with patch.object(screen.renderer, "submit", return_value=7) as submit:
            screen._start_plot("track")
            request = submit.call_args.args[0]
            self.assertEqual(request.product, "track")
            self.assertEqual(request.settings.geography_mode, "degraded")
        screen._replace_project(self.project(mode="full"))
        with patch.object(screen.renderer, "submit", return_value=7) as submit:
            screen._start_plot("ri")
            self.assertEqual(submit.call_args.args[0].product, "ri")
        screen._set_buttons_loading(False)

    def test_asset_completion_activates_same_project_after_row_and_property_edits(self):
        screen = self.screen
        self.start_preparation()
        generation = screen._project_generation
        rows = list(screen.controller.session.rows)
        values = list(rows[0].values)
        values[2] = "10.5"
        rows[0] = replace(rows[0], values=tuple(values))
        screen._commit(rows=rows, settings=replace(screen.controller.session.settings, confidence="High"))
        self.assertEqual(screen._project_generation, generation)
        with patch.object(screen, "_output_render_finished") as chart_result:
            self.finish_preparation()
            chart_result.assert_not_called()
        self.assertEqual(screen.controller.session.rows, tuple(rows))
        self.assertEqual(screen.controller.session.settings.confidence, "High")
        self.assertEqual(screen.controller.session.settings.geography_mode, "full")
        self.assertEqual(screen._chart_map_status, "Full maps ready")
        self.assertIsNone(screen._map_asset_job_id)
        self.assertFalse(screen._map_preparation_progress.grid_info())

    def test_new_project_during_preparation_keeps_its_own_mode_and_revision(self):
        screen = self.screen
        self.start_preparation()
        generation = screen._project_generation
        screen.new_session()
        replacement = screen.controller.session
        self.assertEqual(screen._project_generation, generation + 1)
        self.assertEqual(replacement.settings.geography_mode, "full")
        self.assertEqual(replacement.settings.storm_name, "")
        self.finish_preparation()
        self.assertEqual(screen.controller.session, replacement)
        self.assertFalse(screen.controller.dirty)
        self.assertFalse(screen.controller.undo())

    def test_open_project_during_preparation_preserves_loaded_degraded_mode(self):
        screen = self.screen
        self.start_preparation()
        generation = screen._project_generation
        path = Path(self.tmp.name) / "another.cycloneaid.json"
        save_project(self.project("Another project"), path)
        with patch("cycloneaid.gui_session.filedialog.askopenfilename", return_value=str(path)):
            screen.open_session()
        replacement = screen.controller.session
        self.assertEqual(screen._project_generation, generation + 1)
        self.finish_preparation()
        self.assertEqual(screen.controller.session, replacement)
        self.assertEqual(screen.controller.session.settings.geography_mode, "degraded")
        self.assertEqual(screen._chart_map_status, "Without basemap")
        self.assertFalse(screen.controller.dirty)

    def test_open_sample_during_preparation_preserves_packaged_sample_mode(self):
        screen = self.screen
        self.start_preparation()
        generation = screen._project_generation
        screen.open_sample()
        replacement = screen.controller.session
        self.assertEqual(screen._project_generation, generation + 1)
        self.assertEqual(replacement.settings.storm_name, "TEST PALAU")
        self.finish_preparation()
        self.assertEqual(screen.controller.session, replacement)
        self.assertEqual(screen.controller.session.settings.geography_mode, "degraded")

    def test_import_during_preparation_does_not_enable_maps_for_imported_data(self):
        from cycloneaid.csvio import export_csv

        screen = self.screen
        self.start_preparation()
        generation = screen._project_generation
        path = Path(self.tmp.name) / "new-track.csv"
        export_csv((point(lat=11), point(24, lat=12)), path)
        with patch("cycloneaid.gui_session.filedialog.askopenfilename", return_value=str(path)):
            screen.import_csv()
        replacement = screen.controller.session
        self.assertEqual(screen._project_generation, generation + 1)
        self.assertEqual(float(replacement.rows[0].values[2]), 11)
        self.finish_preparation()
        self.assertEqual(screen.controller.session, replacement)
        self.assertEqual(screen.controller.session.settings.geography_mode, "degraded")

    def test_recovery_during_preparation_does_not_enable_maps_for_recovered_project(self):
        screen = self.screen
        self.start_preparation()
        generation = screen._project_generation
        save_project(self.project("Recovered project"), self.recovery)
        screen._offer_recovery()
        replacement = screen.controller.session
        self.assertEqual(screen._project_generation, generation + 1)
        self.assertEqual(replacement.settings.storm_name, "Recovered project")
        self.finish_preparation()
        self.assertEqual(screen.controller.session, replacement)
        self.assertEqual(screen.controller.session.settings.geography_mode, "degraded")

    def test_asset_failure_is_consumed_as_setup_failure_and_keeps_full_mode(self):
        screen = self.screen
        self.start_preparation()
        screen._commit(settings=replace(screen.controller.session.settings, geography_mode="full"))
        before = screen.controller.session
        with patch.object(screen, "_output_render_finished") as chart_result:
            self.finish_preparation(error="Network unreachable")
            chart_result.assert_not_called()
        self.assertEqual(screen.controller.session, before)
        self.assertEqual(screen._chart_map_status, "Map setup needed")
        self.assertEqual(screen._enable_maps_button.cget("text"), "Retry map setup")
        self.assertIn("Network unreachable", screen._chart_map_detail)
