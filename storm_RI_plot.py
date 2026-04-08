"""
Rapid Intensification (dV/dt) analysis and plotting for CycloneAid.

Standalone module: intensity change rate time-series with RI threshold highlighting.
Input: DataFrame with time and wind speed (knots or km/h). Supports standalone export
and embedding in prognostic workflows.
"""

from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Default RI threshold: 30 kt / 24h (WMO rapid intensification)
DEFAULT_RI_THRESHOLD_KT_24H = 30.0

# CycloneAid version for metadata
try:
    import storm_tracker_gui
    CYCLONEAID_VERSION = getattr(storm_tracker_gui, "VERSION", "Alpha 0.8.0")
except (ImportError, AttributeError):
    CYCLONEAID_VERSION = "Alpha 0.8.0"


def _wind_to_kmh(wind_series, unit_hint=None):
    """Convert wind to km/h. If unit_hint is 'kt' or 'knots', treat as knots; else assume km/h if values are large."""
    wind = pd.Series(wind_series).astype(float)
    if unit_hint and str(unit_hint).lower() in ("kt", "knots"):
        return wind * 1.852
    if unit_hint and str(unit_hint).lower() in ("kmh", "km/h"):
        return wind
    # Auto-detect: if max wind > 200, likely km/h; else assume knots
    if wind.max() > 200:
        return wind
    return wind * 1.852


def compute_dv_dt(
    df,
    time_col="time",
    wind_col="wind_kt",
    wind_unit="kt",
    window_hours=24,
    interpolated_col=None,
):
    """
    Compute intensity change rate dV/dt (km/h per window).

    Args:
        df: DataFrame with time and wind columns.
        time_col: Name of datetime column.
        wind_col: Name of wind speed column (knots or km/h).
        wind_unit: 'kt' or 'km/h'.
        window_hours: 24 or 6 (km/h per 24h or per 6h).
        interpolated_col: Optional column name (bool) marking interpolated points.

    Returns:
        DataFrame with columns: time, wind_kmh, dv_dt_kmh_per_window, is_interpolated (if interpolated_col given).
    """
    df = df.sort_values(time_col).dropna(subset=[time_col, wind_col])
    if df.empty or len(df) < 2:
        return pd.DataFrame(columns=["time", "wind_kmh", "dv_dt_kmh_per_window", "is_interpolated"])

    times = pd.to_datetime(df[time_col])
    wind_kmh = _wind_to_kmh(df[wind_col], wind_unit)
    is_interp = df[interpolated_col] if interpolated_col and interpolated_col in df.columns else pd.Series(False, index=df.index)

    # Non-uniform intervals: compute per-window change by finding points window_hours apart
    time_vals = times.astype(np.int64) // 10**9  # seconds
    out_times = []
    out_dv = []
    out_wind = []
    out_interp = []

    for i in range(len(df)):
        t0 = time_vals.iloc[i]
        t_target = t0 + window_hours * 3600
        # Find index j such that time[j] >= t_target (first point at or after t0 + window)
        j = np.searchsorted(time_vals.values, t_target)
        if j >= len(df):
            break
        # Use exact time difference for rate
        dt_hours = (times.iloc[j] - times.iloc[i]).total_seconds() / 3600.0
        if dt_hours <= 0:
            continue
        dv = (wind_kmh.iloc[j] - wind_kmh.iloc[i]) / (dt_hours / window_hours)  # normalize to per-window
        out_times.append(times.iloc[i])
        out_dv.append(dv)
        out_wind.append(wind_kmh.iloc[i])
        out_interp.append(is_interp.iloc[i] if hasattr(is_interp, 'iloc') else False)

    result = pd.DataFrame({
        "time": out_times,
        "wind_kmh": out_wind,
        "dv_dt_kmh_per_window": out_dv,
        "is_interpolated": out_interp,
    })
    return result


