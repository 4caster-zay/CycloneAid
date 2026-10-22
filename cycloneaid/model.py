"""Forecast values and classification rules; no plotting or GUI dependencies."""
from dataclasses import dataclass
import math
import pandas as pd

INTENSITY_THRESHOLDS = (
    (137, "C5"), (113, "C4"), (96, "C3"), (83, "C2"),
    (64, "C1"), (48, "STS"), (34, "TS"), (0, "TD"),
)
INTENSITIES = tuple(label for _, label in reversed(INTENSITY_THRESHOLDS))
STORM_TYPES = ("Tropical", "Subtropical", "Extratropical", "Low")
TIME_ORIGINS = ("provided", "generated", "interpolated", "legacy-estimated")


def derive_intensity(wind):
    return next((label for threshold, label in INTENSITY_THRESHOLDS if float(wind) >= threshold), "TD")


def parse_bool(value):
    if isinstance(value, bool):
        return value
    if str(value).strip().lower() in ("true", "1", "yes"):
        return True
    if str(value).strip().lower() in ("false", "0", "no", "", "none"):
        return False
    raise ValueError(f"Invalid boolean: {value!r}")


def utc_timestamp(value):
    if value is None or str(value).strip() in ("", "NaT"):
        return pd.NaT
    return pd.to_datetime(value, utc=True)


def normalize_longitude(value):
    lon = float(value)
    if not math.isfinite(lon) or not -180 <= lon <= 360:
        raise ValueError("Longitude must be finite and between -180 and 360 degrees")
    return (lon + 180) % 360 - 180


@dataclass(frozen=True, init=False)
class ForecastPoint:
    time: pd.Timestamp
    lat: float
    lon: float
    wind_kt: float
    intensity_class: str
    storm_type: str
    landfall: bool
    is_interpolated: bool
    override_reason: str
    time_origin: str

    def __init__(self, time, lat, lon, wind_kt, intensity_class=None, storm_type=None,
                 landfall=False, is_interpolated=False, category=None,
                 override_reason="", time_origin="provided"):
        wind = float(wind_kt)
        if category is not None:
            if category == "L":
                intensity_class, storm_type = derive_intensity(wind), "Low"
            elif category == "EX":
                intensity_class, storm_type = derive_intensity(wind), "Extratropical"
            elif category in ("SD", "SS"):
                intensity_class, storm_type = derive_intensity(wind), "Subtropical"
            else:
                intensity_class, storm_type = category, "Tropical"
        estimated = parse_bool(is_interpolated)
        if time_origin == "provided" and estimated:
            time_origin = "legacy-estimated"
        values = dict(time=utc_timestamp(time), lat=float(lat), lon=normalize_longitude(lon),
                      wind_kt=wind, intensity_class=intensity_class or derive_intensity(wind),
                      storm_type=storm_type or "Tropical", landfall=parse_bool(landfall),
                      is_interpolated=estimated or time_origin in ("interpolated", "legacy-estimated"),
                      override_reason=str(override_reason or "").strip(), time_origin=time_origin)
        for name, value in values.items():
            object.__setattr__(self, name, value)

    _derive_intensity_class = staticmethod(derive_intensity)

    @property
    def category(self):
        if self.storm_type == "Low":
            return "L"
        if self.storm_type == "Extratropical":
            return "EX"
        if self.storm_type == "Subtropical":
            return "SD" if self.intensity_class == "TD" else "SS"
        return self.intensity_class
