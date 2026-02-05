"""Dossier CRUD + section updates + weather simulation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from core.api.deps import get_current_user, get_current_user_or_demo, get_dossier_repo
from core.contracts.enums import DossierStatus, SectionCompletion, SectionId
from core.contracts.dossier import Dossier
from core.contracts.weather import WeatherSimulation
from core.persistence.repositories.dossier_repo import DossierRepository

router = APIRouter(prefix="/dossiers", tags=["dossiers"])


@router.get("")
async def list_dossiers(
    status: DossierStatus | None = None,
    user_id: str = Depends(get_current_user),
    repo: DossierRepository = Depends(get_dossier_repo),
) -> list[dict]:
    if status is not None:
        items = await repo.list_by_status(user_id, status)
    else:
        items = await repo.list_all(user_id)
    return [d.to_firestore() for d in items]


@router.post("", status_code=201)
async def create_dossier(
    dossier: Dossier,
    user_id: str = Depends(get_current_user_or_demo),
    repo: DossierRepository = Depends(get_dossier_repo),
) -> dict:
    doc_id = await repo.create(user_id, dossier)
    data = dossier.to_firestore()
    data["id"] = doc_id
    return data


@router.get("/{dossier_id}")
async def get_dossier(
    dossier_id: str,
    user_id: str = Depends(get_current_user),
    repo: DossierRepository = Depends(get_dossier_repo),
) -> dict:
    item = await repo.get(user_id, dossier_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Dossier not found")
    data = item.to_firestore()
    data["id"] = dossier_id
    return data


@router.put("/{dossier_id}")
async def update_dossier(
    dossier_id: str,
    dossier: Dossier,
    user_id: str = Depends(get_current_user),
    repo: DossierRepository = Depends(get_dossier_repo),
) -> dict:
    await repo.update(user_id, dossier_id, dossier)
    data = dossier.to_firestore()
    data["id"] = dossier_id
    return data


@router.delete("/{dossier_id}", status_code=204, response_class=Response)
async def delete_dossier(
    dossier_id: str,
    user_id: str = Depends(get_current_user),
    repo: DossierRepository = Depends(get_dossier_repo),
) -> Response:
    await repo.delete(user_id, dossier_id)
    return Response(status_code=204)


# ------------------------------------------------------------------
# Section completion
# ------------------------------------------------------------------


@router.patch("/{dossier_id}/sections/{section}")
async def update_section(
    dossier_id: str,
    section: SectionId,
    completion: SectionCompletion,
    user_id: str = Depends(get_current_user),
    repo: DossierRepository = Depends(get_dossier_repo),
) -> dict:
    """Update the completion status of a single dossier section."""
    await repo.update_section(user_id, dossier_id, section, completion)
    return {"section": section.value, "completion": completion.value}


# ------------------------------------------------------------------
# Weather simulations (subcollection under dossier)
# ------------------------------------------------------------------


@router.get("/{dossier_id}/simulations")
async def list_simulations(
    dossier_id: str,
    user_id: str = Depends(get_current_user),
    repo: DossierRepository = Depends(get_dossier_repo),
) -> list[dict]:
    sims = await repo.list_simulations(user_id, dossier_id)
    return [s.to_firestore() for s in sims]


@router.post("/{dossier_id}/simulations", status_code=201)
async def create_simulation(
    dossier_id: str,
    simulation: WeatherSimulation,
    user_id: str = Depends(get_current_user),
    repo: DossierRepository = Depends(get_dossier_repo),
) -> dict:
    simulation.dossier_id = dossier_id
    sim_id = await repo.add_simulation(user_id, dossier_id, simulation)
    data = simulation.to_firestore()
    data["id"] = sim_id
    return data
