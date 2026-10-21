from dataclasses import replace
from pathlib import Path
import pickle
import random
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

import matplotlib.pyplot as plt
import pandas as pd
from rtree.index import Index
from shapely.geometry import MultiPolygon, box

from cycloneaid.cone import create_optimized_buffers, ERROR_MODERATE, geodesic_disc
from cycloneaid.geography import GEOD, find_nearest_city, detect_landfalls, geography_readiness
from cycloneaid.session import ForecastSession, SessionSettings, point_to_row
from cycloneaid.rendering import RenderCoordinator, RenderRequest, build_figure, export_figure
from test_core import BASE, point


def request(product='track', revision=1):
    settings = SessionSettings(geography_mode='degraded', issue_time=BASE.isoformat())
    session = ForecastSession(tuple(point_to_row(p) for p in (point(), point(24, wind_kt=80))), settings, revision)
    return RenderRequest.from_session(session, product)


class GeographyTests(unittest.TestCase):
    def test_index_matches_exhaustive_at_latitude_and_dateline(self):
        cities = [(127.5, 30, 'Regression city', 1000, False),
                  (-179.5, 15, 'Across dateline', 1000, False)]
        rng = random.Random(42)
        cities.extend((rng.uniform(-180,180), rng.uniform(-85,85), str(i), 1000, False) for i in range(8000))
        idx = Index()
        for i, (lon, lat, *_) in enumerate(cities):
            idx.insert(i, (lon, lat, lon, lat))
        for lon, lat in [(125,30), (179.5,15), (0,89), *[(rng.uniform(-180,180), rng.uniform(-80,80)) for _ in range(30)]]:
            self.assertEqual(find_nearest_city(lon, lat, cities, city_index=idx),
                             find_nearest_city(lon, lat, cities))
        isolated = Index()
        isolated.insert(0, (127.5, 30, 127.5, 30))
        self.assertEqual(find_nearest_city(125,30,cities[:1],city_index=isolated)[0], 'Regression city')
        isolated.close()
        idx.close()

    def test_geodesic_radius_and_short_horizon(self):
        disc = geodesic_disc(125,30,80)
        for lon, lat in list(disc.exterior.coords)[::12]:
            self.assertAlmostEqual(GEOD.inv(125,30,lon,lat)[2], 80000, places=4)
        for hours, expected in ((0,20000),(6,30000)):
            points = [point()]+([point(hours)] if hours else [])
            cone = create_optimized_buffers(points, ERROR_MODERATE, BASE)
            distances = [GEOD.inv(125,10,lon,lat)[2] for lon,lat in cone.exterior.coords]
            self.assertAlmostEqual(max(distances), expected, places=3)

    def test_horizon_cap_and_no_coordinate_clipping(self):
        cone = create_optimized_buffers([point(),point(140)], ERROR_MODERATE, BASE)
        self.assertLess(max(GEOD.inv(125,10,x,y)[2] for x,y in cone.exterior.coords), 400001)
        # The core geometry does not silently clip a valid physical coordinate.
        southern = create_optimized_buffers([point(lat=-10,lon=155)], ERROR_MODERATE, BASE)
        self.assertLess(southern.centroid.y, -9)
        self.assertGreater(southern.centroid.x, 154)

    def test_between_point_landfall_and_manual_flags(self):
        land = box(124.5,9,125.5,11)
        events = detect_landfalls([point(lon=124),point(6,lon=126)], land)
        self.assertEqual(len(events),1)
        self.assertAlmostEqual(events[0].lon,124.5,places=3)
        self.assertTrue(BASE < events[0].time < BASE+pd.Timedelta(hours=6))
        self.assertFalse(point(lon=124).landfall)

    def test_offline_readiness_does_not_download(self):
        with TemporaryDirectory() as directory, patch.dict('cartopy.config', data_dir=Path(directory), pre_existing_data_dir=Path(directory)):
            with patch('cartopy.io.shapereader.natural_earth', side_effect=AssertionError('download')):
                self.assertTrue(geography_readiness())


