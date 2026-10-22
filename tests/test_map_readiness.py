"""Map setup can be tested without Tk, networking, or the workspace adapter."""
from dataclasses import replace
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from cycloneaid.gui_maps import MapReadinessMixin
from cycloneaid.rendering import RenderResult
from cycloneaid.session import SessionController, SessionSettings, point_to_row
from test_core import point


class MapHarness(MapReadinessMixin):
    def __init__(self, mode="full"):
        self.controller = SessionController()
        self.controller.commit(settings=SessionSettings(geography_mode=mode))
        self.controller.mark_saved()
        self.renderer = Mock()
        self.renderer.busy = False
        self.renderer.submit.side_effect = self._submit
        self._project_generation = 1
        self._set_status = Mock()
        self._set_buttons_loading = Mock()
        self._init_map_readiness()

    def _submit(self, request):
        self.renderer.busy = True
        return 7

    def _commit(self, **changes):
        self.controller.commit(**changes)
        self._refresh_map_readiness()

    def complete(self, *, error=""):
        self.renderer.busy = False
        return self._handle_map_asset_result(RenderResult(7, -1, "assets", error=error))


class MapReadinessTests(unittest.TestCase):
    def setUp(self):
        self.readiness_patch = patch("cycloneaid.gui_maps.geography_readiness", return_value=())
        self.readiness = self.readiness_patch.start()
        self.confirm_patch = patch("cycloneaid.gui_maps.messagebox.askyesno", return_value=True)
        self.confirm = self.confirm_patch.start()
        self.addCleanup(self.readiness_patch.stop)
        self.addCleanup(self.confirm_patch.stop)

    def test_startup_only_inspects_cache_and_preserves_stored_mode(self):
        for mode, missing, expected in (("full", (), "Full maps ready"),
                                        ("full", ("land",), "Map setup needed"),
                                        ("degraded", (), "Without basemap"),
                                        ("degraded", ("land",), "Without basemap")):
            with self.subTest(mode=mode, missing=missing):
                self.readiness.return_value = missing
                screen = MapHarness(mode)
                before = screen.controller.session
                screen._refresh_map_readiness()
                self.assertEqual(screen._chart_map_status, expected)
                self.assertEqual(screen.controller.session, before)
                screen.renderer.submit.assert_not_called()
                self.confirm.assert_not_called()

    def test_warm_cache_enables_maps_as_one_undoable_action(self):
        screen = MapHarness("degraded")
        row = point_to_row(point())
        screen.controller.commit(rows=(row,))
        before = screen.controller.session
        screen.enable_maps()
        self.assertEqual(screen.controller.session.settings.geography_mode, "full")
        self.assertEqual(screen.controller.session.rows, before.rows)
        self.assertEqual(screen._chart_map_status, "Full maps ready")
        self.assertTrue(screen.controller.dirty)
        screen.renderer.submit.assert_not_called()
        self.confirm.assert_not_called()
        screen.controller.undo()
        self.assertEqual(screen.controller.session.settings.geography_mode, "degraded")

    def test_missing_cache_offers_background_preparation_without_mutating_session(self):
        self.readiness.return_value = ("land", "cities")
        screen = MapHarness("degraded")
        before = screen.controller.session
        screen.enable_maps()
        screen.renderer.submit.assert_called_once_with("assets")
        self.assertEqual(screen._map_asset_job_id, 7)
        self.assertEqual(screen._map_asset_request_generation, 1)
        self.assertIn("background", screen._chart_map_detail)
        self.assertEqual(screen.controller.session, before)
        screen._set_buttons_loading.assert_called_once_with(True, "Preparing map assets…")
        self.assertIn("OSM", self.confirm.call_args.args[1])

    def test_declining_preparation_keeps_project_and_renderer_untouched(self):
        self.readiness.return_value = ("land",)
        self.confirm.return_value = False
        screen = MapHarness("degraded")
        before = screen.controller.session
        screen.prepare_assets()
        self.assertEqual(screen.controller.session, before)
        screen.renderer.submit.assert_not_called()

    def test_success_enables_requesting_project_and_preserves_intervening_edits(self):
        self.readiness.return_value = ("land",)
        screen = MapHarness("degraded")
        screen.enable_maps()
        row = point_to_row(point())
        screen.controller.commit(rows=(row,), settings=replace(screen.controller.session.settings,
                                                              storm_name="Edited while downloading", confidence="High"))
        self.readiness.return_value = ()
        self.assertTrue(screen.complete())
        self.assertEqual(screen.controller.session.settings.geography_mode, "full")
        self.assertEqual(screen.controller.session.settings.storm_name, "Edited while downloading")
        self.assertEqual(screen.controller.session.settings.confidence, "High")
        self.assertEqual(screen.controller.session.rows, (row,))
        self.assertIsNone(screen._map_asset_job_id)
        self.assertEqual(screen._chart_map_status, "Full maps ready")

    def test_success_does_not_change_project_opened_during_preparation(self):
        self.readiness.return_value = ("land",)
        screen = MapHarness("degraded")
        screen.enable_maps()
        screen._project_generation += 1
        screen.controller.commit(settings=SessionSettings(storm_name="Another project", geography_mode="degraded"))
        before = screen.controller.session
        self.readiness.return_value = ()
        screen.complete()
        self.assertEqual(screen.controller.session, before)
        self.assertEqual(screen._chart_map_status, "Without basemap")
        self.assertIn("kept", screen._set_status.call_args.args[0])

    def test_failure_is_retryable_and_never_silently_downgrades_full_mode(self):
        self.readiness.return_value = ("land",)
        screen = MapHarness("full")
        screen.enable_maps()
        before = screen.controller.session
        screen.complete(error="Network unreachable")
        self.assertEqual(screen.controller.session, before)
        self.assertEqual(screen._chart_map_status, "Map setup needed")
        self.assertIn("Network unreachable", screen._chart_map_detail)
        self.assertIn("Retry", screen._chart_map_detail)
        screen.enable_maps()
        self.assertEqual(screen.renderer.submit.call_count, 2)

    def test_incomplete_success_does_not_enable_maps(self):
        self.readiness.return_value = ("land",)
        screen = MapHarness("degraded")
        screen.enable_maps()
        screen.complete()
        self.assertEqual(screen.controller.session.settings.geography_mode, "degraded")
        self.assertIn("still missing", screen._chart_map_detail)

    def test_explicit_without_basemap_choice_cancels_pending_activation(self):
        self.readiness.return_value = ("land",)
        screen = MapHarness("full")
        screen.enable_maps()
        screen.continue_without_basemap()
        explanation = self.confirm.call_args.args[1]
        self.assertIn("city analysis", explanation)
        self.assertIn("automatic coastline events", explanation)
        self.readiness.return_value = ()
        screen.complete()
        self.assertEqual(screen.controller.session.settings.geography_mode, "degraded")

    def test_submit_failure_and_busy_renderer_keep_session_unchanged(self):
        self.readiness.return_value = ("land",)
        screen = MapHarness("degraded")
        screen.renderer.submit.side_effect = RuntimeError("Process unavailable")
        before = screen.controller.session
        screen.enable_maps()
        self.assertEqual(screen.controller.session, before)
        self.assertIsNone(screen._map_asset_job_id)
        self.assertIn("Process unavailable", screen._chart_map_detail)
        screen.renderer.busy = True
        screen.enable_maps()
        self.assertEqual(screen.renderer.submit.call_count, 1)
        self.assertIn("Wait", screen._set_status.call_args.args[0])

    def test_osm_availability_is_independent_of_chart_cache(self):
        screen = MapHarness()
        screen._refresh_map_readiness()
        screen._refresh_osm_status()
        self.assertEqual(screen._chart_map_status, "Full maps ready")
        self.assertEqual(screen._osm_map_state, "unknown")
        self.assertIn("does not verify tile access", screen._osm_map_status)
        screen._retry_live_map = Mock()
        screen.retry_osm_map()
        screen._retry_live_map.assert_called_once_with()
        self.assertEqual(screen._osm_map_state, "loading")
        screen._refresh_osm_status("unavailable", "Tiles timed out.")
        self.assertIn("Tiles timed out", screen._osm_map_status)
        self.assertEqual(screen._chart_map_status, "Full maps ready")

    def test_osm_retry_failure_has_guidance(self):
        screen = MapHarness()
        screen._retry_live_map = Mock(side_effect=RuntimeError("Offline"))
        screen.retry_osm_map()
        self.assertEqual(screen._osm_map_state, "unavailable")
        self.assertIn("Offline", screen._osm_map_status)
        self.assertIn("retry", screen._osm_map_status)

    def test_other_products_and_unrelated_asset_jobs_do_not_clear_request(self):
        screen = MapHarness()
        self.assertFalse(screen._handle_map_asset_result(RenderResult(1, 0, "track")))
        screen._map_asset_job_id = 7
        self.assertTrue(screen._handle_map_asset_result(RenderResult(6, -1, "assets")))
        self.assertEqual(screen._map_asset_job_id, 7)


