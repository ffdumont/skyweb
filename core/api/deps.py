"""FastAPI dependency injection wiring."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request

from core.api.auth import UserClaims, verify_firebase_token, verify_firebase_token_or_demo
from core.persistence.repositories.aircraft_repo import AircraftRepository
from core.persistence.repositories.community_repo import CommunityRepository
from core.persistence.repositories.dossier_repo import DossierRepository
from core.persistence.repositories.route_repo import RouteRepository
from core.persistence.repositories.waypoint_repo import WaypointRepository
from core.persistence.spatialite.aerodrome_query import AerodromeQueryService
from core.persistence.spatialite.airspace_query import AirspaceQueryService
from core.persistence.spatialite.db_manager import SpatiaLiteManager

if TYPE_CHECKING:
    pass


# ------------------------------------------------------------------
# Current user
# ------------------------------------------------------------------


def get_current_user(
    claims: UserClaims = Depends(verify_firebase_token),
) -> str:
    """Return the authenticated user ID."""
    return claims.uid


def get_current_user_or_demo(
    claims: UserClaims = Depends(verify_firebase_token_or_demo),
) -> str:
    """Return the user ID, allowing demo mode with X-Demo-Mode header."""
    return claims.uid


# ------------------------------------------------------------------
# Repositories (stateless — new instance per request is fine)
# ------------------------------------------------------------------


def get_waypoint_repo() -> WaypointRepository:
    return WaypointRepository()


def get_route_repo() -> RouteRepository:
    return RouteRepository()


def get_aircraft_repo() -> AircraftRepository:
    return AircraftRepository()


def get_dossier_repo() -> DossierRepository:
    return DossierRepository()


def get_community_repo() -> CommunityRepository:
    return CommunityRepository()


# ------------------------------------------------------------------
# SpatiaLite services (singleton from app.state)
# ------------------------------------------------------------------


def get_spatialite_manager(request: Request) -> SpatiaLiteManager:
    return request.app.state.spatialite_manager


def get_airspace_query(
    manager: SpatiaLiteManager = Depends(get_spatialite_manager),
) -> AirspaceQueryService:
    return AirspaceQueryService(manager)


def get_aerodrome_query(
    manager: SpatiaLiteManager = Depends(get_spatialite_manager),
) -> AerodromeQueryService:
    return AerodromeQueryService(manager)
