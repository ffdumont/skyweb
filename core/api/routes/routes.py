"""Route CRUD + KML upload + airspace analysis endpoints."""

from __future__ import annotations

import asyncio
import math
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from pydantic import BaseModel

from core.api.deps import (
    get_airspace_query,
    get_current_user,
    get_current_user_or_demo,
    get_route_repo,
    get_waypoint_repo,
)
from core.contracts.enums import LocationType, WaypointRole, WaypointSource
from core.services.elevation import get_ground_elevations
from core.services.route_corrector import correct_route
from core.contracts.route import Route, RouteLeg, RouteWaypointRef
from core.contracts.waypoint import UserWaypoint
from core.persistence.repositories.route_repo import RouteRepository
from core.persistence.repositories.waypoint_repo import WaypointRepository
from core.persistence.errors import SpatiaLiteNotReadyError
from core.persistence.spatialite.airspace_query import AirspaceQueryService

KML_NS = "{http://www.opengis.net/kml/2.2}"

router = APIRouter(prefix="/routes", tags=["routes"])


@router.get("")
async def list_routes(
    user_id: str = Depends(get_current_user),
    repo: RouteRepository = Depends(get_route_repo),
) -> list[dict]:
    routes = await repo.list_all(user_id)
    return [r.to_firestore() for r in routes]


def _parse_kml_coords(text: str) -> dict | None:
    """Parse a single KML coordinate string 'lon,lat[,alt]' into a dict."""
    parts = text.strip().rstrip(",").split(",")
    if len(parts) < 2:
        return None
    return {
        "longitude": float(parts[0]),
        "latitude": float(parts[1]),
        "altitude_m": float(parts[2]) if len(parts) > 2 else 0.0,
    }


def _parse_linestring_kml(content: bytes) -> tuple[str, list[dict]]:
    """Parse a KML into a route name + list of waypoint dicts.

    Supports two formats:
    - Multiple Placemarks with <Point> (extracts name per waypoint)
    - Single Placemark with <LineString> (generic WPT names)
    """
    root = ET.fromstring(content)

    # Extract route name from Document
    route_name = "Imported Route"
    doc_el = root.find(f"{KML_NS}Document")
    if doc_el is not None:
        name_el = doc_el.find(f"{KML_NS}name")
        if name_el is not None and name_el.text:
            route_name = name_el.text.strip()

    # Try Placemarks with <Point> first (named waypoints)
    coords_list: list[dict] = []
    for pm in root.iter(f"{KML_NS}Placemark"):
        point_el = pm.find(f"{KML_NS}Point")
        if point_el is None:
            continue
        coords_el = point_el.find(f"{KML_NS}coordinates")
        if coords_el is None or coords_el.text is None:
            continue
        c = _parse_kml_coords(coords_el.text)
        if c is None:
            continue
        # Extract waypoint name
        name_el = pm.find(f"{KML_NS}name")
        c["name"] = name_el.text.strip() if name_el is not None and name_el.text else None
        coords_list.append(c)

    if len(coords_list) >= 2:
        # Fill in missing names
        for i, c in enumerate(coords_list):
            if not c.get("name"):
                c["name"] = f"WPT{i + 1}"
        return route_name, coords_list

    # Fallback: LineString coordinates (no waypoint names)
    coords_list = []
    for coords_el in root.iter(f"{KML_NS}coordinates"):
        if coords_el.text is None:
            continue
        for line in coords_el.text.strip().split():
            c = _parse_kml_coords(line)
            if c:
                c["name"] = f"WPT{len(coords_list) + 1}"
                coords_list.append(c)
        if coords_list:
            break

    return route_name, coords_list


