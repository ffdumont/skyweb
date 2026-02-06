"""API endpoints for user-specific aerodrome VAC notes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.api.deps import get_aerodrome_notes_repo, get_current_user_or_demo
from core.contracts.aerodrome_notes import AerodromeNotes, Obstacle
from core.persistence.repositories.aerodrome_notes_repo import AerodromeNotesRepository

router = APIRouter(prefix="/aerodrome-notes", tags=["aerodrome-notes"])


# ------------------------------------------------------------------
# Request/Response models
# ------------------------------------------------------------------


class AerodromeNotesResponse(BaseModel):
    """Response model for aerodrome notes."""

    icao: str
    runway_in_use: str | None = None
    circuit_direction: dict[str, str] | None = None
    pattern_altitude_ft: int | None = None
    entry_point: str | None = None
    exit_point: str | None = None
    special_procedures: str | None = None
    obstacles: list[Obstacle] = Field(default_factory=list)
    updated_at: str | None = None
    completion_status: str  # "empty", "partial", "complete"


class SaveAerodromeNotesRequest(BaseModel):
    """Request model for saving aerodrome notes."""

    runway_in_use: str | None = None
    circuit_direction: dict[str, str] | None = None
    pattern_altitude_ft: int | None = None
    entry_point: str | None = None
    exit_point: str | None = None
    special_procedures: str | None = None
    obstacles: list[Obstacle] = Field(default_factory=list)


def _to_response(notes: AerodromeNotes) -> AerodromeNotesResponse:
    """Convert domain model to response."""
    return AerodromeNotesResponse(
        icao=notes.icao,
        runway_in_use=notes.runway_in_use,
        circuit_direction=notes.circuit_direction,
        pattern_altitude_ft=notes.pattern_altitude_ft,
        entry_point=notes.entry_point,
        exit_point=notes.exit_point,
        special_procedures=notes.special_procedures,
        obstacles=notes.obstacles,
        updated_at=notes.updated_at.isoformat() if notes.updated_at else None,
        completion_status=notes.completion_status(),
    )


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("")
async def list_aerodrome_notes(
    user_id: str = Depends(get_current_user_or_demo),
    repo: AerodromeNotesRepository = Depends(get_aerodrome_notes_repo),
) -> list[AerodromeNotesResponse]:
    """List all aerodrome notes for the current user."""
    notes_list = await repo.list_all(user_id)
    return [_to_response(n) for n in notes_list]


@router.get("/{icao}")
async def get_aerodrome_notes(
    icao: str,
    user_id: str = Depends(get_current_user_or_demo),
    repo: AerodromeNotesRepository = Depends(get_aerodrome_notes_repo),
) -> AerodromeNotesResponse | None:
    """Get notes for a specific aerodrome.

    Returns null if no notes exist for this aerodrome.
    """
    notes = await repo.get_by_icao(user_id, icao)
    if notes is None:
        return None
    return _to_response(notes)


@router.get("/batch/{icao_codes}")
async def get_multiple_aerodrome_notes(
    icao_codes: str,
    user_id: str = Depends(get_current_user_or_demo),
    repo: AerodromeNotesRepository = Depends(get_aerodrome_notes_repo),
) -> dict[str, AerodromeNotesResponse]:
    """Get notes for multiple aerodromes.

    icao_codes is a comma-separated list, e.g. "LFXU,LFBP,LFBE"
    Returns a dict keyed by ICAO, only including aerodromes that have notes.
    """
    codes = [c.strip().upper() for c in icao_codes.split(",") if c.strip()]
    notes_dict = await repo.get_multiple(user_id, codes)
    return {icao: _to_response(notes) for icao, notes in notes_dict.items()}


@router.put("/{icao}")
async def save_aerodrome_notes(
    icao: str,
    request: SaveAerodromeNotesRequest,
    user_id: str = Depends(get_current_user_or_demo),
    repo: AerodromeNotesRepository = Depends(get_aerodrome_notes_repo),
) -> AerodromeNotesResponse:
    """Save or update notes for an aerodrome."""
    icao_upper = icao.upper()

    # Validate ICAO format
    if len(icao_upper) != 4 or not icao_upper.isalpha():
        raise HTTPException(status_code=400, detail="Invalid ICAO code format")

    notes = AerodromeNotes(
        icao=icao_upper,
        runway_in_use=request.runway_in_use,
        circuit_direction=request.circuit_direction,
        pattern_altitude_ft=request.pattern_altitude_ft,
        entry_point=request.entry_point,
        exit_point=request.exit_point,
        special_procedures=request.special_procedures,
        obstacles=request.obstacles,
        updated_at=datetime.now(timezone.utc),
    )

    await repo.save(user_id, notes)
    return _to_response(notes)


@router.delete("/{icao}")
async def delete_aerodrome_notes(
    icao: str,
    user_id: str = Depends(get_current_user_or_demo),
    repo: AerodromeNotesRepository = Depends(get_aerodrome_notes_repo),
) -> dict:
    """Delete notes for an aerodrome."""
    await repo.delete_by_icao(user_id, icao)
    return {"deleted": icao.upper()}
