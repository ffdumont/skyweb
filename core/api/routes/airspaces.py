"""Airspace query endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from core.api.deps import get_airspace_query
from core.persistence.errors import SpatiaLiteNotReadyError
from core.persistence.spatialite.airspace_query import AirspaceQueryService

router = APIRouter(prefix="/airspaces", tags=["airspaces"])


@router.get("/bbox")
async def search_bbox(
    min_lat: float,
    min_lon: float,
    max_lat: float,
    max_lon: float,
    altitude_ft: int = 3000,
    svc: AirspaceQueryService = Depends(get_airspace_query),
) -> list[dict]:
    """Query airspaces within a bounding box at a given altitude."""
    try:
        results = await asyncio.to_thread(
            svc.query_segment_airspaces, min_lat, min_lon, max_lat, max_lon, altitude_ft
        )
        return [a.to_firestore() for a in results]
    except SpatiaLiteNotReadyError:
        return []
