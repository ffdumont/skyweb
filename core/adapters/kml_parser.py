"""KML parser for SD VFR route files.

Extracts waypoints from a KML file exported by SD VFR Next
and builds SkyWeb Route/Waypoint contract objects.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from core.contracts.enums import LocationType, WaypointRole
from core.contracts.route import Route, RouteLeg, RouteWaypointRef
from core.contracts.waypoint import Waypoint

KML_NS = "{http://www.opengis.net/kml/2.2}"

# Pattern: "LFXU - LES MUREAUX" → icao="LFXU"
_ICAO_NAME_RE = re.compile(r"^([A-Z]{4}) - ")


def parse_kml_waypoints(kml_path: Path) -> list[dict]:
    """Parse waypoints from the Points folder of an SD VFR KML file.

    Returns a list of dicts with keys: name, latitude, longitude, altitude_m.
    Altitude is in meters (as encoded by SD VFR).
    """
    tree = ET.parse(kml_path)
    root = tree.getroot()

    # Find the <Folder> named "Points"
    points_folder = None
    for folder in root.iter(f"{KML_NS}Folder"):
        name_el = folder.find(f"{KML_NS}name")
        if name_el is not None and name_el.text == "Points":
            points_folder = folder
            break

    if points_folder is None:
        raise ValueError("KML file does not contain a 'Points' folder")

    waypoints = []
    for pm in points_folder.findall(f"{KML_NS}Placemark"):
        name_el = pm.find(f"{KML_NS}name")
        point_el = pm.find(f"{KML_NS}Point")
        if name_el is None or point_el is None:
            continue

        coords_el = point_el.find(f"{KML_NS}coordinates")
        if coords_el is None or coords_el.text is None:
            continue

        # Format: "lon,lat,alt," (trailing comma from SD VFR)
        parts = coords_el.text.strip().rstrip(",").split(",")
        if len(parts) < 3:
            continue

        waypoints.append({
            "name": name_el.text.strip(),
            "longitude": float(parts[0]),
            "latitude": float(parts[1]),
            "altitude_m": float(parts[2]),
        })

    return waypoints


def build_route_from_kml(
    kml_path: Path,
    route_name: str,
    altitudes_ft: list[int],
) -> tuple[list[Waypoint], Route]:
    """Build SkyWeb Waypoint and Route objects from an SD VFR KML file.

    Args:
        kml_path: Path to the KML file.
        route_name: Name for the route (e.g. "LFXU-LFFU").
        altitudes_ft: Planned cruise altitude per leg in ft AMSL.
            Must have exactly N-1 entries for N waypoints.

    Returns:
        A tuple of (list of Waypoints, Route).
    """
    raw = parse_kml_waypoints(kml_path)
    n = len(raw)

    if len(altitudes_ft) != n - 1:
        raise ValueError(
            f"Expected {n - 1} altitudes for {n} waypoints, got {len(altitudes_ft)}"
        )

    # Build Waypoint objects
    waypoints = []
    for wp in raw:
        match = _ICAO_NAME_RE.match(wp["name"])
        waypoints.append(Waypoint(
            name=wp["name"],
            latitude=wp["latitude"],
            longitude=wp["longitude"],
            location_type=LocationType.AERODROME if match else LocationType.GPS_POINT,
            icao_code=match.group(1) if match else None,
        ))

    # Build RouteWaypointRef list
    refs = []
    for i, wp in enumerate(waypoints):
        if i == 0:
            role = WaypointRole.DEPARTURE
        elif i == n - 1:
            role = WaypointRole.ARRIVAL
        else:
            role = WaypointRole.ENROUTE

        refs.append(RouteWaypointRef(
            waypoint_id=wp.id,
            sequence_order=i + 1,
            role=role,
        ))

    # Build RouteLeg list
    legs = [
        RouteLeg(
            from_seq=i + 1,
            to_seq=i + 2,
            planned_altitude_ft=alt,
        )
        for i, alt in enumerate(altitudes_ft)
    ]

    route = Route(
        name=route_name,
        waypoints=refs,
        legs=legs,
    )

    return waypoints, route
