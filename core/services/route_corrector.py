"""Route correction: altitude assignment + intermediate CLIMB/DESC waypoints.

Ported from skytools/skypath/skypath_services/route_corrector.
Uses Google Elevation API for DEP/ARR ground elevation when available,
falls back to KML altitudes otherwise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


EARTH_RADIUS_NM = 3440.065
METERS_TO_FEET = 3.28084

# Defaults (matching SkyPath config)
DEFAULT_CLIMB_RATE_FPM = 500
DEFAULT_GROUND_SPEED_KT = 100
DEFAULT_MIN_ALT_FT = 1000  # minimum altitude for DEP/ARR when KML altitude is ~0
DEFAULT_PATTERN_ALT_FT = 1000  # altitude above ground for DEP/ARR (TDP)


@dataclass
class CorrectedWaypoint:
    """A waypoint with corrected altitude and metadata."""

    name: str
    latitude: float
    longitude: float
    altitude_ft: float
    altitude_source: str  # "departure" | "segment" | "arrival" | "intermediate_climb" | "intermediate_desc"
    is_intermediate: bool = False
    original_altitude_m: float = 0.0


def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in nautical miles."""
    la1, lo1 = math.radians(lat1), math.radians(lon1)
    la2, lo2 = math.radians(lat2), math.radians(lon2)
    dlat = la2 - la1
    dlon = lo2 - lo1
    a = math.sin(dlat / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlon / 2) ** 2
    return 2 * math.asin(math.sqrt(a)) * EARTH_RADIUS_NM


def correct_route(
    waypoints: list[dict],
    *,
    dep_ground_ft: float | None = None,
    arr_ground_ft: float | None = None,
    climb_rate_fpm: int = DEFAULT_CLIMB_RATE_FPM,
    ground_speed_kt: int = DEFAULT_GROUND_SPEED_KT,
    pattern_alt_ft: int = DEFAULT_PATTERN_ALT_FT,
    min_alt_ft: int = DEFAULT_MIN_ALT_FT,
) -> list[CorrectedWaypoint]:
    """Apply altitude correction and insert intermediate CLIMB/DESC waypoints.

    KML altitudes are treated as planned flight altitudes for enroute waypoints.
    For DEP/ARR, ground elevation from Google Elevation API is used when
    available (altitude = ground + pattern_alt_ft). Otherwise falls back to
    the KML altitude directly, with a minimum floor applied.

    Parameters
    ----------
    waypoints:
        List of dicts with keys: name, latitude, longitude, altitude_m.
        Ordered from departure to arrival.
    dep_ground_ft:
        Ground elevation at departure in feet (from Google Elevation API).
        None if unavailable.
    arr_ground_ft:
        Ground elevation at arrival in feet (from Google Elevation API).
        None if unavailable.
    climb_rate_fpm:
        Climb/descent rate in feet per minute.
    ground_speed_kt:
        Ground speed in knots (used to compute horizontal distance during climb/desc).
    pattern_alt_ft:
        Altitude above ground elevation for DEP/ARR when ground is known.
    min_alt_ft:
        Minimum altitude for DEP/ARR when KML altitude is near zero and no
        ground elevation is available.

    Returns
    -------
    List of CorrectedWaypoint including any inserted intermediate points.
    """
    if len(waypoints) < 2:
        return []

    # --- Step 1: Build base corrected waypoints ---
    base = _assign_altitudes(
        waypoints, dep_ground_ft, arr_ground_ft, pattern_alt_ft, min_alt_ft
    )

    # --- Step 2: Insert intermediate CLIMB/DESC waypoints ---
    return _insert_intermediates(base, climb_rate_fpm, ground_speed_kt)


