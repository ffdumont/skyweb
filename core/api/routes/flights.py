"""Flight CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.api.deps import get_current_user, get_flight_repo
from core.contracts.enums import FlightStatus
from core.contracts.flight import Flight
from core.persistence.repositories.flight_repo import FlightRepository

router = APIRouter(prefix="/flights", tags=["flights"])


@router.get("")
async def list_flights(
    status: FlightStatus | None = None,
    user_id: str = Depends(get_current_user),
    repo: FlightRepository = Depends(get_flight_repo),
) -> list[dict]:
    if status is not None:
        items = await repo.list_by_status(user_id, status)
    else:
        items = await repo.list_all(user_id)
    return [f.to_firestore() for f in items]


@router.post("", status_code=201)
async def create_flight(
    flight: Flight,
    user_id: str = Depends(get_current_user),
    repo: FlightRepository = Depends(get_flight_repo),
) -> dict:
    doc_id = await repo.create(user_id, flight)
    data = flight.to_firestore()
    data["id"] = doc_id
    return data


@router.get("/{flight_id}")
async def get_flight(
    flight_id: str,
    user_id: str = Depends(get_current_user),
    repo: FlightRepository = Depends(get_flight_repo),
) -> dict:
    item = await repo.get(user_id, flight_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Flight not found")
    data = item.to_firestore()
    data["id"] = flight_id
    return data


@router.put("/{flight_id}")
async def update_flight(
    flight_id: str,
    flight: Flight,
    user_id: str = Depends(get_current_user),
    repo: FlightRepository = Depends(get_flight_repo),
) -> dict:
    await repo.update(user_id, flight_id, flight)
    data = flight.to_firestore()
    data["id"] = flight_id
    return data


@router.delete("/{flight_id}", status_code=204)
async def delete_flight(
    flight_id: str,
    user_id: str = Depends(get_current_user),
    repo: FlightRepository = Depends(get_flight_repo),
) -> None:
    await repo.delete(user_id, flight_id)
