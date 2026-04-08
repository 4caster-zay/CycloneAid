"""
Validation module for storm forecast data.

Provides hard error and soft warning validation before visualization.
"""

from datetime import timedelta
from math import radians, sin, cos, sqrt, atan2
import pandas as pd


def haversine_distance(lon1, lat1, lon2, lat2):
    """Calculate distance between two points in kilometers."""
    R = 6371  # Earth's radius in kilometers
    
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


class ValidationResult:
    """Container for validation results."""
    def __init__(self):
        self.hard_errors = []
        self.soft_warnings = []
        self.is_valid = True
    
    def add_hard_error(self, message):
        """Add a hard error that blocks rendering."""
        self.hard_errors.append(message)
        self.is_valid = False
    
    def add_soft_warning(self, message):
        """Add a soft warning that allows rendering but shows alert."""
        self.soft_warnings.append(message)
    
    def has_errors(self):
        """Check if there are any hard errors."""
        return len(self.hard_errors) > 0
    
    def has_warnings(self):
        """Check if there are any soft warnings."""
        return len(self.soft_warnings) > 0


def validate_forecast_points(forecast_points):
    """
    Validate forecast points before visualization.
    
    Args:
        forecast_points: List of ForecastPoint objects
        
    Returns:
        ValidationResult object with errors and warnings
    """
    result = ValidationResult()
    
    if not forecast_points:
        result.add_hard_error("No forecast points provided")
        return result
    
    # Hard error checks
    _validate_required_fields(forecast_points, result)
    _validate_timestamps(forecast_points, result)
    _validate_duplicate_lead_times(forecast_points, result)
    
    # Soft warning checks (only if no hard errors)
    if result.is_valid:
        _validate_intensity_consistency(forecast_points, result)
        _validate_landfall_locations(forecast_points, result)
        _validate_position_jumps(forecast_points, result)
    
    return result


def _validate_required_fields(forecast_points, result):
    """Check for missing required fields."""
    required_fields = ['time', 'lat', 'lon', 'wind_kt']
    
    for i, pt in enumerate(forecast_points):
        for field in required_fields:
            value = getattr(pt, field, None)
            if value is None or (isinstance(value, str) and value.strip() == ''):
                result.add_hard_error(
                    f"Point {i+1}: Missing required field '{field}'"
                )


def _validate_timestamps(forecast_points, result):
    """Check for non-monotonic timestamps."""
    if len(forecast_points) < 2:
        return
    
    times = [pt.time for pt in forecast_points]
    
    # Check for non-monotonic sequence
    for i in range(1, len(times)):
        if times[i] < times[i-1]:
            result.add_hard_error(
                f"Non-monotonic timestamps: Point {i+1} ({times[i]}) "
                f"is before point {i} ({times[i-1]})"
            )
    
    # Check for duplicate times
    seen_times = set()
    for i, t in enumerate(times):
        if t in seen_times:
            result.add_hard_error(
                f"Duplicate timestamp at point {i+1}: {t}"
            )
        seen_times.add(t)


def _validate_duplicate_lead_times(forecast_points, result):
    """Check for duplicate lead times."""
    if len(forecast_points) < 2:
        return
    
    # Calculate lead times from first point
    t0 = forecast_points[0].time
    lead_times = []
    
    for i, pt in enumerate(forecast_points):
        lead_hours = int((pt.time - t0).total_seconds() / 3600)
        lead_times.append((i, lead_hours))
    
    # Check for duplicates
    seen_leads = {}
    for idx, lead in lead_times:
        if lead in seen_leads:
            result.add_hard_error(
                f"Duplicate lead time {lead}h at points {seen_leads[lead]+1} and {idx+1}"
            )
        seen_leads[lead] = idx


def _validate_intensity_consistency(forecast_points, result):
    """Check for wind speed increases while intensity class decreases."""
    intensity_order = ['TD', 'TS', 'STS', 'C1', 'C2', 'C3', 'C4', 'C5']
    
    for i in range(1, len(forecast_points)):
        prev_pt = forecast_points[i-1]
        curr_pt = forecast_points[i]
        
        prev_wind = prev_pt.wind_kt
        curr_wind = curr_pt.wind_kt
        
        prev_intensity_idx = intensity_order.index(prev_pt.intensity_class) if prev_pt.intensity_class in intensity_order else -1
        curr_intensity_idx = intensity_order.index(curr_pt.intensity_class) if curr_pt.intensity_class in intensity_order else -1
        
        # Wind increased but intensity decreased
        if (curr_wind > prev_wind and 
            prev_intensity_idx >= 0 and curr_intensity_idx >= 0 and
            curr_intensity_idx < prev_intensity_idx):
            result.add_soft_warning(
                f"Point {i+1}: Wind speed increased ({prev_wind}→{curr_wind} kt) "
                f"but intensity class decreased ({prev_pt.intensity_class}→{curr_pt.intensity_class})"
            )


def _validate_landfall_locations(forecast_points, result):
    """Check if landfall points are actually offshore."""
    # This is a simplified check - in reality, would need land/sea mask
    # For now, flag if landfall is set but coordinates suggest offshore
    # (e.g., very low latitude/longitude in Western Pacific context)
    
    for i, pt in enumerate(forecast_points):
        if pt.landfall:
            # Basic check: if coordinates are clearly in open ocean
            # (This is heuristic - proper check would use land/sea mask)
            if pt.lat < 5 or pt.lat > 35 or pt.lon < 100 or pt.lon > 150:
                result.add_soft_warning(
                    f"Point {i+1}: Landfall flagged at ({pt.lat:.2f}°N, {pt.lon:.2f}°E) "
                    f"but location may be offshore"
                )


def _validate_position_jumps(forecast_points, result):
    """Check for unrealistic position jumps."""
    MAX_REASONABLE_SPEED_KMH = 50  # Maximum reasonable storm speed (~27 kt)
    
    for i in range(1, len(forecast_points)):
        prev_pt = forecast_points[i-1]
        curr_pt = forecast_points[i]
        
        # Calculate time difference in hours
        dt_hours = (curr_pt.time - prev_pt.time).total_seconds() / 3600
        
        if dt_hours <= 0:
            continue  # Already caught by timestamp validation
        
        # Calculate distance
        distance_km = haversine_distance(
            prev_pt.lon, prev_pt.lat,
            curr_pt.lon, curr_pt.lat
        )
        
        # Calculate speed
        speed_kmh = distance_km / dt_hours if dt_hours > 0 else 0
        
        # Flag if speed exceeds reasonable maximum
        if speed_kmh > MAX_REASONABLE_SPEED_KMH:
            result.add_soft_warning(
                f"Point {i+1}: Large position jump detected. "
                f"Distance: {distance_km:.1f} km in {dt_hours:.1f}h "
                f"(speed: {speed_kmh:.1f} km/h)"
            )
        
        # Also flag if distance > 300 km in 6 hours
        if dt_hours <= 6 and distance_km > 300:
            result.add_soft_warning(
                f"Point {i+1}: Sudden jump of {distance_km:.1f} km in {dt_hours:.1f}h "
                f"(>300 km in 6h threshold)"
            )