def _assign_altitudes(
    waypoints: list[dict],
    dep_ground_ft: float | None,
    arr_ground_ft: float | None,
    pattern_alt_ft: int,
    min_alt_ft: int,
) -> list[CorrectedWaypoint]:
    """Assign corrected altitudes.

    - DEP/ARR: ground elevation + pattern_alt_ft when ground is known,
      otherwise KML altitude (with min_alt_ft floor).
    - Enroute: KML altitude directly (planned flight altitude).
    """
    result: list[CorrectedWaypoint] = []

    for i, wp in enumerate(waypoints):
        alt_m = wp.get("altitude_m", 0.0)
        alt_ft = alt_m * METERS_TO_FEET

        if i == 0:
            source = "departure"
            if dep_ground_ft is not None:
                alt_ft = dep_ground_ft + pattern_alt_ft
            elif alt_ft < 50:
                alt_ft = min_alt_ft
        elif i == len(waypoints) - 1:
            source = "arrival"
            if arr_ground_ft is not None:
                alt_ft = arr_ground_ft + pattern_alt_ft
            elif alt_ft < 50:
                alt_ft = min_alt_ft
        else:
            source = "segment"

        result.append(
            CorrectedWaypoint(
                name=wp["name"],
                latitude=wp["latitude"],
                longitude=wp["longitude"],
                altitude_ft=round(alt_ft),
                altitude_source=source,
                original_altitude_m=alt_m,
            )
        )

    return result


def _insert_intermediates(
    base: list[CorrectedWaypoint],
    climb_rate_fpm: int,
    ground_speed_kt: int,
) -> list[CorrectedWaypoint]:
    """Insert intermediate CLIMB/DESC waypoints between base waypoints."""
    if len(base) < 2:
        return list(base)

    enhanced: list[CorrectedWaypoint] = []

    for i, wp in enumerate(base):
        enhanced.append(wp)

        if i >= len(base) - 1:
            continue

        next_wp = base[i + 1]
        is_last_segment = i == len(base) - 2

        # Determine target altitude for intermediate
        if is_last_segment:
            target_alt = wp.altitude_ft
        else:
            target_alt = next_wp.altitude_ft

        intermediate = _calc_intermediate(
            wp, next_wp, target_alt, is_last_segment, climb_rate_fpm, ground_speed_kt
        )
        if intermediate is not None:
            enhanced.append(intermediate)

    return enhanced


def _calc_intermediate(
    start: CorrectedWaypoint,
    end: CorrectedWaypoint,
    target_alt: float,
    is_last_segment: bool,
    climb_rate_fpm: int,
    ground_speed_kt: int,
) -> CorrectedWaypoint | None:
    """Calculate an intermediate waypoint for altitude transition.

    Returns None if altitude change < 100 ft or climb distance >= segment distance.
    """
    alt_diff = abs(end.altitude_ft - start.altitude_ft)
    if alt_diff < 100:
        return None

    # Time and distance for altitude change
    time_min = alt_diff / climb_rate_fpm
    climb_dist_nm = (ground_speed_kt * time_min) / 60

    total_dist_nm = _haversine_nm(start.latitude, start.longitude, end.latitude, end.longitude)
    if climb_dist_nm >= total_dist_nm:
        return None

    # Position ratio along segment
    if is_last_segment:
        ratio = 1.0 - (climb_dist_nm / total_dist_nm)
    else:
        ratio = climb_dist_nm / total_dist_nm

    # Linear interpolation
    lat = start.latitude + (end.latitude - start.latitude) * ratio
    lon = start.longitude + (end.longitude - start.longitude) * ratio

    direction = "CLIMB" if end.altitude_ft > start.altitude_ft else "DESC"

    if is_last_segment and direction == "DESC":
        name = f"{direction}_{int(end.altitude_ft)}"
    else:
        name = f"{direction}_{int(target_alt)}"

    return CorrectedWaypoint(
        name=name,
        latitude=lat,
        longitude=lon,
        altitude_ft=round(target_alt),
        altitude_source=f"intermediate_{direction.lower()}",
        is_intermediate=True,
        original_altitude_m=target_alt / METERS_TO_FEET,
    )
