"""Aerodrome lookup endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from core.api.deps import get_aerodrome_query
from core.persistence.errors import SpatiaLiteNotReadyError
from core.persistence.spatialite.aerodrome_query import AerodromeQueryService

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
    return result.to_firestore()
