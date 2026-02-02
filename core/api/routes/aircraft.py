"""Aircraft CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.api.deps import get_aircraft_repo, get_current_user
from core.contracts.aircraft import Aircraft
from core.persistence.repositories.aircraft_repo import AircraftRepository

router = APIRouter(prefix="/aircraft", tags=["aircraft"])


@router.get("")
async def list_aircraft(
    user_id: str = Depends(get_current_user),
    repo: AircraftRepository = Depends(get_aircraft_repo),
) -> list[dict]:
    items = await repo.list_all(user_id)
    return [a.to_firestore() for a in items]


@router.post("", status_code=201)
async def create_aircraft(
    aircraft: Aircraft,
    user_id: str = Depends(get_current_user),
    repo: AircraftRepository = Depends(get_aircraft_repo),
) -> dict:
    doc_id = await repo.create(user_id, aircraft)
    data = aircraft.to_firestore()
    data["id"] = doc_id
    return data


@router.get("/{aircraft_id}")
async def get_aircraft(
    aircraft_id: str,
    user_id: str = Depends(get_current_user),
    repo: AircraftRepository = Depends(get_aircraft_repo),
) -> dict:
    item = await repo.get(user_id, aircraft_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    data = item.to_firestore()
    data["id"] = aircraft_id
    return data


@router.put("/{aircraft_id}")
async def update_aircraft(
    aircraft_id: str,
    aircraft: Aircraft,
    user_id: str = Depends(get_current_user),
    repo: AircraftRepository = Depends(get_aircraft_repo),
) -> dict:
    await repo.update(user_id, aircraft_id, aircraft)
    data = aircraft.to_firestore()
    data["id"] = aircraft_id
    return data


@router.delete("/{aircraft_id}", status_code=204)
async def delete_aircraft(
    aircraft_id: str,
    user_id: str = Depends(get_current_user),
    repo: AircraftRepository = Depends(get_aircraft_repo),
) -> None:
    await repo.delete(user_id, aircraft_id)