@unittest.skipUnless(os.environ.get("CYCLONEAID_GUI_TESTS") == "1", "Requires a working X display")
class MapReadinessWidgetTests(unittest.TestCase):
    def test_controls_expose_setup_progress_retry_and_explicit_degraded_mode(self):
        import tkinter as tk

        class Screen(MapReadinessMixin, tk.Frame):
            def _commit(self, **changes):
                self.controller.commit(**changes)
                self._refresh_map_readiness()

        root = tk.Tk()
        root.withdraw()
        try:
            screen = Screen(root)
            screen.controller = SessionController()
            screen.renderer = Mock(busy=False)
            screen.renderer.submit.return_value = 7
            screen._set_status = Mock()
            screen._set_buttons_loading = Mock()
            screen._project_generation = 1
            screen._init_map_readiness()
            with patch("cycloneaid.gui_maps.geography_readiness", return_value=("land",)), \
                    patch("cycloneaid.gui_maps.messagebox.askyesno", return_value=True):
                screen._build_map_readiness(screen).pack(fill="x")
                self.assertEqual(screen._map_readiness_label.cget("text"), "Map setup needed")
                screen.enable_maps()
                self.assertTrue(screen._map_preparation_progress.grid_info())
                screen._handle_map_asset_result(RenderResult(7, -1, "assets", error="Offline"))
                self.assertFalse(screen._map_preparation_progress.grid_info())
                self.assertEqual(screen._enable_maps_button.cget("text"), "Retry map setup")
                screen.continue_without_basemap()
                self.assertEqual(screen._map_readiness_label.cget("text"), "Without basemap")
                self.assertFalse(screen._without_basemap_button.grid_info())
            screen.destroy()
            root.update()
        finally:
            root.destroy()