@router.post("/upload", status_code=201)
async def upload_kml(
    file: UploadFile,
    user_id: str = Depends(get_current_user),
    route_repo: RouteRepository = Depends(get_route_repo),
) -> dict:
    """Upload a KML file and create a route.

    Supports both SD VFR format (Points folder) and simple LineString KML.
    Returns the route with resolved waypoint coordinates.
    """
    content = await file.read()

    # Try SD VFR parser first, fall back to simple LineString
    with tempfile.NamedTemporaryFile(suffix=".kml", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        try:
            from core.adapters.kml_parser import parse_kml_waypoints
            raw_wps = parse_kml_waypoints(tmp_path)
            # Extract route name from KML Document element
            root = ET.fromstring(content)
            doc_el = root.find(f"{KML_NS}Document")
            name_el = doc_el.find(f"{KML_NS}name") if doc_el is not None else None
            route_name = name_el.text.strip() if name_el is not None and name_el.text else tmp_path.stem
            coords_list = [
                {"name": w["name"], "longitude": w["longitude"], "latitude": w["latitude"], "altitude_m": w.get("altitude_m", 0)}
                for w in raw_wps
            ]
        except (ValueError, KeyError):
            route_name, coords_list = _parse_linestring_kml(content)
    finally:
        tmp_path.unlink(missing_ok=True)

    if len(coords_list) < 2:
        raise HTTPException(status_code=400, detail="KML must contain at least 2 points")

    # Ensure all waypoints have names
    for i, c in enumerate(coords_list):
        if not c.get("name"):
            c["name"] = f"WPT{i + 1}"

    # Get ground elevations for departure and arrival via Google Elevation API
    dep = coords_list[0]
    arr = coords_list[-1]
    elevations = await get_ground_elevations([
        (dep["latitude"], dep["longitude"]),
        (arr["latitude"], arr["longitude"]),
    ])
    dep_ground_ft = elevations[0]
    arr_ground_ft = elevations[1]

    # Apply route correction: altitude assignment + intermediate CLIMB/DESC waypoints
    corrected = correct_route(
        coords_list, dep_ground_ft=dep_ground_ft, arr_ground_ft=arr_ground_ft
    )

    # Build waypoint objects from corrected list
    waypoint_objects = []
    for cw in corrected:
        wp = UserWaypoint(
            name=cw.name,
            latitude=cw.latitude,
            longitude=cw.longitude,
            location_type=LocationType.GPS_POINT,
            source=WaypointSource.ROUTE_CORRECTION if cw.is_intermediate else WaypointSource.KML_IMPORT,
        )
        waypoint_objects.append(wp)

    # Build route refs and legs from corrected waypoints
    refs = [
        RouteWaypointRef(
            waypoint_id=wp.id,
            sequence_order=i + 1,
            role=(
                WaypointRole.DEPARTURE if i == 0
                else WaypointRole.ARRIVAL if i == len(waypoint_objects) - 1
                else WaypointRole.ENROUTE
            ),
        )
        for i, wp in enumerate(waypoint_objects)
    ]
    legs = []
    for i in range(len(waypoint_objects) - 1):
        alt_ft = max(corrected[i + 1].altitude_ft, 0)
        legs.append(RouteLeg(from_seq=i + 1, to_seq=i + 2, planned_altitude_ft=alt_ft))
    route = Route(name=route_name, waypoints=refs, legs=legs)
    route_id = await route_repo.save_with_waypoints(user_id, route, waypoint_objects)

    data = route.to_firestore()
    data["id"] = route_id
    data["coordinates"] = [
        {
            "lat": cw.latitude,
            "lon": cw.longitude,
            "name": cw.name,
            "altitude_ft": cw.altitude_ft,
            "is_intermediate": cw.is_intermediate,
        }
        for cw in corrected
    ]
    return data


# Demo KML path relative to project root (works locally and in Docker)
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DEMO_KML_PATH = _PROJECT_ROOT / "data" / "demo" / "LFXU-LFFU-2025-09-25-14-51-39.kml"


@router.post("/demo", status_code=201)
async def load_demo_route(
    route_repo: RouteRepository = Depends(get_route_repo),
    wp_repo: WaypointRepository = Depends(get_waypoint_repo),
) -> dict:
    """Load the hardcoded demo route KML file.

    This endpoint bypasses authentication and uses a fixed KML file for demo purposes.
    """
    if not DEMO_KML_PATH.exists():
        raise HTTPException(status_code=404, detail=f"Demo KML file not found: {DEMO_KML_PATH}")

    content = DEMO_KML_PATH.read_bytes()

    # Parse KML
    try:
        from core.adapters.kml_parser import parse_kml_waypoints
        raw_wps = parse_kml_waypoints(DEMO_KML_PATH)
        root = ET.fromstring(content)
        doc_el = root.find(f"{KML_NS}Document")
        name_el = doc_el.find(f"{KML_NS}name") if doc_el is not None else None
        route_name = name_el.text.strip() if name_el is not None and name_el.text else DEMO_KML_PATH.stem
        coords_list = [
            {"name": w["name"], "longitude": w["longitude"], "latitude": w["latitude"], "altitude_m": w.get("altitude_m", 0)}
            for w in raw_wps
        ]
    except (ValueError, KeyError):
        route_name, coords_list = _parse_linestring_kml(content)

    if len(coords_list) < 2:
        raise HTTPException(status_code=400, detail="Demo KML must contain at least 2 points")

    for i, c in enumerate(coords_list):
        if not c.get("name"):
            c["name"] = f"WPT{i + 1}"

    # Get ground elevations
    dep = coords_list[0]
    arr = coords_list[-1]
    elevations = await get_ground_elevations([
        (dep["latitude"], dep["longitude"]),
        (arr["latitude"], arr["longitude"]),
    ])
    dep_ground_ft = elevations[0]
    arr_ground_ft = elevations[1]

    # Apply route correction
    corrected = correct_route(
        coords_list, dep_ground_ft=dep_ground_ft, arr_ground_ft=arr_ground_ft
    )

    # Build waypoint objects
    waypoint_objects = []
    for cw in corrected:
        wp = UserWaypoint(
            name=cw.name,
            latitude=cw.latitude,
            longitude=cw.longitude,
            location_type=LocationType.GPS_POINT,
            source=WaypointSource.ROUTE_CORRECTION if cw.is_intermediate else WaypointSource.KML_IMPORT,
        )
        waypoint_objects.append(wp)

    # Build route refs and legs
    refs = [
        RouteWaypointRef(
            waypoint_id=wp.id,
            sequence_order=i + 1,
            role=(
                WaypointRole.DEPARTURE if i == 0
                else WaypointRole.ARRIVAL if i == len(waypoint_objects) - 1
                else WaypointRole.ENROUTE
            ),
        )
        for i, wp in enumerate(waypoint_objects)
    ]
    legs = []
    for i in range(len(waypoint_objects) - 1):
        alt_ft = max(corrected[i + 1].altitude_ft, 0)
        legs.append(RouteLeg(from_seq=i + 1, to_seq=i + 2, planned_altitude_ft=alt_ft))
    route = Route(name=route_name, waypoints=refs, legs=legs)

    # Save with demo user ID
    demo_user_id = "demo"
    route_id = await route_repo.save_with_waypoints(demo_user_id, route, waypoint_objects)

    data = route.to_firestore()
    data["id"] = route_id
    data["coordinates"] = [
        {
            "lat": cw.latitude,
            "lon": cw.longitude,
            "name": cw.name,
            "altitude_ft": cw.altitude_ft,
            "is_intermediate": cw.is_intermediate,
        }
        for cw in corrected
    ]
    return data


@router.get("/{route_id}")
async def get_route(
    route_id: str,
    user_id: str = Depends(get_current_user_or_demo),
    repo: RouteRepository = Depends(get_route_repo),
    wp_repo: WaypointRepository = Depends(get_waypoint_repo),
) -> dict:
    route = await repo.get(user_id, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")

    # Resolve waypoint coordinates
    wp_ids = [ref.waypoint_id for ref in route.waypoints]
    wp_map = await wp_repo.get_by_ids(user_id, wp_ids)

    # Build coordinates list in sequence order
    coordinates = []
    for ref in sorted(route.waypoints, key=lambda r: r.sequence_order):
        wp = wp_map.get(ref.waypoint_id)
        if wp:
            # Find altitude from legs
            alt_ft = 0
            for leg in route.legs:
                if leg.to_seq == ref.sequence_order:
                    alt_ft = leg.planned_altitude_ft
                    break
            coordinates.append({
                "lat": wp.latitude,
                "lon": wp.longitude,
                "name": wp.name,
                "altitude_ft": alt_ft,
                "is_intermediate": wp.source == WaypointSource.ROUTE_CORRECTION,
            })

    data = route.to_firestore()
    data["id"] = route_id
    data["coordinates"] = coordinates
    return data


@router.delete("/{route_id}", status_code=204, response_class=Response)
async def delete_route(
    route_id: str,
    user_id: str = Depends(get_current_user),
    repo: RouteRepository = Depends(get_route_repo),
) -> Response:
    await repo.delete(user_id, route_id)
    return Response(status_code=204)


@router.get("/{route_id}/ground-profile")
async def ground_profile(
    route_id: str,
    user_id: str = Depends(get_current_user_or_demo),
    route_repo: RouteRepository = Depends(get_route_repo),
    wp_repo: WaypointRepository = Depends(get_waypoint_repo),
) -> list[dict]:
    """Return sampled ground elevation profile along the route.

    Samples a point every ~2 NM along the great-circle path between
    waypoints, queries Google Elevation API, and returns
    [{distance_nm, elevation_ft}].
    """
    route = await route_repo.get(user_id, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")

    # Resolve waypoint coordinates
    wp_ids = [ref.waypoint_id for ref in route.waypoints]
    wp_map = await wp_repo.get_by_ids(user_id, wp_ids)

    coords: list[tuple[float, float]] = []
    for ref in sorted(route.waypoints, key=lambda r: r.sequence_order):
        wp = wp_map.get(ref.waypoint_id)
        if wp:
            coords.append((wp.latitude, wp.longitude))

    if len(coords) < 2:
        return []

    # Sample points every ~2 NM along the route
    SAMPLE_INTERVAL_NM = 2.0
    samples: list[tuple[float, float, float]] = []  # (lat, lon, cumulative_dist_nm)
    cum_dist = 0.0

    samples.append((coords[0][0], coords[0][1], 0.0))

    for i in range(1, len(coords)):
        lat1, lon1 = coords[i - 1]
        lat2, lon2 = coords[i]
        seg_dist = _haversine_nm_py(lat1, lon1, lat2, lon2)

        if seg_dist < 0.1:
            cum_dist += seg_dist
            continue

        # Walk along segment at fixed intervals
        d = SAMPLE_INTERVAL_NM - (cum_dist % SAMPLE_INTERVAL_NM) if cum_dist > 0 else SAMPLE_INTERVAL_NM
        if d > seg_dist:
            cum_dist += seg_dist
            continue

        walked = d
        while walked <= seg_dist:
            ratio = walked / seg_dist
            lat = lat1 + (lat2 - lat1) * ratio
            lon = lon1 + (lon2 - lon1) * ratio
            samples.append((lat, lon, cum_dist + walked))
            walked += SAMPLE_INTERVAL_NM

        cum_dist += seg_dist

    # Always include the last point
    if cum_dist > 0 and (not samples or abs(samples[-1][2] - cum_dist) > 0.1):
        samples.append((coords[-1][0], coords[-1][1], cum_dist))

    if len(samples) < 2:
        samples.append((coords[-1][0], coords[-1][1], cum_dist))

    # Query Google Elevation API
    sample_coords = [(s[0], s[1]) for s in samples]
    elevations = await get_ground_elevations(sample_coords)

    result = []
    for i, (lat, lon, dist) in enumerate(samples):
        elev = elevations[i] if i < len(elevations) else None
        if elev is not None:
            result.append({"distance_nm": round(dist, 1), "elevation_ft": elev})

    return result


def _haversine_nm_py(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in nautical miles (pure Python)."""
    la1, lo1 = math.radians(lat1), math.radians(lon1)
    la2, lo2 = math.radians(lat2), math.radians(lon2)
    dlat = la2 - la1
    dlon = lo2 - lo1
    a = math.sin(dlat / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlon / 2) ** 2
    return 2 * math.asin(math.sqrt(a)) * 3440.065


@router.get("/{route_id}/analysis")
async def analyze_route(
    route_id: str,
    user_id: str = Depends(get_current_user_or_demo),
    route_repo: RouteRepository = Depends(get_route_repo),
    wp_repo: WaypointRepository = Depends(get_waypoint_repo),
    airspace_svc: AirspaceQueryService = Depends(get_airspace_query),
) -> dict:
    """Perform airspace intersection analysis on a route."""
    route = await route_repo.get(user_id, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")

    # Resolve waypoint IDs to coordinates
    wp_ids = [ref.waypoint_id for ref in route.waypoints]
    wp_map = await wp_repo.get_by_ids(user_id, wp_ids)

    # Build tuples for analyze_route: (name, lat, lon) indexed by sequence_order
    waypoint_tuples: list[tuple[str, float, float]] = []
    for ref in sorted(route.waypoints, key=lambda r: r.sequence_order):
        wp = wp_map.get(ref.waypoint_id)
        if wp is None:
            raise HTTPException(
                status_code=400,
                detail=f"Waypoint {ref.waypoint_id} not found",
            )
        waypoint_tuples.append((wp.name, wp.latitude, wp.longitude))

    # Build leg tuples: (from_seq, to_seq, altitude_ft)
    leg_tuples = [
        (leg.from_seq, leg.to_seq, leg.planned_altitude_ft)
        for leg in route.legs
    ]

    # Run synchronous SpatiaLite query in thread pool
    try:
        leg_airspaces = await asyncio.to_thread(
            airspace_svc.analyze_route, waypoint_tuples, leg_tuples
        )
    except SpatiaLiteNotReadyError:
        return {
            "route_id": route_id,
            "legs": [],
            "analyzed_at": datetime.utcnow().isoformat(),
        }

    return {
        "route_id": route_id,
        "legs": [la.to_firestore() for la in leg_airspaces],
        "analyzed_at": datetime.utcnow().isoformat(),
    }


# ============ Altitude Override Models ============


class LegAltitudeOverride(BaseModel):
    """Override altitude for a single leg."""
    from_seq: int
    to_seq: int
    planned_altitude_ft: int


class AnalysisRequest(BaseModel):
    """Request body for analysis with altitude overrides."""
    legs: list[LegAltitudeOverride]


class RouteAltitudeUpdate(BaseModel):
    """Request body for saving altitude changes."""
    legs: list[LegAltitudeOverride]


@router.post("/{route_id}/analysis")
async def analyze_route_with_overrides(
    route_id: str,
    request: AnalysisRequest,
    user_id: str = Depends(get_current_user_or_demo),
    route_repo: RouteRepository = Depends(get_route_repo),
    wp_repo: WaypointRepository = Depends(get_waypoint_repo),
    airspace_svc: AirspaceQueryService = Depends(get_airspace_query),
) -> dict:
    """Perform airspace analysis with custom altitude overrides.

    This allows analyzing the route at different altitudes without
    saving the changes to the database.
    """
    route = await route_repo.get(user_id, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")

    # Resolve waypoint IDs to coordinates
    wp_ids = [ref.waypoint_id for ref in route.waypoints]
    wp_map = await wp_repo.get_by_ids(user_id, wp_ids)

    # Build tuples for analyze_route: (name, lat, lon) indexed by sequence_order
    waypoint_tuples: list[tuple[str, float, float]] = []
    for ref in sorted(route.waypoints, key=lambda r: r.sequence_order):
        wp = wp_map.get(ref.waypoint_id)
        if wp is None:
            raise HTTPException(
                status_code=400,
                detail=f"Waypoint {ref.waypoint_id} not found",
            )
        waypoint_tuples.append((wp.name, wp.latitude, wp.longitude))

    # Build leg tuples from request overrides
    leg_tuples = [
        (leg.from_seq, leg.to_seq, leg.planned_altitude_ft)
        for leg in request.legs
    ]

    # Run synchronous SpatiaLite query in thread pool
    try:
        leg_airspaces = await asyncio.to_thread(
            airspace_svc.analyze_route, waypoint_tuples, leg_tuples
        )
    except SpatiaLiteNotReadyError:
        return {
            "route_id": route_id,
            "legs": [],
            "analyzed_at": datetime.utcnow().isoformat(),
        }

    return {
        "route_id": route_id,
        "legs": [la.to_firestore() for la in leg_airspaces],
        "analyzed_at": datetime.utcnow().isoformat(),
    }


@router.patch("/{route_id}/altitudes")
async def update_route_altitudes(
    route_id: str,
    request: RouteAltitudeUpdate,
    user_id: str = Depends(get_current_user_or_demo),
    route_repo: RouteRepository = Depends(get_route_repo),
) -> dict:
    """Update the planned altitudes for route legs.

    This saves the altitude changes to Firestore.
    """
    route = await route_repo.get(user_id, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")

    # Build a map of altitude overrides by (from_seq, to_seq)
    override_map = {
        (leg.from_seq, leg.to_seq): leg.planned_altitude_ft
        for leg in request.legs
    }

    # Update route legs with new altitudes
    updated_legs = []
    for leg in route.legs:
        key = (leg.from_seq, leg.to_seq)
        if key in override_map:
            updated_legs.append(RouteLeg(
                from_seq=leg.from_seq,
                to_seq=leg.to_seq,
                planned_altitude_ft=override_map[key],
            ))
        else:
            updated_legs.append(leg)

    # Update route with new legs
    route.legs = updated_legs
    route.updated_at = datetime.utcnow()

    # Save to Firestore
    await route_repo.update(user_id, route_id, route)

    return {"status": "ok", "updated_legs": len(request.legs)}
