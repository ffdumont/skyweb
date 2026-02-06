"""NOTAM API routes.

Provides endpoints to fetch NOTAMs for a route, including:
- Airport NOTAMs (departure, destination, alternates)
- FIR NOTAMs (for FIRs crossed by the route)
- En-route NOTAMs (geographic proximity to route)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from core.api.deps import (
    get_current_user_or_demo,
    get_route_repo,
    get_waypoint_repo,
)
from core.persistence.repositories.route_repo import RouteRepository
from core.persistence.repositories.waypoint_repo import WaypointRepository
from core.services.notam_service import NotamService, RouteWaypoint, RouteNotamResult, NotamData
from core.services.briefing_service import BriefingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notam", tags=["NOTAM"])

# Singleton service instances
_notam_service: NotamService | None = None
_briefing_service: BriefingService | None = None


def get_notam_service() -> NotamService:
    """Get or create the NOTAM service singleton."""
    global _notam_service
    if _notam_service is None:
        _notam_service = NotamService()
    return _notam_service


def get_briefing_service() -> BriefingService:
    """Get or create the briefing service singleton."""
    global _briefing_service
    if _briefing_service is None:
        _briefing_service = BriefingService()
    return _briefing_service


class NotamResponse(BaseModel):
    """Response model for route NOTAMs."""
    route_id: str
    departure_icao: str
    destination_icao: str
    alternate_icaos: list[str]
    firs_crossed: list[str]
    departure: list[NotamData]
    destination: list[NotamData]
    alternates: list[NotamData]
    firs: list[NotamData]
    enroute: list[NotamData]
    total_count: int
    fetched_at: datetime


class LocationNotamsResponse(BaseModel):
    """Response model for location-specific NOTAMs."""
    locations: list[str]
    notams: list[NotamData]
    total_count: int
    fetched_at: datetime


class BriefingRequest(BaseModel):
    """Request model for generating a NOTAM briefing."""
    departure_icao: str
    destination_icao: str
    departure: list[dict]
    destination: list[dict]
    firs: list[dict]
    enroute: list[dict]
    flight_date: str | None = None


class BriefingResponse(BaseModel):
    """Response model for NOTAM briefing."""
    briefing: str
    generated_at: datetime


@router.get("/{route_id}")
async def get_route_notams(
    route_id: str,
    alternate_icaos: str | None = None,
    buffer_nm: float = 10.0,
    flight_time: str | None = None,
    user_id: str = Depends(get_current_user_or_demo),
    route_repo: RouteRepository = Depends(get_route_repo),
    wp_repo: WaypointRepository = Depends(get_waypoint_repo),
    notam_svc: NotamService = Depends(get_notam_service),
) -> NotamResponse:
    """
    Get NOTAMs relevant to a route.

    Args:
        route_id: The route ID
        alternate_icaos: Comma-separated alternate airport ICAO codes
        buffer_nm: Buffer distance for en-route NOTAMs (default 10 NM)
        flight_time: ISO datetime for flight validity filter (default: now)

    Returns:
        NOTAMs categorized by departure, destination, alternates, FIRs, and en-route
    """
    # Load route
    route = await route_repo.get(user_id, route_id)
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route {route_id} not found",
        )

    # Load waypoints
    waypoints: list[RouteWaypoint] = []
    departure_icao = ""
    destination_icao = ""

    sorted_refs = sorted(route.waypoints, key=lambda r: r.sequence_order)
    for ref in sorted_refs:
        wp = await wp_repo.get(user_id, ref.waypoint_id)
        if not wp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Waypoint {ref.waypoint_id} not found",
            )
        waypoints.append(RouteWaypoint(name=wp.name, lat=wp.latitude, lon=wp.longitude))

        # Extract departure and destination ICAOs from waypoint names
        # Expected format: "LFXX - Airport Name" or just "LFXX"
        icao = _extract_icao(wp.name)
        if ref.sequence_order == 1 and icao:
            departure_icao = icao
        if ref.sequence_order == len(sorted_refs) and icao:
            destination_icao = icao

    # Parse alternate ICAOs
    alternates = []
    if alternate_icaos:
        alternates = [s.strip().upper() for s in alternate_icaos.split(",") if s.strip()]

    # Parse flight time if provided (ISO format), otherwise use current time
    effective_flight_time = datetime.now(timezone.utc)
    if flight_time:
        try:
            # Support both with and without timezone
            if flight_time.endswith("Z"):
                flight_time = flight_time[:-1] + "+00:00"
            elif "+" not in flight_time and "-" not in flight_time[-6:]:
                flight_time = flight_time + "+00:00"
            effective_flight_time = datetime.fromisoformat(flight_time)
        except ValueError:
            logger.warning(f"Invalid flight_time format: {flight_time}, using current time")

    # Get NOTAMs
    result = notam_svc.get_route_notams(
        waypoints=waypoints,
        departure_icao=departure_icao,
        destination_icao=destination_icao,
        alternate_icaos=alternates,
        buffer_nm=buffer_nm,
        flight_time=effective_flight_time,
    )

    return NotamResponse(
        route_id=route_id,
        departure_icao=departure_icao,
        destination_icao=destination_icao,
        alternate_icaos=alternates,
        firs_crossed=result.firs_crossed,
        departure=result.departure,
        destination=result.destination,
        alternates=result.alternates,
        firs=result.firs,
        enroute=result.enroute,
        total_count=result.total_count,
        fetched_at=datetime.now(timezone.utc),
    )


@router.get("/location/{icao_codes}")
async def get_location_notams(
    icao_codes: str,
    notam_svc: NotamService = Depends(get_notam_service),
) -> LocationNotamsResponse:
    """
    Get NOTAMs for specific ICAO locations.

    Args:
        icao_codes: Comma-separated ICAO codes (airports or FIRs)

    Returns:
        NOTAMs for the specified locations
    """
    locations = [s.strip().upper() for s in icao_codes.split(",") if s.strip()]
    if not locations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one ICAO code required",
        )

    notams = notam_svc.get_notams_for_locations(locations)

    return LocationNotamsResponse(
        locations=locations,
        notams=notams,
        total_count=len(notams),
        fetched_at=datetime.now(timezone.utc),
    )


def _extract_icao(name: str) -> str | None:
    """Extract ICAO code from waypoint name.

    Examples:
        "LFXU - LES MUREAUX" -> "LFXU"
        "LFPG" -> "LFPG"
        "PITHIVIERS" -> None
    """
    import re
    match = re.match(r"^([A-Z]{4})\b", name.strip().upper())
    return match.group(1) if match else None


@router.post("/briefing")
async def generate_briefing(
    request: BriefingRequest,
    briefing_svc: BriefingService = Depends(get_briefing_service),
) -> BriefingResponse:
    """
    Generate a human-readable NOTAM briefing in French using AI.

    Args:
        request: NOTAMs data and flight info

    Returns:
        AI-generated briefing in French
    """
    try:
        briefing = briefing_svc.generate_briefing(
            departure_icao=request.departure_icao,
            destination_icao=request.destination_icao,
            departure_notams=request.departure,
            destination_notams=request.destination,
            fir_notams=request.firs,
            enroute_notams=request.enroute,
            flight_date=request.flight_date,
        )

        return BriefingResponse(
            briefing=briefing,
            generated_at=datetime.now(timezone.utc),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Briefing generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate briefing",
        )
