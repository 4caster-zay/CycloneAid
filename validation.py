"""Shared validation. Malformed forecasts return diagnostics rather than raising."""
from math import isfinite, radians, sin, cos, sqrt, atan2
import pandas as pd
from cycloneaid.model import INTENSITIES, STORM_TYPES, TIME_ORIGINS, derive_intensity


def haversine_distance(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    a = sin((lat2-lat1)/2)**2 + cos(lat1)*cos(lat2)*sin((lon2-lon1)/2)**2
    a = max(0, min(1, a))
    return 6371 * 2 * atan2(sqrt(a), sqrt(1-a))


class ValidationResult:
    def __init__(self):
        self.hard_errors = []
        self.soft_warnings = []

    @property
    def is_valid(self):
        return not self.hard_errors

    def add_hard_error(self, message):
        self.hard_errors.append(message)

    def add_soft_warning(self, message):
        self.soft_warnings.append(message)

    def has_errors(self):
        return bool(self.hard_errors)

    def has_warnings(self):
        return bool(self.soft_warnings)


def validate_forecast_points(forecast_points, *, regional=False, landmask_qc=False):
    result = ValidationResult()
    if not forecast_points:
        result.add_hard_error("No forecast points provided")
        return result
    times = []
    for i, pt in enumerate(forecast_points, 1):
        prefix = f"Point {i}: "
        for field, lower, upper in (("lat", -90, 90), ("lon", -180, 180), ("wind_kt", 0, float("inf"))):
            try:
                value = float(getattr(pt, field))
                if not isfinite(value) or not lower <= value <= upper:
                    raise ValueError()
            except (TypeError, ValueError, AttributeError):
                result.add_hard_error(prefix + f"Invalid {field}; require finite value in [{lower}, {upper}]")
        try:
            t = pd.Timestamp(pt.time)
            if pd.isna(t) or t.tzinfo is None or t.utcoffset().total_seconds() != 0:
                raise ValueError()
            times.append(t)
        except (TypeError, ValueError, AttributeError):
            times.append(None)
            result.add_hard_error(prefix + "Timestamp must be present and timezone-aware UTC")
        if getattr(pt, "intensity_class", None) not in INTENSITIES:
            result.add_hard_error(prefix + "Invalid intensity class")
        if getattr(pt, "storm_type", None) not in STORM_TYPES:
            result.add_hard_error(prefix + "Invalid storm type")
        if getattr(pt, "time_origin", "provided") not in TIME_ORIGINS:
            result.add_hard_error(prefix + "Invalid timestamp provenance")
        try:
            if pt.intensity_class != derive_intensity(pt.wind_kt):
                if not getattr(pt, "override_reason", "").strip():
                    result.add_hard_error(prefix + "Intensity differs from wind; an explicit override reason is required")
                else:
                    result.add_soft_warning(prefix + f"Intensity override: {pt.override_reason}")
            if getattr(pt, "is_interpolated", False):
                result.add_soft_warning(prefix + f"Estimated data ({getattr(pt, 'time_origin', 'legacy-estimated')})")
            if regional and not (100 <= pt.lon <= 150 and 0 <= pt.lat <= 40):
                result.add_hard_error(prefix + "Track renderer supports 100–150°E and 0–40°N")
        except (TypeError, ValueError, AttributeError):
            pass
    for i, (prev, curr) in enumerate(zip(times, times[1:]), 2):
        if prev is not None and curr is not None and curr <= prev:
            result.add_hard_error(f"Point {i}: Timestamps must be strictly increasing and unique")
    if result.is_valid:
        flagged = [(i, point) for i, point in enumerate(forecast_points, 1) if getattr(point, "landfall", False)]
        if flagged and landmask_qc:
            mask = _land_mask()
            for i, point in flagged:
                if mask is None:
                    result.add_soft_warning(f"Point {i}: Manual landfall flag; optional land-mask QC unavailable")
                elif not mask.is_land(point.lat, point.lon):
                    result.add_soft_warning(f"Point {i}: Manual landfall flag is over water in the optional land mask")
        for i, (prev, curr) in enumerate(zip(forecast_points, forecast_points[1:]), 2):
            hours = (curr.time-prev.time).total_seconds()/3600
            distance = haversine_distance(prev.lon, prev.lat, curr.lon, curr.lat)
            if distance/hours > 50:
                result.add_soft_warning(f"Point {i}: Large position jump ({distance/hours:.1f} km/h)")
    return result


from functools import lru_cache


@lru_cache(maxsize=1)
def _land_mask():
    """Optional point QC only; coastline events use the explicit geography service."""
    try:
        from global_land_mask import globe
        return globe
    except ImportError:
        return None
