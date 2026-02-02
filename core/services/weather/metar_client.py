"""NOAA Aviation Weather Center METAR client."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from core.contracts.enums import CloudCover
from core.contracts.weather import CloudLayer, ObservationData

BASE_URL = "https://aviationweather.gov/api/data/metar"


class MetarClient:
    """Async HTTP client for METAR observations."""

    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self._client = http_client or httpx.AsyncClient(timeout=15.0)

    async def get_current_metar(self, icao: str) -> ObservationData | None:
        """Fetch the most recent METAR for an ICAO code."""
        resp = await self._client.get(
            BASE_URL,
            params={"ids": icao.upper(), "format": "json"},
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        return _parse_metar(data[0])

    async def get_metar_at_time(
        self,
        icao: str,
        target_time: datetime,
        hours_before: int = 3,
    ) -> ObservationData | None:
        """Fetch the METAR closest to a target time."""
        resp = await self._client.get(
            BASE_URL,
            params={
                "ids": icao.upper(),
                "format": "json",
                "hours": hours_before,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None

        # Find closest observation to target_time
        best = None
        best_delta = None
        for entry in data:
            obs = _parse_metar(entry)
            delta = abs((obs.observation_time - target_time).total_seconds())
            if best_delta is None or delta < best_delta:
                best = obs
                best_delta = delta

        return best


def _parse_metar(raw: dict) -> ObservationData:
    """Parse a single NOAA METAR JSON entry into ObservationData."""
    obs_time_str = raw.get("reportTime", raw.get("obsTime", ""))
    try:
        obs_time = datetime.fromisoformat(obs_time_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        obs_time = datetime.now(tz=timezone.utc)

    # Parse cloud layers
    clouds: list[CloudLayer] = []
    for layer in raw.get("clouds", []):
        cover_str = layer.get("cover", "")
        base = layer.get("base")
        cover_map = {"CLR": CloudCover.CLR, "FEW": CloudCover.FEW, "SCT": CloudCover.SCT,
                     "BKN": CloudCover.BKN, "OVC": CloudCover.OVC}
        cover = cover_map.get(cover_str)
        if cover is not None and base is not None:
            clouds.append(CloudLayer(cover=cover, base_ft=base))

    # Ceiling: lowest BKN or OVC
    ceiling = None
    for cl in clouds:
        if cl.cover in (CloudCover.BKN, CloudCover.OVC):
            if ceiling is None or cl.base_ft < ceiling:
                ceiling = cl.base_ft

    return ObservationData(
        observation_time=obs_time,
        icao=raw.get("icaoId", raw.get("stationId", "ZZZZ")).upper(),
        wind_direction=raw.get("wdir"),
        wind_speed=raw.get("wspd"),
        wind_gust=raw.get("wgst"),
        temperature=raw.get("temp"),
        dewpoint=raw.get("dewp"),
        visibility=_parse_visibility(raw.get("visib")),
        ceiling=ceiling,
        clouds=clouds,
        flight_category=raw.get("fltcat"),
        altimeter=raw.get("altim"),
        raw_metar=raw.get("rawOb", ""),
    )


def _parse_visibility(visib) -> int | None:
    """Convert visibility to meters. NOAA returns statute miles."""
    if visib is None:
        return None
    try:
        sm = float(visib)
        return int(sm * 1609.34)  # statute miles to meters
    except (ValueError, TypeError):
        return None
