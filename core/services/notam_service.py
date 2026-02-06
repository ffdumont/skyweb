"""NOTAM service for fetching and filtering NOTAMs along a route.

Uses ICAO Data Services API to fetch NOTAMs for France and filters them
by airport, FIR, and geographic proximity to the route.
"""

from __future__ import annotations

import os
import re
import math
import logging
import httpx
from datetime import datetime, timezone
from dataclasses import dataclass
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ICAO API Configuration
ICAO_API_KEY = os.getenv("ICAO_API_KEY", "")
ICAO_BASE_URL = "https://v4p4sz5ijk.execute-api.us-east-1.amazonaws.com/anbdata/states/notams"

# French FIRs with approximate boundaries
FRENCH_FIRS = {
    "LFFF": {"name": "Paris", "lat_min": 46.5, "lat_max": 50.0, "lon_min": 0.0, "lon_max": 5.5},
    "LFMM": {"name": "Marseille", "lat_min": 42.0, "lat_max": 46.5, "lon_min": 3.0, "lon_max": 7.5},
    "LFBB": {"name": "Bordeaux", "lat_min": 43.0, "lat_max": 47.0, "lon_min": -2.0, "lon_max": 3.0},
    "LFRR": {"name": "Brest", "lat_min": 46.0, "lat_max": 50.0, "lon_min": -6.0, "lon_max": 0.0},
    "LFEE": {"name": "Reims", "lat_min": 48.0, "lat_max": 51.0, "lon_min": 3.0, "lon_max": 8.0},
}


class NotamData(BaseModel):
    """Parsed NOTAM data."""
    id: str
    raw: str
    q_code: str | None = None
    area: str | None = None
    sub_area: str | None = None
    subject: str | None = None
    modifier: str | None = None
    message: str | None = None
    location: str | None = None
    fir: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_nm: int | None = None


class RouteNotamResult(BaseModel):
    """Result of route NOTAM analysis."""
    departure: list[NotamData] = []
    destination: list[NotamData] = []
    alternates: list[NotamData] = []
    firs: list[NotamData] = []
    enroute: list[NotamData] = []
    firs_crossed: list[str] = []

    @property
    def total_count(self) -> int:
        return (
            len(self.departure) + len(self.destination) +
            len(self.alternates) + len(self.firs) + len(self.enroute)
        )


@dataclass
class RouteWaypoint:
    """A waypoint on the route."""
    name: str
    lat: float
    lon: float


