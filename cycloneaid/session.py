"""Immutable editable sessions, history, and atomic project/recovery persistence."""
from dataclasses import asdict, dataclass, field, replace
from functools import lru_cache
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4

import pandas as pd
from cycloneaid.metadata import __version__
from cycloneaid.model import ForecastPoint, utc_timestamp
from validation import ValidationResult, validate_forecast_points

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ForecastRow:
    values: tuple[str, ...]
    row_id: str = field(default_factory=lambda: uuid4().hex)
    override_reason: str = ""
    time_origin: str = "provided"

    def __post_init__(self):
        if len(self.values) != 9:
            raise ValueError("A forecast row requires nine table values")
        object.__setattr__(self, "values", tuple(str(v) for v in self.values))


@dataclass(frozen=True)
class SessionSettings:
    storm_name: str = "CycloneAid"
    confidence: str = "Moderate"
    preset: str = "Forecaster"
    issue_time: str = ""
    source: str = "Unknown"
    wind_averaging_period: str = "Unknown"
    geography_mode: str = "full"
    import_notes: str = ""
    landmask_qc: bool = False


@dataclass(frozen=True)
class ForecastSession:
    rows: tuple[ForecastRow, ...] = ()
    settings: SessionSettings = field(default_factory=SessionSettings)
    revision: int = 0

    def __post_init__(self):
        object.__setattr__(self, "rows", tuple(self.rows))


@lru_cache(maxsize=10000)
def parse_row(row):
    v = row.values
    return ForecastPoint(v[0], v[2], v[3], v[4], landfall=v[5], storm_type=v[6],
                         intensity_class=v[7], is_interpolated=v[8],
                         override_reason=row.override_reason, time_origin=row.time_origin)


def validate_session(session, *, regional=False):
    result = ValidationResult()
    points = []
    for i, row in enumerate(session.rows, 1):
        try:
            points.append(parse_row(row))
        except (ValueError, TypeError, OverflowError) as exc:
            result.add_hard_error(f"Row {i}: {exc}")
    # Never render a partial forecast after a failed row conversion.
    if result.has_errors():
        return (), result
    checked = validate_forecast_points(points, regional=regional, landmask_qc=session.settings.landmask_qc)
    result.hard_errors.extend(checked.hard_errors)
    result.soft_warnings.extend(checked.soft_warnings)
    settings = session.settings
    if settings.confidence not in ("High", "Moderate", "Low"):
        result.add_hard_error("Invalid confidence setting")
    if settings.preset not in ("Forecaster", "Media"):
        result.add_hard_error("Invalid export preset")
    if settings.geography_mode not in ("full", "degraded"):
        result.add_hard_error("Invalid geography mode")
    try:
        issue = utc_timestamp(settings.issue_time) if settings.issue_time else (points[0].time if points else pd.NaT)
        if pd.isna(issue) or (points and issue > points[0].time):
            raise ValueError()
    except (TypeError, ValueError):
        result.add_hard_error("Issue time must be valid UTC and no later than the first forecast point")
    if settings.source == "Unknown" or settings.wind_averaging_period == "Unknown":
        result.add_soft_warning("Source agency or wind averaging period is unknown; no convention conversion is applied")
    return tuple(points) if result.is_valid else (), result


class SessionController:
    def __init__(self, session=None):
        self.session = session or ForecastSession()
        self._revision = self.session.revision
        self._undo = []
        self._redo = []
        self.saved_state = self._content(self.session)

    @staticmethod
    def _content(session):
        return session.rows, session.settings

    @property
    def dirty(self):
        return self._content(self.session) != self.saved_state

    def mark_saved(self):
        self.saved_state = self._content(self.session)

    def commit(self, *, rows=None, settings=None, infer_issue_time=True):
        rows = tuple(rows) if rows is not None else self.session.rows
        settings = settings or self.session.settings
        if infer_issue_time and not settings.issue_time:
            for row in rows:
                try:
                    timestamp = utc_timestamp(row.values[0])
                    if not pd.isna(timestamp):
                        settings = replace(settings, issue_time=timestamp.isoformat())
                        break
                except (TypeError, ValueError):
                    continue
        if (rows, settings) == self._content(self.session):
            return False
        self._undo.append(self.session)
        self._undo = self._undo[-100:]
        self._redo.clear()
        self._install(ForecastSession(rows, settings))
        return True

    def _install(self, session):
        self._revision += 1
        self.session = replace(session, revision=self._revision)

    def undo(self):
        if not self._undo:
            return False
        self._redo.append(self.session)
        self._install(self._undo.pop())
        return True

    def redo(self):
        if not self._redo:
            return False
        self._undo.append(self.session)
        self._install(self._redo.pop())
        return True


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_project(session, path):
    atomic_json(path, {"schema_version": SCHEMA_VERSION, "app_version": __version__,
                       "session": asdict(session)})


def load_project(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported project schema version")
    raw = data["session"]
    rows = tuple(ForecastRow(**row) for row in raw["rows"])
    if len({row.row_id for row in rows}) != len(rows) or any(not row.row_id for row in rows):
        raise ValueError("Project row IDs must be nonempty and unique")
    return ForecastSession(rows, SessionSettings(**raw["settings"]))


def recovery_path():
    root = os.environ.get("LOCALAPPDATA") if os.name == "nt" else os.environ.get("XDG_STATE_HOME")
    return Path(root or Path.home()/".local"/"state")/"cycloneaid"/"recovery.json"


def point_to_row(point):
    return ForecastRow((point.time.isoformat(), "0", str(point.lat), str(point.lon),
                        f"{point.wind_kt:g}", str(point.landfall), point.storm_type,
                        point.intensity_class, str(point.is_interpolated)),
                       override_reason=point.override_reason, time_origin=point.time_origin)
