import pandas as pd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
from cartopy.feature import NaturalEarthFeature
from shapely.geometry import Point, box
from shapely.ops import unary_union
from matplotlib.patches import Patch
from matplotlib.transforms import Affine2D, offset_copy, blended_transform_factory, ScaledTranslation
import sys
import os
from math import radians, sin, cos, sqrt, atan2, degrees
from scipy.interpolate import interp1d
import numpy as np
from rtree import index
from functools import lru_cache
from datetime import timedelta
import matplotlib.dates as mdates
import xml.etree.ElementTree as ET

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

# ─── Error Radii Tables (km) ───
error_moderate = {0:20,12:40,24:80,36:115,48:150,60:175,72:200,96:300,120:400}
error_high     = {t:r*0.8 for t,r in error_moderate.items()}
error_low      = {t:r*1.3 for t,r in error_moderate.items()}
error_tables   = {'Low':error_low, 'Moderate':error_moderate, 'High':error_high}

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

class ForecastPoint:
    """Represents a single point in the storm forecast track.
    
    Attributes:
        time (datetime): Time of the forecast point
        lat (float): Latitude in degrees
        lon (float): Longitude in degrees
        wind_kt (int): Wind speed in knots
        intensity_class (str): Intensity classification (TD, TS, STS, C1-C5)
        storm_type (str): Storm structure/type (Tropical, Subtropical, Extratropical, Low)
        landfall (bool): Whether this point represents landfall
        is_interpolated (bool): Whether this point was interpolated from GPX data
    """
    def __init__(self, time, lat, lon, wind_kt, intensity_class=None, storm_type=None, 
                 landfall=False, is_interpolated=False, category=None):
        self.time     = pd.to_datetime(time)
        self.lat      = float(lat)
        self.lon      = float(lon)
        self.wind_kt  = int(wind_kt)
        self.landfall = bool(landfall) if isinstance(landfall, bool) else str(landfall).lower()=='true'
        self.is_interpolated = bool(is_interpolated)
        
        # Backward compatibility: if category is provided, parse it
        if category is not None:
            intensity_class, storm_type = self._parse_category(category)
        
        # Set defaults if not provided
        if intensity_class is None:
            intensity_class = self._derive_intensity_class(wind_kt)
        if storm_type is None:
            storm_type = "Tropical"
        
        self.intensity_class = intensity_class
        self.storm_type = storm_type
    
    def _parse_category(self, category):
        """Parse legacy category into intensity_class and storm_type."""
        # Map legacy categories to new structure
        if category in ['L']:
            return 'TD', 'Low'
        elif category in ['EX']:
            # Need wind to determine intensity
            return self._derive_intensity_class(self.wind_kt), 'Extratropical'
        elif category in ['SD']:
            return 'TD', 'Subtropical'
        elif category in ['SS']:
            return 'TS' if self.wind_kt >= 34 else 'TD', 'Subtropical'
        else:
            # Regular intensity classes (TD, TS, STS, C1-C5)
            return category, 'Tropical'
    
    def _derive_intensity_class(self, wind_kt):
        """Derive intensity class from wind speed."""
        thresholds = [
            (137, 'C5'), (113, 'C4'), (96, 'C3'), (83, 'C2'), 
            (64, 'C1'), (48, 'STS'), (34, 'TS'), (0, 'TD')
        ]
        for threshold, label in thresholds:
            if wind_kt >= threshold:
                return label
        return 'TD'
    
    @property
    def category(self):
        """Legacy property for backward compatibility."""
        # Return composite label
        if self.storm_type == 'Low':
            return 'L'
        elif self.storm_type == 'Extratropical':
            return 'EX'
        elif self.storm_type == 'Subtropical':
            return 'SS' if self.intensity_class in ['TS', 'STS', 'C1', 'C2', 'C3', 'C4', 'C5'] else 'SD'
        else:
            return self.intensity_class