@unittest.skipUnless(os.environ.get("CYCLONEAID_GEOGRAPHY_TESTS") == "1", "Requires an already populated geography cache")
class CachedFullMapPreviewTests(unittest.TestCase):
    def test_full_preview_contains_cached_geographic_features_without_network(self):
        import cartopy
        from cartopy.mpl.feature_artist import FeatureArtist
        import matplotlib.pyplot as plt
        from cycloneaid.geography import geography_readiness, get_city_data, get_land_geometry, get_ph_provinces
        from cycloneaid.rendering import RenderRequest, build_figure
        from cycloneaid.session import load_project

        root = Path(__file__).resolve().parents[1]
        cache = Path(os.environ.get("CARTOPY_DATA_DIR", root / ".cache" / "cartopy"))
        caches = (get_city_data, get_land_geometry, get_ph_provinces)
        with patch.dict(cartopy.config, data_dir=cache, pre_existing_data_dir=cache), \
                patch("cartopy.io.Downloader._urlopen", side_effect=AssertionError("Unexpected download")):
            if geography_readiness():
                self.skipTest("Populate the map cache explicitly before running geography checks")
            for function in caches:
                function.cache_clear()
            session = load_project(root / "examples" / "sample.cycloneaid.json")
            session = replace(session, settings=replace(session.settings, geography_mode="full"))
            figure = None
            try:
                figure = build_figure(RenderRequest.from_session(session, "track"))
                figure.canvas.draw()
                names = {getattr(artist._feature, "name", "")
                         for ax in figure.axes for artist in ax.collections if isinstance(artist, FeatureArtist)}
                self.assertTrue({"land", "coastline", "admin_0_boundary_lines_land"}.issubset(names))
                self.assertFalse(any("WITHOUT BASEMAP" in text.get_text().upper() for text in figure.texts))
            finally:
                if figure is not None:
                    plt.close(figure)
                for function in caches:
                    function.cache_clear()
