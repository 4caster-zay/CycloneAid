import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

import pandas as pd
from cycloneaid.model import ForecastPoint
from cycloneaid.session import (ForecastRow, ForecastSession, SessionController, SessionSettings,
                                point_to_row, parse_row, save_project, load_project, validate_session)
from cycloneaid.imports import read_tracks, prepare_track, read_forecast
from validation import validate_forecast_points

BASE = pd.Timestamp("2026-01-01T00:00Z")


def point(hour=0, **kwargs):
    return ForecastPoint(BASE + pd.Timedelta(hours=hour), kwargs.pop("lat", 10),
                         kwargs.pop("lon", 125), kwargs.pop("wind_kt", 40), **kwargs)


class CoreTests(unittest.TestCase):
    def test_invalid_forecasts(self):
        for pt in (point(lat=100), point(lat=float("nan")), point(wind_kt=-5),
                   ForecastPoint(None, 10, 125, 40), point(intensity_class="C5"),
                   point(storm_type="invalid"), point(wind_kt=float("inf"))):
            with self.subTest(pt=pt):
                self.assertTrue(validate_forecast_points([pt]).has_errors())
        raw = SimpleNamespace(time=None, lat=100, lon=500, wind_kt=-5)
        self.assertTrue(validate_forecast_points([raw, point(6)]).has_errors())

    def test_subhourly_and_normalization(self):
        self.assertTrue(validate_forecast_points([point(), point(.5)]).is_valid)
        self.assertFalse(validate_forecast_points([point(), point()]).is_valid)
        self.assertEqual(point(lon=350).lon, -10)
        with self.assertRaises(ValueError):
            point(lon=500)

    def test_override_is_explicit(self):
        result = validate_forecast_points([point(intensity_class="C5", override_reason="Agency advisory")])
        self.assertTrue(result.is_valid)
        self.assertTrue(result.has_warnings())

    def test_session_roundtrip_and_undo_revision(self):
        controller = SessionController()
        row = point_to_row(point())
        controller.commit(rows=[row], settings=SessionSettings(storm_name="Test", source="Agency"))
        original = controller.session
        controller.commit(rows=[replace(row, override_reason="changed")])
        revision = controller.session.revision
        self.assertTrue(controller.undo())
        self.assertEqual(controller.session.rows, original.rows)
        self.assertGreater(controller.session.revision, revision)
        self.assertTrue(controller.redo())
        with TemporaryDirectory() as directory:
            path = Path(directory)/"project.cycloneaid"
            save_project(controller.session, path)
            loaded = load_project(path)
            self.assertEqual(loaded.rows, controller.session.rows)
            self.assertEqual(loaded.settings, controller.session.settings)
            self.assertEqual(json.loads(path.read_text())["schema_version"], 1)

    def test_atomic_failure_preserves_project(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)/"project.json"
            save_project(ForecastSession(), path)
            before = path.read_bytes()
            with patch("cycloneaid.session.os.replace", side_effect=OSError("disk unavailable")):
                with self.assertRaises(OSError):
                    save_project(ForecastSession(settings=SessionSettings(storm_name="changed")), path)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_invalid_row_never_yields_partial_forecast(self):
        bad = ForecastRow(("bad", "0", "10", "125", "40", "False", "Tropical", "TS", "False"))
        points, result = validate_session(ForecastSession((point_to_row(point()), bad)))
        self.assertEqual(points, ())
        self.assertIn("Row 2", result.hard_errors[0])

    def test_csv_schemas_and_timezone(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)/"forecast.csv"
            for classification in ("category\n2026-01-01T09:00+09:00,10,125,40,TS\n",
                                   "intensity_class,storm_type\n2026-01-01T09:00+09:00,10,125,40,TS,Tropical\n"):
                path.write_text("time,lat,lon,wind_kt,"+classification)
                points, warnings = read_forecast(path)
                self.assertEqual(points[0].time, BASE)
                self.assertEqual(points[0].intensity_class, "TS")

    def test_gpx_missing_times_and_track_boundaries(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)/"forecast.gpx"
            path.write_text('<gpx><trk><trkseg><trkpt lat="10" lon="125"/></trkseg>'
                            '<trkseg><trkpt lat="11" lon="126"/></trkseg></trk></gpx>')
            tracks = read_tracks(path)
            self.assertEqual(len(tracks), 2)
            with self.assertRaisesRegex(ValueError, "Missing timestamp"):
                prepare_track(tracks[0])
            rows, _ = prepare_track(tracks[0], start=BASE, interval_hours=6)
            self.assertEqual(parse_row(rows[0]).time_origin, "generated")

    def test_kmz_and_timestamped_kml(self):
        document = ('<kml xmlns:gx="http://www.google.com/kml/ext/2.2"><Placemark><gx:Track>'
                    '<when>2026-01-01T00:00Z</when><gx:coord>125 10 0</gx:coord>'
                    '</gx:Track></Placemark><Polygon><coordinates>1,2 3,4 1,2</coordinates></Polygon></kml>')
        with TemporaryDirectory() as directory:
            path = Path(directory)/"forecast.kmz"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("doc.kml", document)
            tracks = read_tracks(path)
            self.assertEqual(len(tracks), 1)
            rows, _ = prepare_track(tracks[0])
            self.assertEqual(parse_row(rows[0]).time, BASE)