def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in nautical miles."""
    R = 3440.065
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _point_to_segment_distance_nm(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """Calculate minimum distance from point to line segment in NM."""
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    ab_sq = abx * abx + aby * aby
    if ab_sq == 0:
        return _haversine_nm(px, py, ax, ay)
    t = max(0, min(1, (apx * abx + apy * aby) / ab_sq))
    return _haversine_nm(px, py, ax + t * abx, ay + t * aby)


def _point_to_route_distance_nm(lat: float, lon: float, waypoints: list[RouteWaypoint]) -> float:
    """Calculate minimum distance from a point to any segment of the route."""
    if len(waypoints) < 2:
        return _haversine_nm(lat, lon, waypoints[0].lat, waypoints[0].lon) if waypoints else float('inf')
    return min(
        _point_to_segment_distance_nm(lat, lon, waypoints[i].lat, waypoints[i].lon, waypoints[i+1].lat, waypoints[i+1].lon)
        for i in range(len(waypoints) - 1)
    )


def _parse_notam_coordinates(raw: str) -> tuple[float, float, int] | None:
    """Extract coordinates and radius from NOTAM.

    Tries multiple formats:
    1. Q-line format: 4734N00036E005 (DDMM N DDDMM E RRR)
    2. PSN format: 473450N 0003618E (DDMMSS N DDDMMSS E) - no radius
    """
    # Try Q-line format first (includes radius)
    match = re.search(r'(\d{4})([NS])(\d{5})([EW])(\d{3})', raw)
    if match:
        lat_str, lat_dir, lon_str, lon_dir, radius_str = match.groups()
        lat = int(lat_str[:2]) + int(lat_str[2:4]) / 60
        lon = int(lon_str[:3]) + int(lon_str[3:5]) / 60
        if lat_dir == 'S':
            lat = -lat
        if lon_dir == 'W':
            lon = -lon
        return (lat, lon, int(radius_str))

    # Try PSN format (6 digits for lat with seconds, 7 digits for lon with seconds)
    # Pattern: 473450N 0003618E or 473450N0003618E
    psn_match = re.search(r'(\d{6})([NS])\s*(\d{7})([EW])', raw)
    if psn_match:
        lat_str, lat_dir, lon_str, lon_dir = psn_match.groups()
        # DDMMSS format
        lat = int(lat_str[:2]) + int(lat_str[2:4]) / 60 + int(lat_str[4:6]) / 3600
        lon = int(lon_str[:3]) + int(lon_str[3:5]) / 60 + int(lon_str[5:7]) / 3600
        if lat_dir == 'S':
            lat = -lat
        if lon_dir == 'W':
            lon = -lon
        # No radius in PSN format, default to 5 NM
        return (lat, lon, 5)

    return None


def _determine_firs(waypoints: list[RouteWaypoint]) -> list[str]:
    """Determine which FIRs a route passes through."""
    firs = set()
    for wp in waypoints:
        for fir_code, bounds in FRENCH_FIRS.items():
            if (bounds["lat_min"] <= wp.lat <= bounds["lat_max"] and
                bounds["lon_min"] <= wp.lon <= bounds["lon_max"]):
                firs.add(fir_code)
    return list(firs)


def _parse_notam(data: dict) -> NotamData:
    """Parse raw API response into NotamData."""
    raw = data.get("all", "")

    # Extract location from A) line
    location_match = re.search(r"A\)\s*([A-Z]{4})", raw)
    location = location_match.group(1) if location_match else None

    # Extract FIR from Q) line
    fir_match = re.search(r"Q\)\s*([A-Z]{4})", raw)
    fir = fir_match.group(1) if fir_match else None

    # Parse dates
    start_date = end_date = None
    if data.get("startdate"):
        try:
            start_date = datetime.fromisoformat(data["startdate"].replace("Z", "+00:00"))
        except ValueError:
            pass
    if data.get("enddate"):
        try:
            end_date = datetime.fromisoformat(data["enddate"].replace("Z", "+00:00"))
        except ValueError:
            pass

    # Parse coordinates
    coords = _parse_notam_coordinates(raw)
    lat, lon, radius = coords if coords else (None, None, None)

    return NotamData(
        id=data.get("id", ""),
        raw=raw,
        q_code=data.get("Qcode"),
        area=data.get("Area"),
        sub_area=data.get("SubArea"),
        subject=data.get("Subject"),
        modifier=data.get("Modifier"),
        message=data.get("message"),
        location=location,
        fir=fir,
        start_date=start_date,
        end_date=end_date,
        latitude=lat,
        longitude=lon,
        radius_nm=radius,
    )


class NotamService:
    """Service for fetching NOTAMs from ICAO API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or ICAO_API_KEY
        self._cache: dict[str, tuple[list[dict], datetime]] = {}
        self._cache_ttl_seconds = 3600  # 1 hour cache

    def _get_cached_notams(self, state: str = "FRA") -> list[dict]:
        """Get NOTAMs from cache or fetch from API."""
        cache_key = f"state:{state}"
        now = datetime.now(timezone.utc)

        # Check cache
        if cache_key in self._cache:
            data, cached_at = self._cache[cache_key]
            if (now - cached_at).total_seconds() < self._cache_ttl_seconds:
                logger.debug(f"Using cached NOTAMs for {state} ({len(data)} items)")
                return data

        # Fetch from API
        if not self.api_key:
            logger.warning("No ICAO API key configured")
            return []

        try:
            response = httpx.get(
                f"{ICAO_BASE_URL}/notams-list",
                params={"api_key": self.api_key, "format": "json", "states": state},
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            self._cache[cache_key] = (data, now)
            logger.info(f"Fetched {len(data)} NOTAMs for {state}")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch NOTAMs: {e}")
            return []

    def get_notams_for_locations(self, icao_codes: list[str]) -> list[NotamData]:
        """Get NOTAMs for specific ICAO locations."""
        all_notams = self._get_cached_notams()
        pattern = r"A\)\s*(" + "|".join(re.escape(code) for code in icao_codes) + r")\b"
        return [_parse_notam(n) for n in all_notams if re.search(pattern, n.get("all", ""))]

    def get_route_notams(
        self,
        waypoints: list[RouteWaypoint],
        departure_icao: str,
        destination_icao: str,
        alternate_icaos: list[str] | None = None,
        buffer_nm: float = 10.0,
        flight_time: datetime | None = None,
    ) -> RouteNotamResult:
        """Get NOTAMs relevant to a flight route."""
        if flight_time is None:
            flight_time = datetime.now(timezone.utc)

        alternate_icaos = alternate_icaos or []
        firs = _determine_firs(waypoints)

        # Get airport and FIR NOTAMs
        all_locations = [departure_icao, destination_icao] + alternate_icaos + firs
        location_notams = self.get_notams_for_locations(all_locations)

        # Helper to check if a NOTAM with coordinates is near the route
        def is_near_route(n: NotamData, buffer: float) -> bool | None:
            """Returns True if near, False if far, None if no coordinates."""
            if n.latitude is None or n.longitude is None:
                return None  # No coordinates = can't determine
            dist = _point_to_route_distance_nm(n.latitude, n.longitude, waypoints)
            radius = n.radius_nm or 0
            return dist <= buffer + radius

        # Track seen IDs to prevent duplicates
        seen_ids: set[str] = set()

        def add_unique(notam: NotamData, target: list[NotamData]) -> None:
            if notam.id not in seen_ids:
                seen_ids.add(notam.id)
                target.append(notam)

        # Categorize - airport NOTAMs don't need geographic filtering
        departure: list[NotamData] = []
        destination: list[NotamData] = []
        alternates: list[NotamData] = []
        fir_notams: list[NotamData] = []

        for n in location_notams:
            if n.location == departure_icao:
                add_unique(n, departure)
            elif n.location == destination_icao:
                add_unique(n, destination)
            elif n.location in alternate_icaos:
                add_unique(n, alternates)
            elif n.location in firs:
                # FIR NOTAMs: filter geographically if they have coordinates
                # Use a larger buffer (25 NM)
                near = is_near_route(n, max(buffer_nm, 25.0))
                if near is True or near is None:  # Include if near OR no coordinates
                    add_unique(n, fir_notams)

        # Find geographic NOTAMs near route (en-route)
        # Only include NOTAMs WITH coordinates that are near the route
        all_french = self._get_cached_notams()
        enroute: list[NotamData] = []

        for raw_notam in all_french:
            notam = _parse_notam(raw_notam)
            if notam.id in seen_ids:
                continue
            # For en-route, REQUIRE coordinates and proximity check
            near = is_near_route(notam, buffer_nm)
            if near is True:  # Must have coordinates AND be near
                add_unique(notam, enroute)

        # Filter by validity
        def is_active(n: NotamData) -> bool:
            if n.start_date and n.start_date > flight_time:
                return False
            if n.end_date and n.end_date < flight_time:
                return False
            return True

        return RouteNotamResult(
            departure=[n for n in departure if is_active(n)],
            destination=[n for n in destination if is_active(n)],
            alternates=[n for n in alternates if is_active(n)],
            firs=[n for n in fir_notams if is_active(n)],
            enroute=[n for n in enroute if is_active(n)],
            firs_crossed=firs,
        )
