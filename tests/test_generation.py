from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from cycloneaid.generation import MAX_GENERATED_ROWS, generate_rows, preview_generation, suggest_start_time
from cycloneaid.model import ForecastPoint
from cycloneaid.session import (ForecastSession, SessionController, SessionSettings,
                                load_project, parse_row, save_project, validate_session)


START = "2026-01-01 00:00"


class GenerationTests(unittest.TestCase):
    def test_inclusive_default_range_has_preview_and_timestamp_only_rows(self):
        preview = preview_generation(START)
        self.assertEqual(preview.count, 21)
        self.assertEqual(preview.start, pd.Timestamp("2026-01-01T00:00Z"))
        self.assertEqual(preview.end, pd.Timestamp("2026-01-06T00:00Z"))
        rows = generate_rows(START)
        self.assertEqual(len(rows), preview.count)
        self.assertEqual(len({row.row_id for row in rows}), len(rows))
        self.assertEqual(rows[0].values[0], preview.start.isoformat())
        self.assertEqual(rows[-1].values[0], preview.end.isoformat())
        for row in rows:
            self.assertEqual(row.values[1:5], ("", "", "", ""))
            self.assertEqual(row.values[5:], ("False", "Tropical", "TD", "False"))
            self.assertEqual(row.time_origin, "generated")

    def test_fractional_intervals_use_exact_decimal_divisibility(self):
        for interval, horizon, count in ((".5", "1.5", 4), (".1", ".3", 4),
                                         (".000000000025", ".000000000075", 4)):
            with self.subTest(interval=interval):
                preview = preview_generation(START, interval, horizon)
                self.assertEqual(preview.count, count)
                rows = generate_rows(START, interval, horizon)
                self.assertEqual(pd.Timestamp(rows[-1].values[0]), preview.end)
        with self.assertRaisesRegex(ValueError, "exact multiple"):
            preview_generation(START, ".3", "1")
        with self.assertRaisesRegex(ValueError, "nanoseconds"):
            preview_generation(START, ".0000000000000001", "1")
        with self.assertRaisesRegex(ValueError, "nanoseconds"):
            preview_generation(START, "0.10000000000000000000000000001", "1")

    def test_explicit_utc_start_and_invalid_dates(self):
        for start in (START, "2026-01-01T00:00Z", "2026-01-01T00:00:00+00:00"):
            with self.subTest(start=start):
                self.assertEqual(preview_generation(start).start, pd.Timestamp("2026-01-01T00:00Z"))
        for start in ("", "NaT", "now", "today", "2026-01-01", "2026-02-30 00:00", "2026-01-01 24:00"):
            with self.subTest(start=start), self.assertRaisesRegex(ValueError, "valid UTC start"):
                preview_generation(start)
        with self.assertRaisesRegex(ValueError, "must use UTC"):
            preview_generation("2026-01-01T08:00+08:00")
        with self.assertRaisesRegex(ValueError, "supported date range"):
            preview_generation("2262-04-11T23:47:16Z")

    def test_invalid_durations_and_resource_bound(self):
        for value in ("", "bad", "0", "-1", "NaN", "Infinity", "-Infinity", "1e99", "1e999999999", "1e-999999999"):
            for label, arguments in (("Interval", (value, "120")), ("Horizon", ("6", value))):
                with self.subTest(value=value, label=label), self.assertRaisesRegex(ValueError, label):
                    preview_generation(START, *arguments)
        self.assertEqual(preview_generation(START, 1, MAX_GENERATED_ROWS - 1).count, MAX_GENERATED_ROWS)
        with self.assertRaisesRegex(ValueError, "at most 1,000"):
            preview_generation(START, 1, MAX_GENERATED_ROWS)

    def test_append_validates_only_existing_timestamps_and_preserves_rows(self):
        existing = generate_rows(START, 6, 12)
        before = tuple(existing)
        self.assertEqual(suggest_start_time(existing), pd.Timestamp("2026-01-01T18:00Z"))
        self.assertEqual(suggest_start_time(existing, ".5"), pd.Timestamp("2026-01-01T12:30Z"))
        new = generate_rows("2026-01-01 18:00", 6, 12, existing_rows=existing)
        self.assertEqual(existing, before)
        self.assertFalse({row.row_id for row in existing} & {row.row_id for row in new})
        for start in (START, "2026-01-01 12:00"):
            with self.subTest(start=start), self.assertRaisesRegex(ValueError, "later than the final"):
                generate_rows(start, existing_rows=existing)
        self.assertIsNone(suggest_start_time(()))

    def test_invalid_existing_timestamps_are_actionable(self):
        valid = generate_rows(START, 6, 6)
        for rows, message in (((replace(valid[0], values=("", *valid[0].values[1:])),), "Existing row 1"),
                              ((replace(valid[0], values=("bad", *valid[0].values[1:])),), "Existing row 1"),
                              ((valid[0], valid[0]), "Existing row 2"),
                              ((valid[1], valid[0]), "timestamp order")):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                preview_generation("2026-01-02 00:00", existing_rows=rows)

    def test_one_commit_preserves_settings_and_roundtrips_blank_issue_time(self):
        settings = SessionSettings(storm_name="Test storm", source="Agency", preset="Media")
        original_rows = generate_rows(START, 6, 6)
        original = ForecastSession(original_rows, settings)
        controller = SessionController(original)
        generated = generate_rows("2026-01-01 12:00", 6, 12, existing_rows=original_rows)
        self.assertTrue(controller.commit(rows=(*original_rows, *generated), infer_issue_time=False))
        self.assertEqual(controller.session.settings, settings)
        self.assertEqual(controller.session.rows[:len(original_rows)], original_rows)
        self.assertTrue(controller.dirty)
        applied = controller.session
        self.assertTrue(controller.undo())
        self.assertEqual(controller.session.rows, original.rows)
        self.assertEqual(controller.session.settings, original.settings)
        self.assertFalse(controller.dirty)
        self.assertFalse(controller.undo())
        self.assertTrue(controller.redo())
        self.assertEqual(controller.session.rows, applied.rows)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "generated.json"
            save_project(controller.session, path)
            restored = load_project(path)
            self.assertEqual(restored.rows, applied.rows)
            self.assertEqual(restored.settings, settings)
            self.assertEqual(json.loads(path.read_text())["schema_version"], 1)

    def test_generated_times_do_not_mark_entered_forecast_values_as_interpolated(self):
        rows = generate_rows(START, 6, 6)
        self.assertFalse(validate_session(ForecastSession(rows))[1].is_valid)
        completed = tuple(replace(row, values=(row.values[0], "", "10", "125", "40",
                                               "False", "Tropical", "TS", "False")) for row in rows)
        points, checked = validate_session(ForecastSession(completed))
        self.assertTrue(checked.is_valid)
        self.assertTrue(all(point.time_origin == "generated" for point in points))
        self.assertTrue(all(not point.is_interpolated for point in points))
        self.assertFalse(parse_row(completed[0]).is_interpolated)
        self.assertTrue(ForecastPoint(START, 10, 125, 40, time_origin="generated", is_interpolated=True).is_interpolated)
        for origin in ("interpolated", "legacy-estimated"):
            self.assertTrue(ForecastPoint(START, 10, 125, 40, time_origin=origin).is_interpolated)

    def test_import_generated_timestamps_keep_forecast_values_uninterpolated(self):
        from cycloneaid.imports import prepare_track, read_tracks
        with TemporaryDirectory() as directory:
            path = Path(directory) / "untimed.gpx"
            path.write_text('<gpx><trk><trkseg><trkpt lat="10" lon="125"/>'
                            '<trkpt lat="11" lon="126"/></trkseg></trk></gpx>')
            rows, _ = prepare_track(read_tracks(path)[0], start=START, interval_hours=6)
            self.assertTrue(all(parse_row(row).time_origin == "generated" for row in rows))
            self.assertTrue(all(not parse_row(row).is_interpolated for row in rows))


if __name__ == "__main__":
    unittest.main()