class RITests(unittest.TestCase):
    def test_datetime_units_and_exact_interpolated_endpoint(self):
        from storm_RI_plot import compute_dv_dt
        for unit in ("us", "ns"):
            frame = pd.DataFrame({"time": pd.to_datetime([BASE, BASE+pd.Timedelta(hours=30)]).as_unit(unit),
                                  "wind_kt": [40, 85], "estimated": [False, False]})
            result = compute_dv_dt(frame, interpolated_col="estimated")
            self.assertEqual(len(result), 1)
            self.assertAlmostEqual(result.iloc[0].dv_dt_kmh_per_window, 36*1.852)
            self.assertTrue(result.iloc[0].is_interpolated)

    def test_endpoint_provenance_and_no_extrapolation(self):
        from storm_RI_plot import compute_dv_dt
        frame = pd.DataFrame({"time": [BASE, BASE+pd.Timedelta(hours=24)],
                              "wind_kt": [40, 80], "estimated": [False, True]})
        result = compute_dv_dt(frame, interpolated_col="estimated")
        self.assertTrue(result.iloc[0].is_interpolated)
        self.assertTrue(compute_dv_dt(frame, window_hours=48).empty)

    def test_library_plot_and_no_six_hour_ri_label(self):
        import matplotlib.pyplot as plt
        from storm_RI_plot import plot_ri_from_forecast_points
        for hours in (6, 24):
            fig = plot_ri_from_forecast_points([point(), point(24, wind_kt=80)], window_hours=hours)
            self.assertFalse(hours == 6 and any("RI threshold" in text.get_text() for text in fig.findobj() if hasattr(text, "get_text")))
            plt.close(fig)


class OptionalIntegrationTests(unittest.TestCase):
    def test_default_validation_does_not_load_global_landmask(self):
        with patch('validation._land_mask', side_effect=AssertionError('Unexpected 1 GB mask load')):
            self.assertTrue(validate_forecast_points([point(landfall=True)]).is_valid)

    def test_optional_land_mask_present_and_absent(self):
        from unittest.mock import Mock
        for mask in (None, Mock()):
            if mask is not None:
                mask.is_land.return_value=False
            with patch('validation._land_mask',return_value=mask):
                result=validate_forecast_points([point(landfall=True)],landmask_qc=True)
                self.assertTrue(result.is_valid)
                self.assertTrue(result.has_warnings())

    def test_csv_roundtrip_provenance(self):
        from cycloneaid.csvio import export_csv
        original=point(intensity_class='C5',override_reason='Official advisory',
                       time_origin='generated')
        with TemporaryDirectory() as directory:
            path=Path(directory)/'forecast.csv'
            export_csv([original],path)
            restored,_=read_forecast(path)
            self.assertEqual(restored,[original])