def read_gpx_to_dataframe(gpx_path):
    """
    Read a GPX file and convert track points to a DataFrame compatible
    with the existing forecast CSV format.

    The resulting DataFrame has columns:
        ['time', 'lat', 'lon', 'wind_kt', 'intensity_class', 'storm_type', 
         'landfall', 'is_interpolated']

    - time: taken from GPX <time> element when available, otherwise
            generated as hourly intervals from the current UTC time.
    - wind_kt: default 0 (user can edit later in CSV if desired).
    - intensity_class: default 'TD' (derived from wind_kt=0).
    - storm_type: default 'Low' for GPX imports.
    - landfall: default False.
    - is_interpolated: True if timestamps were missing and generated.
    """
    if not os.path.exists(gpx_path):
        raise FileNotFoundError(f"GPX file not found: {gpx_path}")

    tree = ET.parse(gpx_path)
    root = tree.getroot()

    # Detect namespace (e.g. '{http://www.topografix.com/GPX/1/1}gpx')
    if '}' in root.tag:
        ns_uri = root.tag.split('}')[0].strip('{')
        ns = {'gpx': ns_uri}
        trkpt_xpath = './/gpx:trkpt'
        rtept_xpath = './/gpx:rtept'
        wpt_xpath = './/gpx:wpt'
        time_tag = 'gpx:time'
    else:
        ns = {}
        trkpt_xpath = './/trkpt'
        rtept_xpath = './/rtept'
        wpt_xpath = './/wpt'
        time_tag = 'time'

    points = []

    # Support both track points (<trkpt>) and route points (<rtept>),
    # and fall back to waypoints (<wpt>) if necessary. This covers
    # exports from tools like Windy.com that use <rtept>.
    trkpts = list(root.findall(trkpt_xpath, ns))
    if not trkpts:
        trkpts = list(root.findall(rtept_xpath, ns))
    if not trkpts:
        trkpts = list(root.findall(wpt_xpath, ns))

    if not trkpts:
        raise ValueError(
            f"No usable points (<trkpt>, <rtept>, or <wpt>) found in GPX file: {gpx_path}"
        )

    # Check if any timestamps are missing
    has_timestamps = False
    for trkpt in trkpts:
        time_elem = trkpt.find(time_tag, ns)
        if time_elem is not None and time_elem.text:
            has_timestamps = True
            break
    
    # If no times are provided, create a simple hourly sequence from now
    base_time = pd.Timestamp.utcnow().floor('H')
    is_interpolated = not has_timestamps

    for i, trkpt in enumerate(trkpts):
        lat = float(trkpt.attrib.get('lat'))
        lon = float(trkpt.attrib.get('lon'))

        time_elem = trkpt.find(time_tag, ns)
        if time_elem is not None and time_elem.text:
            time_val = pd.to_datetime(time_elem.text)
            point_interpolated = False
        else:
            time_val = base_time + pd.Timedelta(hours=i)
            point_interpolated = True

        points.append(
            {
                'time': time_val,
                'lat': lat,
                'lon': lon,
                'wind_kt': 0,
                'intensity_class': 'TD',  # Default for 0 wind
                'storm_type': 'Low',  # Default for GPX imports
                'landfall': False,
                'is_interpolated': point_interpolated,
            }
        )

    df = pd.DataFrame(points)
    if df.empty:
        raise ValueError(f"GPX file produced no valid points: {gpx_path}")
    return df

def find_nearest_city(point_lon, point_lat, cities_data, max_distance_km=200):
    """Find the nearest city to a given point within max_distance_km.
    
    Args:
        point_lon (float): Longitude of the point
        point_lat (float): Latitude of the point
        cities_data (list): List of (lon, lat, name, population, is_capital) tuples
        max_distance_km (float): Maximum distance to consider in kilometers
        
    Returns:
        tuple: (name, lon, lat, distance_km) or None if no city found
    """
    def haversine_distance(lon1, lat1, lon2, lat2):
        R = 6371  # Earth's radius in kilometers
        
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c
    
    nearest_city = None
    min_distance = float('inf')
    
    for city_lon, city_lat, name, pop, is_capital in cities_data:
        distance = haversine_distance(point_lon, point_lat, city_lon, city_lat)
        if distance <= max_distance_km and distance < min_distance:
            min_distance = distance
            nearest_city = (name, city_lon, city_lat, distance)
    
    return nearest_city

