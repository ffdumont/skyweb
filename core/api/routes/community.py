"""Community data endpoints (VAC notes, TDP)."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException

from core.api.deps import get_community_repo, get_current_user
from core.persistence.repositories.community_repo import CommunityRepository

router = APIRouter(prefix="/community", tags=["community"])


@router.get("/vac-notes/{icao}")
async def get_vac_notes(
    icao: str,
    repo: CommunityRepository = Depends(get_community_repo),
) -> dict:
    data = await repo.get_vac_notes(icao.upper())
    if data is None:
        raise HTTPException(status_code=404, detail=f"No VAC notes for {icao}")
    return data


@router.put("/vac-notes/{icao}")
async def set_vac_notes(
    icao: str,
    notes: dict = Body(...),
    user_id: str = Depends(get_current_user),
    repo: CommunityRepository = Depends(get_community_repo),
) -> dict:
    await repo.set_vac_notes(icao.upper(), notes, user_id)
    return {"status": "ok", "icao": icao.upper()}


@router.get("/tdp/{icao}")
async def get_tdp(
    icao: str,
    repo: CommunityRepository = Depends(get_community_repo),
) -> dict:
    data = await repo.get_tdp(icao.upper())
    if data is None:
        raise HTTPException(status_code=404, detail=f"No TDP data for {icao}")
    return data
