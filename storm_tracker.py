import pandas as pd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from shapely.geometry import Point
from matplotlib.patches import Patch
from datetime import datetime, timezone, timedelta

# Export preset: optional; if not provided, Forecaster preset is used
try:
    from export_preset import (
        RenderContext,
        LAYER_TRACK_LINE,
        LAYER_FORECAST_CONE,
        LAYER_TRACK_POINTS,
        LAYER_CITY_LABELS,
        LAYER_LANDFALL_MARKERS,
        LAYER_LEAD_TIME_ANNOTATIONS,
        LAYER_VALIDATION_WARNINGS,
        LAYER_METADATA_FOOTER,
        FORECASTER_PRESET,
    )
except ImportError:
    RenderContext = None
    LAYER_TRACK_LINE = LAYER_FORECAST_CONE = LAYER_TRACK_POINTS = None
    LAYER_CITY_LABELS = LAYER_LANDFALL_MARKERS = LAYER_LEAD_TIME_ANNOTATIONS = None
    LAYER_VALIDATION_WARNINGS = LAYER_METADATA_FOOTER = FORECASTER_PRESET = None

from cycloneaid.cone import ERROR_TABLES as error_tables
error_high = error_tables['High']
error_low = error_tables['Low']

# ─── Confidence Colors & Alpha ───
confidence_colors = {
    'Low':      '#0000FF',  # Brighter blue
    'Moderate': '#00FFFF',  # Cyan
    'High':     '#FFFF00',  # Yellow
}
fill_alpha = 0.25  # Slightly increased for better visibility

# ─── Category Colors ───
category_colors = {
    'L':   '#989898',  # Gray for Low pressure systems
    'TD':  '#5ebaff',  # Light blue
    'TS':  '#00faf4',  # Cyan
    'STS': '#00ef00',  # Green
    'C1':  '#ffffcc',  # Light yellow
    'C2':  '#ffe775',  # Yellow
    'C3':  '#ffc140',  # Orange
    'C4':  '#ff8f20',  # Dark orange
    'C5':  '#ff6060',  # Red
    'EX':  '#c07898',  # Mauve/purple for post-tropical systems
    'SD':  '#2d5d7e',  # Darker blue for subtropical depression
    'SS':  '#007d7a',  # Darker cyan for subtropical storm
}

# Public aliases preserve existing imports while sharing one domain/geography service.
from cycloneaid.model import ForecastPoint as ForecastPoint, utc_timestamp
from cycloneaid.metadata import __version__ as VERSION, CONE_METHOD
from cycloneaid.cone import create_optimized_buffers
from cycloneaid.geography import (
    get_ph_provinces as _get_ph_provinces,
    find_nearest_city, cities_in_cone,
)


def read_gpx_to_dataframe(gpx_path, **timing):
    from cycloneaid.imports import read_forecast
    from dataclasses import asdict
    points, _ = read_forecast(gpx_path, **timing)
    return pd.DataFrame([asdict(point) for point in points])


def optimize_city_processing(cities_data, cone):
    return cities_in_cone(cone)


