"""Non-destructive CSV/GPX/KML/KMZ import staging shared by GUI and CLI."""
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
import pandas as pd
from cycloneaid.model import ForecastPoint, utc_timestamp
from cycloneaid.session import point_to_row
from validation import validate_forecast_points


@dataclass(frozen=True)
class ImportTrack:
    name: str
    records: tuple[dict, ...]


def _local(element):
    return element.tag.rsplit("}", 1)[-1]


def _text(element, name):
    return next((child.text for child in element if _local(child) == name), None)


def read_tracks(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path, comment="#", keep_default_na=False)
        required = {"time", "lat", "lon", "wind_kt"}
        if not required.issubset(frame.columns):
            raise ValueError("Missing CSV columns: " + ", ".join(sorted(required-set(frame.columns))))
        return [ImportTrack(path.stem, tuple(frame.to_dict("records")))]
    if path.suffix.lower() == ".kmz":
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".kml")]
            if not names:
                raise ValueError("KMZ contains no KML document")
            roots = [(name, ET.fromstring(archive.read(name))) for name in names]
    else:
        roots = [(path.name, ET.parse(path).getroot())]
    tracks = []
    for filename, root in roots:
        if _local(root) == "gpx":
            groups = [el for el in root.iter() if _local(el) in ("trkseg", "rte")]
            if not groups:
                groups = [root]
            for i, group in enumerate(groups, 1):
                points = [el for el in group if _local(el) in ("trkpt", "rtept", "wpt")]
                records = tuple(dict(lat=p.attrib["lat"], lon=p.attrib["lon"],
                                     time=_text(p, "time") or "", wind_kt=0,
                                     storm_type="Low") for p in points)
                if records:
                    tracks.append(ImportTrack(f"{filename}: segment {i}", records))
        else:
            for i, el in enumerate(root.iter(), 1):
                kind = _local(el)
                if kind not in ("LineString", "Point", "Track"):
                    continue
                records = []
                if kind == "Track":
                    coords = [child.text for child in el if _local(child) == "coord"]
                    times = [child.text for child in el if _local(child) == "when"]
                    if times and len(times) != len(coords):
                        raise ValueError("KML Track coordinate/timestamp counts differ")
                    for j, coord in enumerate(coords):
                        lon, lat, *_ = coord.split()
                        records.append(dict(lon=lon, lat=lat, time=times[j] if times else "", wind_kt=0))
                else:
                    for child in el:
                        if _local(child) == "coordinates" and child.text:
                            for token in child.text.split():
                                lon, lat, *_ = token.split(",")
                                records.append(dict(lon=lon, lat=lat, time="", wind_kt=0))
                if records:
                    tracks.append(ImportTrack(f"{filename}: {kind} {i}", tuple(records)))
    if not tracks:
        raise ValueError("No supported track geometry found (polygon rings are not forecast tracks)")
    return tracks


def prepare_track(track, *, start=None, interval_hours=None, override_resolver=None):
    """Resolve missing values without changing a session. Raises on any bad row."""
    points, warnings = [], []
    for i, record in enumerate(track.records):
        raw = dict(record)
        try:
            time = raw.get("time", "")
            origin = raw.get("time_origin", "provided") or "provided"
            if time is None or str(time).strip() == "":
                if start is None or interval_hours is None or interval_hours <= 0:
                    raise ValueError("Missing timestamp; supply an explicit UTC start and positive interval")
                time = utc_timestamp(start) + pd.Timedelta(hours=i*interval_hours)
                origin = "generated"
            else:
                if pd.Timestamp(time).tzinfo is None:
                    warnings.append("Timezone-free timestamps interpreted as UTC")
            args = {key: raw[key] for key in ("lat", "lon", "wind_kt", "intensity_class", "storm_type",
                                              "landfall", "is_interpolated", "category", "override_reason")
                    if key in raw and str(raw[key]).strip() != ""}
            # New columns take precedence over the legacy composite category.
            if args.get("intensity_class"):
                args.pop("category", None)
            point = ForecastPoint(time=time, time_origin=origin, **args)
            from cycloneaid.model import derive_intensity
            if point.intensity_class != derive_intensity(point.wind_kt) and not point.override_reason and override_resolver:
                reason = override_resolver(i+1, point)
                if not reason:
                    raise ValueError("Intensity override cancelled")
                point = ForecastPoint(time=point.time, lat=point.lat, lon=point.lon, wind_kt=point.wind_kt,
                                      intensity_class=point.intensity_class, storm_type=point.storm_type,
                                      landfall=point.landfall, is_interpolated=point.is_interpolated,
                                      time_origin=point.time_origin, override_reason=reason)
            points.append(point)
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"Row {i+1}: {exc}") from exc
    result = validate_forecast_points(points)
    if result.has_errors():
        raise ValueError("\n".join(result.hard_errors))
    return tuple(point_to_row(point) for point in points), tuple(dict.fromkeys(warnings + result.soft_warnings))


def read_forecast(path, **kwargs):
    tracks = read_tracks(path)
    if len(tracks) != 1:
        raise ValueError("Multiple tracks found; select a track in the GUI")
    rows, warnings = prepare_track(tracks[0], **kwargs)
    from cycloneaid.session import parse_row
    return [parse_row(row) for row in rows], warnings
