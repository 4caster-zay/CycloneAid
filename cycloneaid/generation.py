"""Validate and generate UTC timestamp rows without changing a session."""
from dataclasses import dataclass
from decimal import Decimal, DecimalException, localcontext
import re

import pandas as pd

from cycloneaid.model import utc_timestamp
from cycloneaid.session import ForecastRow

MAX_GENERATED_ROWS = 1000
_NS_PER_HOUR = Decimal(3_600_000_000_000)
_MAX_DURATION_NS = Decimal(2**63 - 1)
_UTC_START = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?"
    r"(?:Z|[+-]\d{2}:\d{2})?"
)


@dataclass(frozen=True)
class GenerationPreview:
    start: pd.Timestamp
    end: pd.Timestamp
    interval: pd.Timedelta
    count: int


def _hours(value, label):
    try:
        hours = Decimal(str(value).strip())
        if not hours.is_finite() or hours <= 0:
            raise ValueError()
        with localcontext() as context:
            context.prec = max(28, len(hours.as_tuple().digits) + 14)
            nanoseconds = hours * _NS_PER_HOUR
        if nanoseconds > _MAX_DURATION_NS:
            raise ValueError()
        if nanoseconds <= 0 or nanoseconds != nanoseconds.to_integral_value():
            raise ValueError(f"{label} must resolve to a whole number of nanoseconds")
        return int(nanoseconds)
    except (DecimalException, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc):
            raise
        raise ValueError(f"{label} must be a positive finite number of hours within the supported date range") from exc


def _existing_times(rows):
    times = []
    for index, row in enumerate(rows, 1):
        try:
            timestamp = utc_timestamp(row.values[0])
            if pd.isna(timestamp):
                raise ValueError()
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Existing row {index} needs a valid timestamp. Complete or remove it before generating rows.") from exc
        if times and timestamp <= times[-1]:
            raise ValueError(f"Existing row {index} is not later than the previous row. Fix the timestamp order before generating rows.")
        times.append(timestamp)
    return times


def _start_time(value):
    text = str(value).strip()
    try:
        if not _UTC_START.fullmatch(text):
            raise ValueError()
        timestamp = pd.Timestamp(text)
        if timestamp.tzinfo is not None and timestamp.utcoffset().total_seconds() != 0:
            raise ValueError("Start time must use UTC (Z or +00:00); an omitted offset is also interpreted as UTC")
        return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")
    except (TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("Start time must"):
            raise
        raise ValueError("Enter a valid UTC start as YYYY-MM-DD HH:MM[:SS], optionally ending in Z or +00:00") from exc


def suggest_start_time(existing_rows, interval_hours=6):
    """Return the last existing timestamp plus the interval, or None for no rows."""
    times = _existing_times(existing_rows)
    interval = pd.Timedelta(_hours(interval_hours, "Interval"), unit="ns")
    try:
        return times[-1] + interval if times else None
    except (ValueError, OverflowError) as exc:
        raise ValueError("The suggested start is outside the supported date range") from exc


def preview_generation(start, interval_hours=6, horizon_hours=120, *, existing_rows=()):
    """Describe an inclusive, append-only range; no rows or row IDs are created."""
    times = _existing_times(existing_rows)
    interval_ns = _hours(interval_hours, "Interval")
    horizon_ns = _hours(horizon_hours, "Horizon")
    timestamp = _start_time(start)
    steps, remainder = divmod(horizon_ns, interval_ns)
    if remainder:
        raise ValueError("Horizon must be an exact multiple of the interval")
    count = steps + 1
    if count > MAX_GENERATED_ROWS:
        raise ValueError(f"Generate at most {MAX_GENERATED_ROWS:,} rows per batch; increase the interval or shorten the horizon")
    if times and timestamp <= times[-1]:
        raise ValueError("Start must be later than the final existing timestamp; generated rows can only be appended")
    try:
        end = timestamp + pd.Timedelta(horizon_ns, unit="ns")
    except (ValueError, OverflowError) as exc:
        raise ValueError("The generated range is outside the supported date range") from exc
    return GenerationPreview(timestamp, end, pd.Timedelta(interval_ns, unit="ns"), count)


def generate_rows(start, interval_hours=6, horizon_hours=120, *, existing_rows=()):
    """Return new rows only. Coordinates/winds are blank and must be entered."""
    preview = preview_generation(start, interval_hours, horizon_hours, existing_rows=existing_rows)
    return tuple(
        ForecastRow(((preview.start + index * preview.interval).isoformat(), "", "", "", "",
                     "False", "Tropical", "TD", "False"), time_origin="generated")
        for index in range(preview.count)
    )