def plot_storm_track(forecast_points, storm_name="STORM", issue_time=None, forecaster_confidence='Moderate', render_context=None, *, geography_mode='full', landfall_events=()):
    """
    Plot the storm track with uncertainty cone and forecast points.
    Args:
        forecast_points (list of ForecastPoint): The forecast points to plot.
        storm_name (str): Name of the storm.
        issue_time (datetime): Issue time of the forecast.
        forecaster_confidence (str): 'High', 'Moderate', or 'Low' - heuristic scaling of cone width.
        render_context (RenderContext|None): If provided, controls layers and styling. If None, Forecaster preset is used.
    Returns:
        matplotlib.figure.Figure: The generated matplotlib figure.
    """
    if not forecast_points:
        raise ValueError("No forecast points provided")
        
    if not issue_time:
        issue_time = forecast_points[0].time
    if forecaster_confidence not in error_tables:
        raise ValueError("Choose forecaster confidence from: Low, Moderate, High")
    
    from validation import validate_forecast_points
    validation_result = validate_forecast_points(forecast_points, regional=True)
    
    if validation_result.has_errors():
        error_msg = "Validation errors prevent rendering:\n" + "\n".join(validation_result.hard_errors)
        raise ValueError(error_msg)

    issue_time = utc_timestamp(issue_time)
    if pd.isna(issue_time) or issue_time > forecast_points[0].time:
        raise ValueError("Issue time must be valid and no later than the first point")
    if (forecast_points[-1].time-issue_time).total_seconds()/3600 > 120:
        validation_result.add_soft_warning("Heuristic envelope ends at T+120h; later track points have no envelope")
    has_interpolated = any(pt.is_interpolated for pt in forecast_points)
    valid_until = forecast_points[-1].time if forecast_points else None

    # Build render context from preset if not provided
    if render_context is None and FORECASTER_PRESET is not None:
        storm_data = {
            "forecast_points": forecast_points,
            "issue_time": issue_time,
            "valid_until": valid_until,
            "has_interpolated": has_interpolated,
            "forecaster_confidence": forecaster_confidence,
            "validation_result": validation_result,
            "validation_warning_count": len(validation_result.soft_warnings),
        }
        render_context = FORECASTER_PRESET.build_render_context(storm_data)
    elif render_context is None:
        # Fallback when export_preset not available: minimal context, all layers on
        render_context = RenderContext() if RenderContext else None

    # Dark-mode
    plt.style.use('dark_background')
    fig = plt.figure(figsize=(12,9))
    ax = plt.axes(projection=ccrs.PlateCarree())

    track_times = [(pt.time - issue_time).total_seconds()/3600 for pt in forecast_points]
    table = error_tables[forecaster_confidence]
    cone = create_optimized_buffers(forecast_points, table, issue_time, track_times)
    
    
    # Calculate map extent with padding and 4:3 aspect ratio
    cone_bounds = cone.bounds
    bounds = (min(cone_bounds[0], *(p.lon for p in forecast_points)),
              min(cone_bounds[1], *(p.lat for p in forecast_points)),
              max(cone_bounds[2], *(p.lon for p in forecast_points)),
              max(cone_bounds[3], *(p.lat for p in forecast_points)))
    
    # Add padding (20% of the range)
    lon_range = bounds[2] - bounds[0]
    lat_range = bounds[3] - bounds[1]
    padding_lon = lon_range * 0.2
    padding_lat = lat_range * 0.2
    
    # Initial extent
    min_lon = bounds[0] - padding_lon
    max_lon = bounds[2] + padding_lon
    min_lat = bounds[1] - padding_lat
    max_lat = bounds[3] + padding_lat
    
    # Adjust to maintain 4:3 aspect ratio
    current_width = max_lon - min_lon
    current_height = max_lat - min_lat
    target_ratio = 4/3
    
    current_ratio = current_width / current_height
    if current_ratio < target_ratio:
        # Too tall, need to add width
        extra_width = (target_ratio * current_height - current_width) / 2
        min_lon -= extra_width
        max_lon += extra_width
    else:
        # Too wide, need to add height
        extra_height = (current_width / target_ratio - current_height) / 2
        min_lat -= extra_height
        max_lat += extra_height
    
    # Set the map extent
    ax.set_extent([min_lon, max_lon, min_lat, max_lat], crs=ccrs.PlateCarree())

    if geography_mode == 'full':
        ax.add_feature(cfeature.LAND.with_scale('10m'), facecolor='#2f2f2f')
        ax.add_feature(cfeature.BORDERS.with_scale('50m'), edgecolor='white', linestyle=':')
        ax.coastlines(resolution='10m', color='white')
        for geom in _get_ph_provinces():
            ax.add_geometries([geom], crs=ccrs.PlateCarree(), facecolor='none',
                              edgecolor='#FFD700', linewidth=.8, alpha=.3, zorder=2)
    ax.set_facecolor('#0d0d2b')
    gl = ax.gridlines(draw_labels=True, alpha=.3, linestyle='--')
    gl.top_labels = False
    gl.right_labels = False
    cities_data = optimize_city_processing(None, cone) if geography_mode == 'full' else []

    # Layer: city_labels
    show_cities = render_context is None or (LAYER_CITY_LABELS is not None and render_context.is_layer_visible(LAYER_CITY_LABELS))
    major_only = render_context is not None and render_context.major_cities_only()
    cities_added = set()
    if show_cities:
        for lon, lat, name, population, is_capital in cities_data:
            if Point(lon, lat).within(cone):
                if name not in cities_added:
                    if major_only and population <= 250000:
                        continue
                    if population > 250000:
                        marker_style = '^' if is_capital else 'o'
                        ax.plot(lon, lat, marker_style, color='#FFD700', markersize=4 if is_capital else 3, zorder=4)
                        ax.text(lon + 0.1, lat, f"{name}{'★' if is_capital else ''}", 
                               fontsize=6, color='#FFD700',
                               transform=ccrs.PlateCarree(), zorder=4,
                               bbox=dict(facecolor='#2f2f2f', edgecolor='none', alpha=0.6))
                        cities_added.add(name)
                    elif not major_only and population > 100000:
                        marker_style = '^' if is_capital else 'o'
                        ax.plot(lon, lat, marker_style, color='#C0C0C0', markersize=3.5 if is_capital else 2.5, zorder=3)
                        ax.text(lon + 0.1, lat, f"{name}{'★' if is_capital else ''}", 
                               fontsize=5, color='#C0C0C0',
                               transform=ccrs.PlateCarree(), zorder=3,
                               bbox=dict(facecolor='#2f2f2f', edgecolor='none', alpha=0.5))
                        cities_added.add(name)
                    elif not major_only and (population > 10000 or is_capital):
                        marker_style = '^' if is_capital else 'o'
                        color = '#4169E1' if is_capital else '#808080'
                        ax.plot(lon, lat, marker_style, color=color, markersize=3 if is_capital else 2, zorder=2)
                        ax.text(lon + 0.1, lat, f"{name}{'★' if is_capital else ''}", 
                               fontsize=4, color=color,
                               transform=ccrs.PlateCarree(), zorder=2,
                               bbox=dict(facecolor='#2f2f2f', edgecolor='none', alpha=0.4))
                        cities_added.add(name)

    # Layer: track_line
    def get_marker_style(storm_type):
        styles = {'Tropical': 'o', 'Subtropical': 's', 'Extratropical': '^', 'Low': 'D'}
        return styles.get(storm_type, 'o')

    show_track_line = render_context is None or (LAYER_TRACK_LINE is not None and render_context.is_layer_visible(LAYER_TRACK_LINE))
    line_opacity = render_context.track_line_opacity if render_context else 1.0
    interp_opacity = render_context.interpolated_line_opacity if render_context else 0.4

    if show_track_line:
        lons = [pt.lon for pt in forecast_points]
        lats = [pt.lat for pt in forecast_points]
        for start, end in zip(forecast_points, forecast_points[1:]):
            estimated = start.is_interpolated or end.is_interpolated
            ax.plot([start.lon, end.lon], [start.lat, end.lat], '--' if estimated else '-',
                    color='white', linewidth=2, zorder=6,
                    alpha=interp_opacity if estimated else line_opacity)

    # Layer: track_points
    show_track_points = render_context is None or (LAYER_TRACK_POINTS is not None and render_context.is_layer_visible(LAYER_TRACK_POINTS))
    pt_interp_opacity = render_context.track_point_opacity_interpolated if render_context else 0.5
    use_simplified_labels = render_context.use_simplified_labels() if render_context else False

    if show_track_points:
        for i, pt in enumerate(forecast_points):
            marker_color = category_colors.get(pt.intensity_class, 'white')
            marker_style = get_marker_style(pt.storm_type)
            alpha = pt_interp_opacity if pt.is_interpolated else 1.0
            ax.plot(pt.lon, pt.lat, marker_style, color=marker_color,
                    markeredgecolor='white', markeredgewidth=1, markersize=6, zorder=7, alpha=alpha)
            if pt.intensity_class in ['C1', 'C2', 'C3', 'C4', 'C5']:
                label = pt.intensity_class if use_simplified_labels else (pt.intensity_class + (f" ({pt.storm_type[:4]})" if pt.storm_type != 'Tropical' else ""))
                ax.text(pt.lon, pt.lat + 0.2, label, color=marker_color, fontsize=6, ha='center', va='bottom', weight='bold', zorder=8, alpha=alpha)

    # Layer: forecast_cone
    show_cone = render_context is None or (LAYER_FORECAST_CONE is not None and render_context.is_layer_visible(LAYER_FORECAST_CONE))
    cone_colors = {'High': ('#FF69B4', 0.15), 'Moderate': ('#FF4500', 0.12), 'Low': ('#FF0000', 0.1)}
    cone_opacity_mult = render_context.cone_opacity if render_context else 1.0
    if show_cone:
        cone_color, cone_alpha = cone_colors[forecaster_confidence]
        ax.add_geometries([cone], crs=ccrs.PlateCarree(), facecolor=cone_color,
                          edgecolor=cone_color, alpha=cone_alpha*cone_opacity_mult,
                          linewidth=1.5, zorder=5)

    # Layer: lead_time_annotations
    show_lead_time = (render_context is None or (LAYER_LEAD_TIME_ANNOTATIONS is not None and render_context.is_layer_visible(LAYER_LEAD_TIME_ANNOTATIONS))) and (render_context is None or getattr(render_context, 'show_lead_time_annotations', True))
    if show_lead_time:
        annotated_points = set()
        for i, leadtime in enumerate((0, 12, 24, 36, 48, 72, 96, 120)):
            target_time = issue_time + timedelta(hours=leadtime)
            if target_time < forecast_points[0].time or target_time > forecast_points[-1].time:
                continue
            point = min(forecast_points, key=lambda p: abs((p.time-target_time).total_seconds()))
            actual = (point.time-issue_time).total_seconds()/3600
            if point.time in annotated_points or actual > 120:
                continue
            annotated_points.add(point.time)
            label = point.intensity_class
            if point.storm_type != 'Tropical':
                label += f" ({point.storm_type[:4]})"
            initial = actual == 0
            color = '#FFD700' if initial else 'white'
            # Keep labels near their positions, independently of uncertainty radius.
            offset = (22, -20) if initial else (0, 42 if i % 2 else -42)
            ax.annotate(f"T+{actual:g}h\n{point.time:%m/%d %HZ}\n{label}",
                        (point.lon, point.lat), xytext=offset, textcoords='offset points',
                        ha='center', va='center', color=color, fontsize=6,
                        weight='bold' if initial else 'normal', zorder=9,
                        bbox=dict(facecolor='#2f2f2f', edgecolor=color,
                                  boxstyle='round,pad=0.2', alpha=.85, linewidth=.5),
                        arrowprops=dict(arrowstyle='-', color=color, alpha=.5, linewidth=.5))

    show_landfall = render_context is None or (LAYER_LANDFALL_MARKERS is not None and render_context.is_layer_visible(LAYER_LANDFALL_MARKERS))
    landfalls = []
    if show_landfall:
        for pt in forecast_points:
            if pt.landfall:
                ax.plot(pt.lon, pt.lat, 'x', color='red', markersize=6, markeredgewidth=2, zorder=10)
                nearest = find_nearest_city(pt.lon, pt.lat) if geography_mode == 'full' else None
                landfalls.append((pt.time, pt, nearest))
        lines = []
        for t, point, nearest in sorted(landfalls, key=lambda event: event[0]):
            location = (f"{nearest[0]} ({nearest[3]:.0f}km)" if nearest
                        else f"{point.lat:.1f}°N, {point.lon:.1f}°E")
            lines.append(f"Manual {t:%m/%d %H:%MZ} — {location}")
        for number, event in enumerate(landfall_events, 1):
            ax.plot(event.lon, event.lat, 'X', color='red', markersize=6, zorder=10)
            ax.annotate(f"A{number}", (event.lon, event.lat), xytext=(0, -12),
                        textcoords='offset points', color='#ff6060', fontsize=7,
                        ha='center', va='top', zorder=11,
                        bbox=dict(facecolor='#0d0d2b', edgecolor='none', alpha=.8))
            lines.append(f"A{number} {event.time:%m/%d %H:%MZ} — {event.lat:.2f}°N, {event.lon:.2f}°E")
        if lines:
            ax.text(.98, .02, "Coastline crossings (A: approximate; UTC)\n"+"\n".join(lines),
                    transform=ax.transAxes, ha='right', va='bottom', fontsize=7, color='white',
                    bbox=dict(boxstyle='round,pad=.3', facecolor='#2f2f2f', edgecolor='red', alpha=.85),
                    zorder=12)

    from matplotlib.lines import Line2D
    show_legend = render_context is None or getattr(render_context, 'show_legend', True)
    show_intensity_leg = render_context is None or getattr(render_context, 'show_intensity_legend', True)
    show_storm_type_leg = render_context is None or getattr(render_context, 'show_storm_type_legend', True)
    show_city_leg = render_context is None or getattr(render_context, 'show_city_legend', True)
    show_interp_leg = render_context is None or getattr(render_context, 'show_interpolated_legend', True)

    if show_legend:
        intensity_handles = []
        intensity_definitions = {
            'TD': "TD (<63 km/h)", 'TS': "TS (63-88 km/h)", 'STS': "STS (89-118 km/h)",
            'C1': "CAT1 (119-153 km/h)", 'C2': "CAT2 (154-177 km/h)", 'C3': "CAT3 (178-208 km/h)",
            'C4': "CAT4 (209-251 km/h)", 'C5': "CAT5 (>251 km/h)"
        }
        for intensity in ['TD', 'TS', 'STS', 'C1', 'C2', 'C3', 'C4', 'C5']:
            intensity_handles.append(Patch(facecolor=category_colors[intensity], edgecolor='white', label=intensity_definitions.get(intensity, intensity)))
        if show_intensity_leg:
            ax.add_artist(ax.legend(handles=intensity_handles, loc='upper right', title='Intensity Classes',
                facecolor='#2f2f2f', edgecolor='white', labelcolor='white', ncol=2, fontsize=7, columnspacing=1.0, handletextpad=0.5))
        storm_type_handles = [
            Line2D([0], [0], marker='o', color='w', label='Tropical', markerfacecolor='white', markeredgecolor='white', markersize=8),
            Line2D([0], [0], marker='s', color='w', label='Subtropical', markerfacecolor='white', markeredgecolor='white', markersize=8),
            Line2D([0], [0], marker='^', color='w', label='Extratropical', markerfacecolor='white', markeredgecolor='white', markersize=8),
            Line2D([0], [0], marker='D', color='w', label='Low', markerfacecolor='white', markeredgecolor='white', markersize=8)
        ]
        if show_interp_leg and has_interpolated:
            storm_type_handles.append(Line2D([0], [0], linestyle='--', color='white', alpha=0.4, linewidth=2, label='Interpolated Track'))
        if show_storm_type_leg:
            ax.add_artist(ax.legend(handles=storm_type_handles, loc='right', title='Storm Types',
                facecolor='#2f2f2f', edgecolor='white', labelcolor='white', ncol=1, fontsize=7, bbox_to_anchor=(0.98, 0.65), handletextpad=0.5))
        if show_city_leg:
            city_handles = [
                Patch(facecolor='#2f2f2f', edgecolor='#FFD700', label='Major Cities (>250k)'),
                Patch(facecolor='#2f2f2f', edgecolor='#C0C0C0', label='Local Cities (100k-250k)'),
                Patch(facecolor='#2f2f2f', edgecolor='#808080', label='Small Cities (10k-100k)'),
                Patch(facecolor='#2f2f2f', edgecolor='#4169E1', label='Provincial Capitals')
            ]
            ax.legend(handles=city_handles, loc='right', title='Cities', facecolor='#2f2f2f', edgecolor='white',
                     labelcolor='white', ncol=1, fontsize=7, bbox_to_anchor=(0.98, 0.52), handletextpad=0.5)

    # Layer: metadata_footer
    show_metadata = render_context is None or (LAYER_METADATA_FOOTER is not None and render_context.is_layer_visible(LAYER_METADATA_FOOTER))
    if show_metadata:
        if render_context is not None and getattr(render_context, 'metadata_lines', None):
            metadata_lines = render_context.metadata_lines
        else:
            metadata_lines = [
                f"Generated: {datetime.now(timezone.utc):%Y-%m-%d %H%MZ} UTC",
                f"CycloneAid {VERSION}",
                f"Forecaster Confidence: {forecaster_confidence}",
                f"Valid: {issue_time:%Y-%m-%d %H:%MZ} to {forecast_points[-1].time:%Y-%m-%d %H:%MZ}",
            ]
            if has_interpolated:
                metadata_lines.insert(1, "⚠ This track contains interpolated points from GPX data")
            if validation_result.has_warnings():
                metadata_lines.append(f"⚠ {len(validation_result.soft_warnings)} warning(s)")
        metadata_text = "\n".join(metadata_lines)
        has_warn = has_interpolated or (validation_result.has_warnings() if validation_result else False)
        ax.text(0.02, 0.02, metadata_text, fontsize=7, color='white', transform=ax.transAxes,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#2f2f2f',
                         edgecolor='yellow' if has_warn else 'white', alpha=0.8, linewidth=1.5 if has_warn else 1.0),
                zorder=12, va='bottom')

    plt.title(f"{storm_name} Forecast Track — Issued {issue_time:%Y-%m-%d %H:%MZ}",
              color='white', fontsize=18, pad=10)  # Reduced title padding
    note = f"{CONE_METHOD}: heuristic envelope, not calibrated probability; coverage ≤120h"
    if geography_mode == 'degraded':
        note += " | DEGRADED: no basemap, cities, or automatic landfall"
    fig.text(.5, .05, note, ha='center', fontsize=7)
    # Callers are responsible for closing the figure after use
    return fig

if __name__ == '__main__':
    from cycloneaid.cli import track_main
    raise SystemExit(track_main())
