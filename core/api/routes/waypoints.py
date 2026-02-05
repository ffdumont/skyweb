"""Waypoint CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from core.api.deps import get_current_user, get_waypoint_repo
from core.contracts.waypoint import UserWaypoint
from core.persistence.repositories.waypoint_repo import WaypointRepository

router = APIRouter(prefix="/waypoints", tags=["waypoints"])


@router.get("")
async def list_waypoints(
    user_id: str = Depends(get_current_user),
    repo: WaypointRepository = Depends(get_waypoint_repo),
) -> list[dict]:
    waypoints = await repo.list_all(user_id)
    return [wp.to_firestore() for wp in waypoints]


@router.post("", status_code=201)
async def create_waypoint(
    waypoint: UserWaypoint,
    user_id: str = Depends(get_current_user),
    repo: WaypointRepository = Depends(get_waypoint_repo),
) -> dict:
    doc_id = await repo.create(user_id, waypoint)
    data = waypoint.to_firestore()
    data["id"] = doc_id
    return data


@router.get("/search")
async def search_by_tag(
    tag: str,
    user_id: str = Depends(get_current_user),
    repo: WaypointRepository = Depends(get_waypoint_repo),
) -> list[dict]:
    waypoints = await repo.find_by_tag(user_id, tag)
    return [wp.to_firestore() for wp in waypoints]


@router.get("/{waypoint_id}")
async def get_waypoint(
    waypoint_id: str,
    user_id: str = Depends(get_current_user),
    repo: WaypointRepository = Depends(get_waypoint_repo),
) -> dict:
    wp = await repo.get(user_id, waypoint_id)
    if wp is None:
        raise HTTPException(status_code=404, detail="Waypoint not found")
    data = wp.to_firestore()
    data["id"] = waypoint_id
    return data


@router.delete("/{waypoint_id}", status_code=204, response_class=Response)
async def delete_waypoint(
    waypoint_id: str,
    user_id: str = Depends(get_current_user),
    repo: WaypointRepository = Depends(get_waypoint_repo),
) -> Response:
    await repo.delete(user_id, waypoint_id)
    return Response(status_code=204)
