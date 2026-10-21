"""Cached geography, conservative city indexing, and approximate landfall events."""
from contextlib import closing
from dataclasses import dataclass
from functools import lru_cache
from math import asin, cos, degrees, pi, radians, sin
from pathlib import Path
import cartopy
import cartopy.io.shapereader as shpreader
from pyproj import Geod
from rtree import index
from shapely.geometry import LineString, Point
from shapely.ops import unary_union
from shapely.prepared import prep
import pandas as pd
from validation import haversine_distance

GEOD = Geod(ellps="WGS84")
ASSETS = (("10m", "physical", "land"), ("10m", "physical", "coastline"),
          ("50m", "cultural", "admin_0_boundary_lines_land"),
          ("10m", "cultural", "admin_1_states_provinces_lines"),
          ("10m", "cultural", "populated_places"))


def geography_readiness():
    missing = []
    for resolution, category, name in ASSETS:
        relative = Path("shapefiles")/"natural_earth"/category/f"ne_{resolution}_{name}.shp"
        roots = [Path(cartopy.config[key]) for key in ("data_dir", "pre_existing_data_dir")]
        if not any(all((root/relative).with_suffix(suffix).exists() for suffix in (".shp", ".shx", ".dbf")) for root in roots):
            missing.append(f"{resolution}/{category}/{name}")
    return tuple(missing)


def ensure_geography():
    try:
        for resolution, category, name in ASSETS:
            shpreader.natural_earth(resolution=resolution, category=category, name=name)
        if geography_readiness():
            raise RuntimeError("Incomplete geography cache; remove the incomplete shapefile set and prepare assets again")
    except Exception as exc:
        raise RuntimeError("Geography assets unavailable. Connect once and use 'Prepare map assets', "
                           "or select Degraded geography in Session settings. " + str(exc)) from exc


@lru_cache(maxsize=1)
def get_city_data():
    path = shpreader.natural_earth(resolution="10m", category="cultural", name="populated_places")
    cities = []
    city_index = index.Index()
    with closing(shpreader.Reader(path)) as reader:
        for i, rec in enumerate(reader.records()):
            lon, lat = rec.geometry.x, rec.geometry.y
            attributes = rec.attributes
            feature = str(attributes.get("FEATURECLA", "")).lower()
            capital = "capital" in feature or attributes.get("ADM1CAP", 0) == 1
            cities.append((lon, lat, attributes["NAME"], attributes.get("POP_MAX", 0), capital))
            city_index.insert(i, (lon, lat, lon, lat))
    return cities, city_index


@lru_cache(maxsize=1)
def get_ph_provinces():
    path = shpreader.natural_earth(resolution="10m", category="cultural", name="admin_1_states_provinces_lines")
    with closing(shpreader.Reader(path)) as reader:
        return tuple(rec.geometry for rec in reader.records()
                     if rec.attributes.get("admin", rec.attributes.get("adm0_name")) == "Philippines")


def city_candidates(lon, lat, distance_km, city_index):
    angular = min(pi, distance_km/6371)
    lat_delta = degrees(angular)
    if abs(lat)+lat_delta >= 90:
        return list(city_index.intersection((-180, max(-90, lat-lat_delta), 180, min(90, lat+lat_delta))))
    lon_delta = degrees(asin(min(1, sin(angular)/cos(radians(lat)))))
    low, high = lon-lon_delta, lon+lon_delta
    boxes = [(low, high)]
    if low < -180:
        boxes = [(-180, high), (low+360, 180)]
    elif high > 180:
        boxes = [(low, 180), (-180, high-360)]
    return list({i for left, right in boxes for i in city_index.intersection(
        (left, lat-lat_delta, right, lat+lat_delta))})


def find_nearest_city(lon, lat, cities_data=None, max_distance_km=250, *, city_index=None):
    if cities_data is None:
        cities_data, city_index = get_city_data()
    candidates = (city_candidates(lon, lat, max_distance_km, city_index)
                  if city_index is not None else range(len(cities_data)))
    nearest, minimum = None, float("inf")
    for i in sorted(candidates):
        clon, clat, name, *_ = cities_data[i]
        distance = haversine_distance(lon, lat, clon, clat)
        if distance <= max_distance_km and distance < minimum:
            nearest, minimum = (name, clon, clat, distance), distance
    return nearest


def cities_in_cone(cone):
    cities, city_index = get_city_data()
    prepared = prep(cone)
    return [cities[i] for i in city_index.intersection(cone.bounds)
            if prepared.covers(Point(cities[i][0], cities[i][1]))]


@lru_cache(maxsize=1)
def get_land_geometry():
    path = shpreader.natural_earth(resolution="10m", category="physical", name="land")
    with closing(shpreader.Reader(path)) as reader:
        return unary_union(list(reader.geometries()))


@dataclass(frozen=True)
class LandfallEvent:
    time: pd.Timestamp
    lon: float
    lat: float
    wind_kt: float
    segment_index: int
    source: str = "Approximate Natural Earth coastline intersection"


def detect_landfalls(points, land=None):
    """Find water-to-land crossings, densifying geodesic segments to <=5 km."""
    if len(points) < 2:
        return ()
    land = get_land_geometry() if land is None else land
    events = []
    for i, (start, end) in enumerate(zip(points, points[1:])):
        _, _, distance = GEOD.inv(start.lon, start.lat, end.lon, end.lat)
        if distance < 1:
            continue
        steps = max(0, int(distance//5000))
        middle = GEOD.npts(start.lon, start.lat, end.lon, end.lat, steps) if steps else []
        line = LineString([(start.lon, start.lat), *middle, (end.lon, end.lat)])
        intersection = line.intersection(land.boundary)
        def intersections(geometry):
            if geometry.geom_type == "Point":
                yield geometry
            elif hasattr(geometry, "geoms"):
                for child in geometry.geoms:
                    yield from intersections(child)
        for crossing in sorted(intersections(intersection), key=line.project):
            fraction = line.project(crossing, normalized=True)
            before = line.interpolate(max(0, fraction-1e-6), normalized=True)
            after = line.interpolate(min(1, fraction+1e-6), normalized=True)
            if not land.covers(before) and land.covers(after):
                time = start.time+(end.time-start.time)*fraction
                if not any(p.landfall and abs((p.time-time).total_seconds()) < 1 for p in (start, end)):
                    events.append(LandfallEvent(time, crossing.x, crossing.y,
                                               start.wind_kt+(end.wind_kt-start.wind_kt)*fraction, i))
    return tuple(events)