class RenderingTests(unittest.TestCase):
    def tearDown(self):
        plt.close('all')

    def test_builders_do_not_export_and_copies_draw(self):
        with patch.object(plt.Figure, 'savefig', side_effect=AssertionError('implicit export')):
            for product in ('track','prognostic','ri'):
                figure = build_figure(request(product))
                copy = pickle.loads(pickle.dumps(figure))
                self.assertIsNot(copy,figure)
                copy.canvas.draw()
                plt.close(copy)
                plt.close(figure)
        self.assertEqual(plt.get_fignums(),[])

    def test_single_point_multipart_and_region_guard(self):
        from storm_tracker import plot_storm_track
        geometry = MultiPolygon([box(124.5,9.5,125,10),box(125.1,10.1,125.5,10.5)])
        with patch('storm_tracker.create_optimized_buffers', return_value=geometry):
            fig = plot_storm_track([point()], geography_mode='degraded')
            fig.canvas.draw()
            plt.close(fig)
        with self.assertRaisesRegex(ValueError,'100–150'):
            plot_storm_track([point(lon=155)], geography_mode='degraded')

    def test_atomic_export_failure_and_viewport_restoration(self):
        figure = build_figure(request('ri'))
        before = figure.axes[0].get_xlim()
        with TemporaryDirectory() as directory:
            path = Path(directory)/'chart.png'
            path.write_bytes(b'old')
            with patch.object(figure,'savefig',side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    export_figure(figure,path,view_state=(((0,1),(0,1)),))
            self.assertEqual(path.read_bytes(),b'old')
            self.assertEqual(list(Path(directory).iterdir()),[path])
            self.assertEqual(figure.axes[0].get_xlim(),before)

    @staticmethod
    def wait(coordinator, timeout=50):
        deadline = time.monotonic()+timeout
        while time.monotonic()<deadline:
            result=coordinator.poll()
            if result is not None:
                return result
            time.sleep(.02)
        raise AssertionError('Renderer timeout')

    def test_spawned_worker_cache_invalidation_errors_and_cleanup(self):
        coordinator=RenderCoordinator()
        try:
            coordinator.invalidate(1)
            for product in ('track','prognostic','ri'):
                coordinator.submit(request(product))
                result=self.wait(coordinator)
                self.assertFalse(result.error, result.detail)
                self.assertTrue(result.figure_bytes)
                figure=pickle.loads(result.figure_bytes)
                figure.canvas.draw()
                view_state=tuple((ax.get_xlim(),ax.get_ylim()) for ax in figure.axes)
                plt.close(figure)
            with TemporaryDirectory() as directory:
                path=Path(directory)/'chart.png'
                coordinator.submit(request('ri'),str(path),view_state=view_state)
                result=self.wait(coordinator)
                self.assertTrue(result.cache_hit)
                self.assertTrue(path.read_bytes().startswith(b'\x89PNG'))
            coordinator.submit(request('track'))
            with self.assertRaisesRegex(RuntimeError,'already running'):
                coordinator.submit(request('ri'))
            coordinator.invalidate(2)  # Edits during a job cannot change its captured snapshot.
            self.assertEqual(self.wait(coordinator).revision,1)
            coordinator.submit(request('ri',revision=2))
            self.assertFalse(self.wait(coordinator).cache_hit)
            invalid=replace(request('ri',revision=2),points=(point(),))
            coordinator.submit(invalid)
            self.assertIn('Insufficient coverage',self.wait(coordinator).error)
            self.assertFalse(coordinator.busy)
        finally:
            process=coordinator._process
            coordinator.close()
            self.assertFalse(process.is_alive())

    def test_worker_crash_is_reported_and_can_restart(self):
        coordinator=RenderCoordinator()
        try:
            coordinator.submit(request('ri'))
            coordinator._process.terminate()
            result=self.wait(coordinator)
            self.assertIn('stopped unexpectedly',result.error)
            coordinator.submit(request('ri'))
            self.assertFalse(self.wait(coordinator).error)
        finally:
            coordinator.close()

    def test_imports_do_not_load_gui(self):
        # Check in a fresh process because GUI tests can legitimately import the module.
        import subprocess
        result=subprocess.run([sys.executable,'-c',
            'import storm_tracker, storm_RI_plot, export_preset, sys; '
            'assert "storm_tracker_gui" not in sys.modules; '
            'from cycloneaid.model import ForecastPoint; assert storm_tracker.ForecastPoint is ForecastPoint'],
            capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