@lru_cache(maxsize=128)
def calculate_buffer_size(lat, radius_km):
    """Calculate buffer size with latitude correction (cached for performance)"""
    lat_deg = radius_km/111.0
    lon_deg = radius_km/(111.0 * cos(radians(lat)))
    return (lat_deg + lon_deg) / 2

def create_optimized_buffers(forecast_points, table, issue_time, track_times):
    """Create optimized buffer generation with reduced computational overhead"""
    buffers = []
    table_hours = sorted(table.keys())
    
    # Pre-calculate track data as numpy arrays for faster operations
    track_data = np.array([(pt.lon, pt.lat) for pt in forecast_points])
    track_hours = np.array([(pt.time - issue_time).total_seconds()/3600 for pt in forecast_points])
    
    # Create interpolation functions with numpy arrays
    lon_interp = interp1d(track_hours, track_data[:, 0], kind='linear',
                         bounds_error=False, fill_value=(track_data[0, 0], track_data[-1, 0]))
    lat_interp = interp1d(track_hours, track_data[:, 1], kind='linear',
                         bounds_error=False, fill_value=(track_data[0, 1], track_data[-1, 1]))
    
    # Process forecast points with optimized buffer creation
    for pt, hour in zip(forecast_points, track_hours):
        # Get radius efficiently
        if hour <= 0:
            radius_km = table[0]
        elif hour >= max(table_hours):
            radius_km = table[max(table_hours)]
        elif hour in table:
            radius_km = table[hour]
        else:
            nearest_hour = min(table_hours, key=lambda x: abs(x - hour))
            radius_km = table[nearest_hour]
        
        # Use cached buffer size calculation with increased segments for smoother edges
        buffer_size = calculate_buffer_size(pt.lat, radius_km)
        
        # Create main buffer with increased segments for smoother edges
        buffer = Point(pt.lon, pt.lat).buffer(buffer_size, quad_segs=96)  # Increased from 64 to 96
        buffers.append(buffer)
        
        # Optimize early forecast points buffer creation
        if 0 <= hour <= 24:
            # Create additional buffers with increased segments
            for factor in [0.95, 1.05]:  # Reduced from 4 to 2 factors
                extra_buffer = Point(pt.lon, pt.lat).buffer(buffer_size * factor, quad_segs=48)  # Increased from 32 to 48
                buffers.append(extra_buffer)
    
    # Optimize interpolated points
    # Use more points for smoother interpolation
    hours = np.concatenate([
        np.linspace(0, 24, 96),     # Increased from 48 to 96 points
        np.linspace(24, max(track_times), 48)[1:]  # Increased from 24 to 48 points
    ])
    
    # Vectorize interpolation for better performance
    interp_lons = np.clip(lon_interp(hours), None, 150)
    interp_lats = np.clip(lat_interp(hours), 0, 40)
    
    # Process interpolated points efficiently
    for lon, lat, hour in zip(interp_lons, interp_lats, hours):
        # Efficient radius calculation
        if hour <= 0:
            radius_km = table[0]
        elif hour >= max(table_hours):
            radius_km = table[max(table_hours)]
        else:
            prev_hour = max([h for h in table_hours if h <= hour])
            next_hour = min([h for h in table_hours if h >= hour])
            if prev_hour == next_hour:
                radius_km = table[prev_hour]
            else:
                weight = (hour - prev_hour) / (next_hour - prev_hour)
                radius_km = table[prev_hour] + weight * (table[next_hour] - table[prev_hour])
        
        buffer_size = calculate_buffer_size(lat, radius_km)
        buffer = Point(lon, lat).buffer(buffer_size, quad_segs=48)  # Increased from 32 to 48
        buffers.append(buffer)
    
    return unary_union(buffers)