def plot_ri_timeseries(
    df,
    time_col="time",
    wind_col="wind_kt",
    wind_unit="kt",
    window_hours=24,
    ri_threshold_kt_24h=None,
    interpolated_col=None,
    storm_name="STORM",
    title=None,
):
    """
    Plot dV/dt time-series with Rapid Intensification highlighting.

    Args:
        df: DataFrame with time and wind (and optional is_interpolated).
        time_col: Name of datetime column.
        wind_col: Name of wind column.
        wind_unit: 'kt' or 'km/h'.
        window_hours: 24 or 6.
        ri_threshold_kt_24h: RI threshold in kt/24h (default 30). Converted to km/h/24h for display.
        interpolated_col: Optional column name for interpolated flag.
        storm_name: For title.
        title: Override title.

    Returns:
        matplotlib.figure.Figure
    """
    if ri_threshold_kt_24h is None:
        ri_threshold_kt_24h = DEFAULT_RI_THRESHOLD_KT_24H
    ri_threshold_kmh_per_window = ri_threshold_kt_24h * 1.852 * (window_hours / 24.0)  # km/h per window

    dv_df = compute_dv_dt(df, time_col=time_col, wind_col=wind_col, wind_unit=wind_unit,
                          window_hours=window_hours, interpolated_col=interpolated_col)
    if dv_df.empty:
        raise ValueError("Insufficient data to compute dV/dt (need at least two points with valid time/wind).")

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(12, 6))

    times = pd.to_datetime(dv_df["time"])
    dv = dv_df["dv_dt_kmh_per_window"]
    is_interp = dv_df.get("is_interpolated", pd.Series(False, index=dv_df.index))

    # Segments: non-interpolated solid, interpolated dashed/faded
    seg_start = 0
    for i in range(1, len(dv_df) + 1):
        if i == len(dv_df) or is_interp.iloc[i] != is_interp.iloc[seg_start]:
            t_seg = times.iloc[seg_start:i]
            d_seg = dv.iloc[seg_start:i]
            if is_interp.iloc[seg_start]:
                ax.plot(t_seg, d_seg, "--", color="white", alpha=0.5, linewidth=1.5)
            else:
                ax.plot(t_seg, d_seg, "-", color="white", linewidth=2)
            seg_start = i

    ax.axhline(0, color="gray", linestyle=":", alpha=0.5)
    ax.axhline(ri_threshold_kmh_per_window, color="red", linestyle="--", alpha=0.8, linewidth=1.5, label=f"RI threshold (≥{ri_threshold_kt_24h} kt/24h)")
    ax.axhline(-ri_threshold_kmh_per_window, color="blue", linestyle="--", alpha=0.5, linewidth=1)

    # Fill RI zone
    ax.fill_between(times, ri_threshold_kmh_per_window, dv.clip(lower=ri_threshold_kmh_per_window),
                    where=(dv >= ri_threshold_kmh_per_window), color="red", alpha=0.2)

    # Peak RI event
    peak_idx = dv.idxmax()
    if dv.loc[peak_idx] >= ri_threshold_kmh_per_window:
        ax.plot(times.loc[peak_idx], dv.loc[peak_idx], "o", color="red", markersize=12, markeredgecolor="white", markeredgewidth=2, zorder=5)
        ax.annotate(
            f"Peak RI\n{dv.loc[peak_idx]:.0f} km/h per {window_hours}h",
            (times.loc[peak_idx], dv.loc[peak_idx]),
            xytext=(10, 15), textcoords="offset points", fontsize=9, color="red", fontweight="bold",
            bbox=dict(facecolor="#2f2f2f", edgecolor="red", alpha=0.9),
        )

    ax.set_xlabel("Time (UTC)", fontsize=10)
    ax.set_ylabel(f"Intensity change rate (km/h per {window_hours}h)", fontsize=10)
    ax.set_title(title or f"{storm_name} — Intensity change rate (dV/dt)", fontsize=14)
    ax.legend(loc="upper right", facecolor="#2f2f2f", edgecolor="white", labelcolor="white")
    ax.grid(True, alpha=0.2)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%HZ"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # Metadata footer
    meta = [
        f"CycloneAid {CYCLONEAID_VERSION}",
        f"Generated: {datetime.utcnow():%Y-%m-%d %H%MZ} UTC",
        f"RI threshold: ≥{ri_threshold_kt_24h} kt / 24h",
    ]
    ax.text(0.5, -0.12, "  |  ".join(meta), transform=ax.transAxes,
            fontsize=7, color="gray", ha="center", va="top")

    fig.tight_layout()
    return fig


def plot_ri_from_forecast_points(forecast_points, window_hours=24, ri_threshold_kt_24h=None, storm_name="STORM"):
    """
    Build dV/dt from a list of ForecastPoint-like objects (e.g. from storm_tracker).
    Each must have: .time, .wind_kt, and optionally .is_interpolated.
    """
    rows = []
    for pt in forecast_points:
        rows.append({
            "time": pt.time,
            "wind_kt": pt.wind_kt,
            "is_interpolated": getattr(pt, "is_interpolated", False),
        })
    df = pd.DataFrame(rows)
    return plot_ri_timeseries(
        df,
        time_col="time",
        wind_col="wind_kt",
        wind_unit="kt",
        window_hours=window_hours,
        ri_threshold_kt_24h=ri_threshold_kt_24h,
        interpolated_col="is_interpolated",
        storm_name=storm_name,
    )


if __name__ == "__main__":
    import sys
    import os

    if not os.path.exists("forecast.csv"):
        raise FileNotFoundError("forecast.csv not found")
    df = pd.read_csv("forecast.csv", comment="#")
    # Support both legacy and new column names
    time_col = "time" if "time" in df.columns else "Time (UTC)"
    wind_col = "wind_kt" if "wind_kt" in df.columns else "Wind (kt)"
    if time_col not in df.columns or wind_col not in df.columns:
        raise ValueError("DataFrame must have time and wind columns")
    storm_name = sys.argv[2] if len(sys.argv) > 2 else "STORM"
    ri_threshold = float(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_RI_THRESHOLD_KT_24H
    fig = plot_ri_timeseries(df, time_col=time_col, wind_col=wind_col, storm_name=storm_name, ri_threshold_kt_24h=ri_threshold)
    out_dir = "RI_plots"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{storm_name}_dVdt_{datetime.utcnow():%Y%m%d%H%M}.png")
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved: {out_path}")
