"""Elevation API client for ground-level lookups.

Uses Google Elevation API when GOOGLE_ELEVATION_API_KEY is set,
falls back to Open-Elevation (free, no key) otherwise.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

GOOGLE_ELEVATION_URL = "https://maps.googleapis.com/maps/api/elevation/json"
OPEN_ELEVATION_URL = "https://api.open-elevation.com/api/v1/lookup"
METERS_TO_FEET = 3.28084


async def get_ground_elevations(
    coordinates: list[tuple[float, float]],
) -> list[float | None]:
    """Query elevation API for ground elevations.

    Tries Google Elevation API first (if key available), then
    falls back to Open-Elevation (free, no key required).

    Parameters
    ----------
    coordinates:
        List of (latitude, longitude) tuples.

    Returns
    -------
    List of elevations in feet, or None for failed lookups.
    """
    if not coordinates:
        return []

    api_key = os.environ.get("GOOGLE_ELEVATION_API_KEY")
    if api_key:
        result = await _google_elevation(coordinates, api_key)
        # If Google returned at least one valid result, use it
        if any(r is not None for r in result):
            return result

    # Fallback to Open-Elevation
    return await _open_elevation(coordinates)


async def _google_elevation(
    coordinates: list[tuple[float, float]], api_key: str
) -> list[float | None]:
    """Query Google Elevation API."""
    locations = "|".join(f"{lat},{lon}" for lat, lon in coordinates)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                GOOGLE_ELEVATION_URL,
                params={"locations": locations, "key": api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "OK":
            error = data.get("error_message", data.get("status", "unknown"))
            logger.error("Google Elevation API error: %s", error)
            return [None] * len(coordinates)

        results: list[float | None] = []
        for i, (_lat, _lon) in enumerate(coordinates):
            entry = data["results"][i] if i < len(data["results"]) else None
            if entry and entry.get("elevation") is not None:
                results.append(round(entry["elevation"] * METERS_TO_FEET))
            else:
                results.append(None)
        return results

    except Exception:
        logger.exception("Google Elevation API request failed")
        return [None] * len(coordinates)


async def _open_elevation(
    coordinates: list[tuple[float, float]],
) -> list[float | None]:
    """Query Open-Elevation API (free, no key required).

    Sends a POST with up to 100 locations at a time.
    """
    all_results: list[float | None] = []
    batch_size = 100

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            for start in range(0, len(coordinates), batch_size):
                batch = coordinates[start : start + batch_size]
                payload = {
                    "locations": [
                        {"latitude": lat, "longitude": lon} for lat, lon in batch
                    ]
                }
                resp = await client.post(OPEN_ELEVATION_URL, json=payload)
                resp.raise_for_status()
                data = resp.json()

                for entry in data.get("results", []):
                    elev = entry.get("elevation")
                    if elev is not None:
                        all_results.append(round(elev * METERS_TO_FEET))
                    else:
                        all_results.append(None)

        return all_results

    except Exception:
        logger.exception("Open-Elevation API request failed")
        return [None] * len(coordinates)
