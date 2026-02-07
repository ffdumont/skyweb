"""Aerodrome lookup endpoints."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException

from core.api.deps import get_aerodrome_query
from core.persistence.errors import SpatiaLiteNotReadyError
from core.persistence.spatialite.aerodrome_query import AerodromeQueryService

logger = logging.getLogger(__name__)

# Lazy import for VAC URL generation (requires optional 'sia' dependencies)
_vac_module = None


def _get_vac_url(icao: str) -> str | None:
    """Generate VAC URL, returns None if dependencies not installed."""
    global _vac_module
    if _vac_module is None:
        try:
            from core.services import vac_downloader
            _vac_module = vac_downloader
        except ImportError:
            return None
    try:
        cycle = _vac_module.calculate_airac_cycle()
        return _vac_module.get_vac_url(icao, cycle)
    except Exception as e:
        logger.warning(f"Failed to generate VAC URL for {icao}: {e}")
        return None

router = APIRouter(prefix="/aerodromes", tags=["aerodromes"])


@router.get("/bbox")
async def search_bbox(
    min_lat: float,
    min_lon: float,
    max_lat: float,
    max_lon: float,
    svc: AerodromeQueryService = Depends(get_aerodrome_query),
) -> list[dict]:
    try:
        results = await asyncio.to_thread(svc.search_bbox, min_lat, min_lon, max_lat, max_lon)
        return [ad.to_firestore() for ad in results]
    except SpatiaLiteNotReadyError:
        return []


@router.get("/{icao}")
async def get_aerodrome(
    icao: str,
    svc: AerodromeQueryService = Depends(get_aerodrome_query),
) -> dict:
    try:
        result = await asyncio.to_thread(svc.get_by_icao, icao.upper())
    except SpatiaLiteNotReadyError:
        raise HTTPException(status_code=503, detail="SpatiaLite database not loaded")
    if result is None:
        raise HTTPException(status_code=404, detail=f"Aerodrome {icao} not found")

    # Add VAC URL for French aerodromes
    data = result.to_firestore()
    if result.icao.startswith("LF"):
        vac_url = _get_vac_url(result.icao)
        if vac_url:
            data["vac_url"] = vac_url

    return data
