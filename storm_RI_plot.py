"""Exact-window wind change analysis; RI labeling applies only to 24-hour windows."""
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from cycloneaid.metadata import __version__ as CYCLONEAID_VERSION
from cycloneaid.model import parse_bool

DEFAULT_RI_THRESHOLD_KT_24H = 30.0  # NHC glossary: gain of at least 30 kt in 24 hours.


def _wind_to_kmh(wind_series, unit_hint=None):
    wind = pd.Series(wind_series).astype(float)
    if not np.isfinite(wind).all() or (wind < 0).any():
        raise ValueError("Wind values must be finite and nonnegative")
    if str(unit_hint).lower() in ("kt", "knots"):
        return wind * 1.852
    if str(unit_hint).lower() in ("kmh", "km/h"):
        return wind
    raise ValueError("Specify wind units explicitly: 'kt' or 'km/h'")


def compute_dv_dt(df, time_col="time", wind_col="wind_kt", wind_unit="kt",
                  window_hours=24, interpolated_col=None):
    """Wind difference at exactly start + window, with bracketed interpolation only.

    Existing result columns remain available. window_end and endpoint_wind_kmh
    make the endpoint calculation inspectable. Estimated provenance covers the
    start, both endpoint contributors, and estimated data within the window.
    """
    if not np.isfinite(window_hours) or window_hours <= 0:
        raise ValueError("Window must be finite and positive")
    columns = ["time", "wind_kmh", "dv_dt_kmh_per_window", "is_interpolated",
               "window_end", "endpoint_wind_kmh"]
    if df.empty:
        return pd.DataFrame(columns=columns)
    times = pd.to_datetime(df[time_col], utc=True)
    winds = _wind_to_kmh(df[wind_col], wind_unit).to_numpy()
    if times.isna().any() or not times.is_monotonic_increasing or times.duplicated().any():
        raise ValueError("Times must be present, strictly increasing and unique")
    if len(df) < 2:
        return pd.DataFrame(columns=columns)
    seconds = np.array([(t-times.iloc[0]).total_seconds() for t in times])
    flags = (df[interpolated_col].map(parse_bool).to_numpy(dtype=bool)
             if interpolated_col and interpolated_col in df else np.zeros(len(df), dtype=bool))
    rows = []
    for i, start in enumerate(seconds):
        target = start + window_hours*3600
        j = int(np.searchsorted(seconds, target))
        if j >= len(seconds):
            break
        exact = seconds[j] == target
        endpoint = winds[j] if exact else np.interp(target, seconds[j-1:j+1], winds[j-1:j+1])
        rows.append(dict(time=times.iloc[i], wind_kmh=winds[i],
                         dv_dt_kmh_per_window=endpoint-winds[i],
                         is_interpolated=bool(not exact or flags[i:j+1].any()),
                         window_end=times.iloc[i]+pd.Timedelta(hours=window_hours),
                         endpoint_wind_kmh=endpoint))
    return pd.DataFrame(rows, columns=columns)


def plot_ri_timeseries(df, time_col="time", wind_col="wind_kt", wind_unit="kt",
                      window_hours=24, ri_threshold_kt_24h=None, interpolated_col=None,
                      storm_name="STORM", title=None):
    threshold = DEFAULT_RI_THRESHOLD_KT_24H if ri_threshold_kt_24h is None else float(ri_threshold_kt_24h)
    if not np.isfinite(threshold) or threshold <= 0:
        raise ValueError("RI threshold must be finite and positive")
    values = compute_dv_dt(df, time_col, wind_col, wind_unit, window_hours, interpolated_col)
    if values.empty:
        raise ValueError(f"Insufficient coverage for an exact {window_hours}-hour wind-change window")
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(12, 6))
    times, change = values.time, values.dv_dt_kmh_per_window
    estimated = values.is_interpolated
    for i in range(len(values)-1):
        uncertain = estimated.iloc[i] or estimated.iloc[i+1]
        ax.plot(times.iloc[i:i+2], change.iloc[i:i+2], "--" if uncertain else "-",
                color="white", alpha=.5 if uncertain else 1, linewidth=2)
    ax.plot(times, change, "o", color="white", markersize=4)
    ax.axhline(0, color="gray", linestyle=":", alpha=.5)
    if window_hours == 24:
        limit = threshold*1.852
        ax.axhline(limit, color="red", linestyle="--", label=f"RI threshold (≥{threshold:g} kt/24h)")
        ax.fill_between(times, limit, change.clip(lower=limit), where=change >= limit,
                        color="red", alpha=.2)
        peak = change.idxmax()
        if change.loc[peak] >= limit:
            ax.annotate(f"Peak forecast RI\n{change.loc[peak]/1.852:g} kt / 24h",
                        (times.loc[peak], change.loc[peak]), xytext=(10, -20), va="top",
                        textcoords="offset points", color="red",
                        bbox=dict(facecolor="black", edgecolor="none", alpha=.8))
        ax.legend(loc="upper right")
    ax.set(xlabel="Window start (UTC)", ylabel=f"Wind change (km/h over {window_hours}h)",
           title=title or f"{storm_name} — Forecast wind change")
    ax.grid(True, alpha=.2)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%MZ"))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    meta = [f"CycloneAid {CYCLONEAID_VERSION}",
            f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%MZ}"]
    if estimated.any():
        meta.append("Dashed: estimated contributors or interpolated endpoint; no extrapolation")
    fig.text(.5, .08, " | ".join(meta), fontsize=7, ha="center", wrap=True)
    fig.subplots_adjust(bottom=.28, top=.9, left=.08, right=.98)
    return fig


def plot_ri_from_forecast_points(forecast_points, window_hours=24, ri_threshold_kt_24h=None, storm_name="STORM"):
    from validation import validate_forecast_points
    result = validate_forecast_points(forecast_points)
    if result.has_errors():
        raise ValueError("\n".join(result.hard_errors))
    frame = pd.DataFrame([dict(time=p.time, wind_kt=p.wind_kt,
                               is_interpolated=p.is_interpolated) for p in forecast_points])
    return plot_ri_timeseries(frame, window_hours=window_hours, ri_threshold_kt_24h=ri_threshold_kt_24h,
                              interpolated_col="is_interpolated", storm_name=storm_name)


if __name__ == "__main__":
    from cycloneaid.cli import ri_main
    raise SystemExit(ri_main())