def optimize_city_processing(cities_data, cone):
    """Process cities with spatial indexing for improved performance"""
    # Create spatial index
    idx = index.Index()
    for i, (lon, lat, name, pop, is_capital) in enumerate(cities_data):
        idx.insert(i, (lon, lat, lon, lat))
    
    # Get cone bounds for pre-filtering
    bounds = cone.bounds
    bbox = box(*bounds)
    
    # Pre-filter cities using spatial index
    cities_in_bbox = []
    for i in idx.intersection(bounds):
        lon, lat, name, pop, is_capital = cities_data[i]
        if Point(lon, lat).within(bbox):
            cities_in_bbox.append((lon, lat, name, pop, is_capital))
    
    # Final filtering using actual cone
    return [(lon, lat, name, pop, is_capital) 
            for lon, lat, name, pop, is_capital in cities_in_bbox 
            if Point(lon, lat).within(cone)]

def plot_storm_track(forecast_points, storm_name="STORM", issue_time=None, forecaster_confidence='Moderate', render_context=None):
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
    validation_result = validate_forecast_points(forecast_points)
    
    if validation_result.has_errors():
        error_msg = "Validation errors prevent rendering:\n" + "\n".join(validation_result.hard_errors)
        raise ValueError(error_msg)

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
    
    # Get coordinates for plotting
    xs, ys = cone.exterior.xy
    
    # Calculate map extent with padding and 4:3 aspect ratio
    bounds = cone.bounds  # (min_lon, min_lat, max_lon, max_lat)
    
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
    
    # Ensure we don't exceed reasonable bounds for the region
    min_lon = max(100, min_lon)  # Don't go west of 100°E
    max_lon = min(150, max_lon)  # Don't go east of 150°E
    min_lat = max(0, min_lat)    # Don't go south of equator
    max_lat = min(40, max_lat)   # Don't go north of 40°N
    
    # Set the map extent
    ax.set_extent([min_lon, max_lon, min_lat, max_lat], crs=ccrs.PlateCarree())

    # land/ocean in dark mode
    ax.add_feature(cfeature.LAND.with_scale('50m'), facecolor='#2f2f2f')
    ax.add_feature(cfeature.OCEAN.with_scale('50m'), facecolor='#0d0d2b')
    ax.add_feature(cfeature.BORDERS, edgecolor='white', linestyle=':')
    ax.coastlines(color='white')
    
    # Add gridlines with adaptive spacing based on map size
    lon_range = max_lon - min_lon
    grid_spacing = max(1, round(lon_range / 8))  # Aim for about 8 gridlines across
    
    gl = ax.gridlines(draw_labels=True, color='gray', alpha=0.3)
    gl.xlocator = plt.MultipleLocator(grid_spacing)
    gl.ylocator = plt.MultipleLocator(grid_spacing)
    gl.top_labels = False
    gl.right_labels = False

    # Add provincial boundaries for Philippines
    admin1_shp = shpreader.natural_earth(
        resolution='10m',  # Restored to 10m resolution
        category='cultural',
        name='admin_1_states_provinces_lines'
    )
    
    reader = shpreader.Reader(admin1_shp)
    for rec in reader.records():
        if rec.attributes.get('admin', rec.attributes.get('adm0_name')) == 'Philippines':
            geometries = [rec.geometry]
            ax.add_geometries(
                geometries,
                crs=ccrs.PlateCarree(),
                facecolor='none',
                edgecolor='#FFD700',
                linewidth=0.8,
                alpha=0.3,
                zorder=2
            )

    # Collect cities data with better capital identification
    pop_shp = shpreader.natural_earth(
        resolution='10m',  # Restored to 10m resolution
        category='cultural',
        name='populated_places'
    )
    
    cities_data = []  # Store as (lon, lat, name, population, is_capital)
    reader = shpreader.Reader(pop_shp)
    for rec in reader.records():
        lon, lat = rec.geometry.x, rec.geometry.y
        name = rec.attributes['NAME']
        population = rec.attributes.get('POP_MAX', 0)
        
        # Check if it's a capital using multiple Natural Earth attributes
        is_capital = (
            rec.attributes.get('FEATURECLA', '').lower() in [
                'admin-0 capital', 'admin-1 capital', 'admin-1 region capital'
            ] or
            rec.attributes.get('CAPITAL', '').lower() in ['admin-1 capital', 'yes', 'primary'] or
            rec.attributes.get('ADM1CAP', 0) == 1
        )
        
        cities_data.append((lon, lat, name, population, is_capital))

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
        interpolated_segments = []
        regular_segments = []
        current_seg = []
        is_current_interpolated = False
        for i, pt in enumerate(forecast_points):
            if i == 0:
                is_current_interpolated = pt.is_interpolated
                current_seg = [(pt.lon, pt.lat)]
            elif pt.is_interpolated != is_current_interpolated:
                if is_current_interpolated:
                    interpolated_segments.append(current_seg)
                else:
                    regular_segments.append(current_seg)
                is_current_interpolated = pt.is_interpolated
                current_seg = [(pt.lon, pt.lat)]
            else:
                current_seg.append((pt.lon, pt.lat))
        if is_current_interpolated:
            interpolated_segments.append(current_seg)
        else:
            regular_segments.append(current_seg)
        for seg in regular_segments:
            if len(seg) > 1:
                seg_lons, seg_lats = zip(*seg)
                ax.plot(seg_lons, seg_lats, '--', color='white', linewidth=2.0, zorder=6, alpha=line_opacity)
        for seg in interpolated_segments:
            if len(seg) > 1:
                seg_lons, seg_lats = zip(*seg)
                ax.plot(seg_lons, seg_lats, '--', color='white', linewidth=2.0, zorder=6, alpha=interp_opacity, dashes=(5, 5))

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
        for i in range(3):
            alpha_mult = (1 - (i * 0.2)) * cone_opacity_mult
            ax.fill(xs, ys, color=cone_color, alpha=cone_alpha * alpha_mult, transform=ccrs.PlateCarree(), zorder=5)
        ax.plot(xs, ys, '-', color=cone_color, linewidth=1.5, transform=ccrs.PlateCarree(), alpha=0.7 * cone_opacity_mult, zorder=5)

    # Layer: lead_time_annotations
    show_lead_time = (render_context is None or (LAYER_LEAD_TIME_ANNOTATIONS is not None and render_context.is_layer_visible(LAYER_LEAD_TIME_ANNOTATIONS))) and (render_context is None or getattr(render_context, 'show_lead_time_annotations', True))
    show_error_radii = render_context is None or getattr(render_context, 'show_error_radii_labels', True)

    if show_lead_time:
        standard_leadtimes = [0, 12, 24, 36, 48, 72, 96, 120]
        for i, leadtime in enumerate(standard_leadtimes):
            target_time = issue_time + timedelta(hours=leadtime)
            closest_pt = min(forecast_points, 
                            key=lambda pt: abs((pt.time - target_time).total_seconds()))
            actual_leadtime = int((closest_pt.time - issue_time).total_seconds() / 3600)
            if actual_leadtime <= 0:
                error_radius = table[0]
            elif actual_leadtime >= max(table.keys()):
                error_radius = table[max(table.keys())]
            else:
                nearest_hour = min(table.keys(), key=lambda x: abs(x - actual_leadtime))
                error_radius = table[nearest_hour]
            lat_deg = error_radius/111.0
            lon_deg = error_radius/(111.0 * cos(radians(closest_pt.lat)))
            offset_deg = (lat_deg + lon_deg) / 2
            box_color = 'white'
            text_color = 'white'
            font_weight = 'normal'
            box_alpha = 0.7
            box_linewidth = 0.5
            scale_factor = 1.5
            if actual_leadtime == 0:
                first_pt = forecast_points[0]
                second_pt = forecast_points[1]
                dx = second_pt.lon - first_pt.lon
                dy = second_pt.lat - first_pt.lat
                length = sqrt(dx*dx + dy*dy)
                if length > 0:
                    dx, dy = -dx/length, -dy/length
                else:
                    dx, dy = -1, 0
                scale_factor = 8.0
                box_color = '#FFD700'
                text_color = '#FFD700'
                font_weight = 'bold'
                box_alpha = 0.9
                box_linewidth = 1.0
                offset_lon = dx * offset_deg * scale_factor
                offset_lat = dy * offset_deg * scale_factor
            elif actual_leadtime == 12:
                prev_pt = forecast_points[0]
                dx = closest_pt.lon - prev_pt.lon
                dy = closest_pt.lat - prev_pt.lat
                length = sqrt(dx*dx + dy*dy)
                if length > 0:
                    dx, dy = dx/length, dy/length
                    perp_dx, perp_dy = -dy, dx
                else:
                    perp_dx, perp_dy = 1, 0
                side_multiplier = 1 if i % 2 == 0 else -1
                scale_factor = 3.2
                offset_lon = perp_dx * offset_deg * side_multiplier * scale_factor
                offset_lat = perp_dy * offset_deg * side_multiplier * scale_factor
            else:
                if i > 0:
                    prev_pt = forecast_points[forecast_points.index(closest_pt) - 1]
                    dx = closest_pt.lon - prev_pt.lon
                    dy = closest_pt.lat - prev_pt.lat
                else:
                    next_pt = forecast_points[1]
                    dx = next_pt.lon - closest_pt.lon
                    dy = next_pt.lat - closest_pt.lat
                length = sqrt(dx*dx + dy*dy)
                if length > 0:
                    dx, dy = dx/length, dy/length
                    perp_dx, perp_dy = -dy, dx
                else:
                    perp_dx, perp_dy = 1, 0
                side_multiplier = 1 if i % 2 == 0 else -1
                if actual_leadtime <= 36:
                    scale_factor = 2.0
                elif actual_leadtime == 120:
                    scale_factor = 1.2
                else:
                    scale_factor = 1.5
                offset_lon = perp_dx * offset_deg * side_multiplier * scale_factor
                offset_lat = perp_dy * offset_deg * side_multiplier * scale_factor
            box_lon = closest_pt.lon + offset_lon
            box_lat = closest_pt.lat + offset_lat
            box_point = Point(box_lon, box_lat)
            if box_point.within(cone):
                offset_lon *= 2
                offset_lat *= 2
                box_lon = closest_pt.lon + offset_lon
                box_lat = closest_pt.lat + offset_lat
            lbl = closest_pt.intensity_class
            if closest_pt.storm_type != 'Tropical':
                lbl += f" ({closest_pt.storm_type[:4]})"
            box_text = f"T+{actual_leadtime}h\n{closest_pt.time:%m/%d %HZ}\n{lbl}"
            ax.plot([closest_pt.lon, box_lon], [closest_pt.lat, box_lat],
                    '--', color=box_color, alpha=0.3, linewidth=0.5, zorder=8)
            ax.text(box_lon, box_lat, box_text, transform=ccrs.PlateCarree(),
                   ha='center', va='center', color=text_color, fontsize=6, weight=font_weight,
                   bbox=dict(facecolor='#2f2f2f', edgecolor=box_color, boxstyle='round,pad=0.2',
                             alpha=box_alpha, linewidth=box_linewidth), zorder=9)

    show_landfall = render_context is None or (LAYER_LANDFALL_MARKERS is not None and render_context.is_layer_visible(LAYER_LANDFALL_MARKERS))
    landfalls = []
    if show_landfall:
        for pt in forecast_points:
            if pt.landfall:
                ax.plot(pt.lon, pt.lat, 'x', color='red', markersize=6, markeredgewidth=2, zorder=10)
                nearest = find_nearest_city(pt.lon, pt.lat, cities_data)
                landfalls.append((pt.time, pt, nearest))
        if landfalls:
            landfalls.sort(key=lambda x: x[0])
            lines = ["Landfalls"]
            for t, pt, nearest in landfalls:
                lead_hours = int((pt.time - issue_time).total_seconds() / 3600)
                if nearest:
                    city_name, city_lon, city_lat, distance = nearest
                    lines.append(f"T+{lead_hours}h {t:%m/%d %HZ} — {city_name} ({distance:.0f}km)")
                else:
                    lines.append(f"T+{lead_hours}h {t:%m/%d %HZ} — {pt.lat:.1f}°, {pt.lon:.1f}°")
            ax.text(0.98, 0.02, "\n".join(lines),
                    transform=ax.transAxes, ha='right', va='bottom',
                    fontsize=7, color='white',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='#2f2f2f', edgecolor='red', alpha=0.8),
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
                     labelcolor='white', ncol=1, fontsize=7, bbox_to_anchor=(0.98, 0.45), handletextpad=0.5)

    # Layer: metadata_footer
    show_metadata = render_context is None or (LAYER_METADATA_FOOTER is not None and render_context.is_layer_visible(LAYER_METADATA_FOOTER))
    if show_metadata:
        if render_context is not None and getattr(render_context, 'metadata_lines', None):
            metadata_lines = render_context.metadata_lines
        else:
            from datetime import datetime
            try:
                import storm_tracker_gui
                version = storm_tracker_gui.VERSION
            except (ImportError, AttributeError):
                version = "Alpha 0.8.0"
            metadata_lines = [
                f"Generated: {datetime.utcnow():%Y-%m-%d %H%MZ} UTC",
                f"CycloneAid {version}",
                f"Forecaster Confidence: {forecaster_confidence}",
                f"Valid: {issue_time:%Y-%m-%d %H00Z} to {forecast_points[-1].time:%Y-%m-%d %H00Z}",
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

    plt.title(f"{storm_name} Forecast Track — Issued {issue_time:%Y-%m-%d %H00Z}",
              color='white', fontsize=18, pad=10)  # Reduced title padding
    output_dir = "Tracks"
    os.makedirs(output_dir, exist_ok=True)
    outfile = os.path.join(output_dir, f"{storm_name}_{issue_time:%Y%m%d%H}_{forecaster_confidence}.png")
    plt.savefig(outfile, 
                dpi=300,  # Increased DPI for better quality
                bbox_inches='tight',  # Tight bounding box
                pad_inches=0.2,  # Small padding around the plot
                facecolor=fig.get_facecolor())
    # Callers are responsible for closing the figure after use
    return fig

if __name__ == '__main__':
    def get_confidence_level():
        """Prompt for and validate user confidence level input."""
        while True:
            confidence_level = input("Enter track confidence level (High, Moderate, Low): ").title().strip()
            if confidence_level in ['High', 'Moderate', 'Low']:
                return confidence_level
            print("Invalid input. Please enter 'High', 'Moderate', or 'Low'.")

    # Get confidence level either from command line or user input
    confidence_level = sys.argv[1].title() if len(sys.argv)>1 else get_confidence_level()
    if confidence_level not in ['High', 'Moderate', 'Low']:
        raise ValueError("Confidence level must be 'High', 'Moderate', or 'Low'.")

    # Validate command line arguments
    confidence = confidence_level
    storm = sys.argv[2] if len(sys.argv)>2 else 'TYPHOON'

    # Optional third argument: input file (CSV or GPX). Default remains forecast.csv
    input_file = sys.argv[3] if len(sys.argv) > 3 else 'forecast.csv'

    # Check if input file exists
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    try:
        # If GPX, convert to DataFrame compatible with existing pipeline
        if input_file.lower().endswith('.gpx'):
            df = read_gpx_to_dataframe(input_file)
        else:
            df = pd.read_csv(input_file, comment='#')

        required_columns = ['time', 'lat', 'lon', 'wind_kt', 'category', 'landfall']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns in forecast.csv: {', '.join(missing_columns)}")
        
        if df.empty:
            raise ValueError("forecast.csv contains no data")
            
        pts = [ForecastPoint(**r._asdict()) for r in df.itertuples(index=False)]
        
        # Only generate the track graphic here
        plot_storm_track(pts, storm_name=storm,
                        issue_time=pts[0].time,
                        forecaster_confidence=confidence)
        
    except pd.errors.EmptyDataError:
        print("Error: forecast.csv is empty")
    except pd.errors.ParserError:
        print("Error: forecast.csv is not properly formatted")
    except Exception as e:
        print(f"Error processing forecast data: {str(e)}")
