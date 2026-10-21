"""Regional WGS84 geodesic discs for the documented legacy heuristic envelope."""
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from cycloneaid.geography import GEOD

ERROR_MODERATE = {0:20, 12:40, 24:80, 36:115, 48:150, 60:175, 72:200, 96:300, 120:400}
ERROR_TABLES = {"Moderate": ERROR_MODERATE,
                "High": {h:r*.8 for h,r in ERROR_MODERATE.items()},
                "Low": {h:r*1.3 for h,r in ERROR_MODERATE.items()}}


def radius_at(hour, table):
    return float(np.interp(hour, sorted(table), [table[h] for h in sorted(table)]))


def geodesic_disc(lon, lat, radius_km):
    # 144 bearings: <125 m radial chord error for the largest legacy radius.
    bearings = np.linspace(0, 360, 145)
    lons, lats, _ = GEOD.fwd(np.full(len(bearings), lon), np.full(len(bearings), lat),
                            bearings, np.full(len(bearings), radius_km*1000))
    return Polygon(zip(lons, lats))


def create_optimized_buffers(forecast_points, table, issue_time, track_times=None):
    if not forecast_points:
        raise ValueError("No forecast points provided")
    hours = np.array([(p.time-issue_time).total_seconds()/3600 for p in forecast_points])
    start, end = max(0, hours[0]), min(max(table), hours[-1])
    if end < start:
        raise ValueError("No forecast coverage within the heuristic envelope's 0–120h range")
    # Sample only covered intervals, at <=1h or <=10km track spacing.
    samples = {float(start), float(end)}
    for i in range(len(hours)-1):
        left, right = max(start, hours[i]), min(end, hours[i+1])
        if right < left:
            continue
        a, b = forecast_points[i:i+2]
        _, _, distance = GEOD.inv(a.lon, a.lat, b.lon, b.lat)
        count = max(1, int(np.ceil((right-left))), int(np.ceil(distance/10000)))
        samples.update(np.linspace(left, right, count+1))
    discs = []
    for hour in sorted(samples):
        i = min(max(int(np.searchsorted(hours, hour, side="right"))-1, 0), len(hours)-1)
        a = forecast_points[i]
        lon, lat = a.lon, a.lat
        if i+1 < len(hours):
            b = forecast_points[i+1]
            azimuth, _, distance = GEOD.inv(a.lon, a.lat, b.lon, b.lat)
            fraction = (hour-hours[i])/(hours[i+1]-hours[i])
            lon, lat, _ = GEOD.fwd(a.lon, a.lat, azimuth, distance*fraction)
        discs.append(geodesic_disc(lon, lat, radius_at(hour, table)))
    return unary_union(discs)
