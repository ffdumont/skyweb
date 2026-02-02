"""Weather simulation endpoints (stub — filled by Component 2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.api.deps import get_current_user, get_route_repo
from core.persistence.repositories.route_repo import RouteRepository

router = APIRouter(prefix="/routes/{route_id}/simulations", tags=["weather"])


@router.get("")
async def list_simulations(
    route_id: str,
    user_id: str = Depends(get_current_user),
    repo: RouteRepository = Depends(get_route_repo),
) -> list[dict]:
    sims = await repo.list_simulations(user_id, route_id)
    return [s.to_firestore() for s in sims]


@router.get("/{simulation_id}")
async def get_simulation(
    route_id: str,
    simulation_id: str,
    user_id: str = Depends(get_current_user),
    repo: RouteRepository = Depends(get_route_repo),
) -> dict:
    sim = await repo.get_simulation(user_id, route_id, simulation_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return sim.to_firestore()
