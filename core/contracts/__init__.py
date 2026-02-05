"""SkyWeb data contracts — Pydantic v2 models for VFR flight preparation.

Data authority
--------------

**Firestore** (source of truth for user-owned data):
- ``UserWaypoint`` — ``/users/{uid}/waypoints/{id}``
- ``Route`` — ``/users/{uid}/routes/{id}``
- ``Aircraft`` — ``/users/{uid}/aircraft/{id}``
- ``Dossier`` — ``/users/{uid}/dossiers/{id}``
- ``WeatherSimulation`` — ``/users/{uid}/dossiers/{did}/simulations/{id}``

**SQLite / SpatiaLite** (shared read-only reference data, updated per AIRAC cycle):
- ``AerodromeInfo`` — loaded from SIA XML, queried by ICAO code
- ``AirspaceIntersection`` / ``LegAirspaces`` — spatial queries on route geometry

**Cloud Storage** (binary artifacts, referenced by GCS path from Firestore docs):
- GPX files (``Track.gpx_ref``)
- KML files (``Route.source_kml_ref``)
- Preparation sheets (``Dossier.prep_sheet_ref``)
- NOTAM snapshots (``Dossier.notam_snapshot_ref``)

Calculated (never persisted)
----------------------------
- ``RouteProjection`` — full route projection with assumptions (API response DTO)
- ``RouteLeg`` computed fields — distance, heading, ETE per leg
- Weight & balance envelope check results
- VFR feasibility assessments
"""

from core.contracts.enums import (
    AerodromeStatus,
    AirspaceType,
    CloudCover,
    DossierStatus,
    ForecastModel,
    IntersectionType,
    LocationType,
    SectionCompletion,
    SectionId,
    TrackSource,
    VFRStatus,
    WaypointRole,
    WaypointSource,
)
from core.contracts.common import FirestoreModel, GeoPoint
from core.contracts.result import ServiceError, ServiceResult
from core.contracts.waypoint import UserWaypoint, Waypoint, waypoint_id
from core.contracts.route import (
    ProjectionAssumptions,
    Route,
    RouteLeg,
    RouteProjection,
    RouteWaypointRef,
)
from core.contracts.aircraft import (
    Aircraft,
    EnvelopePoint,
    FuelProfile,
    LoadingStation,
    StationType,
)
from core.contracts.dossier import Dossier, StationLoad, Track, WaypointPassageTime
from core.contracts.weather import (
    CloudLayer,
    ForecastData,
    ModelPoint,
    ModelResult,
    ObservationData,
    VFRIndex,
    WaypointContext,
    WeatherSimulation,
)
from core.contracts.airspace import (
    AirspaceIntersection,
    FrequencyInfo,
    RouteAirspaceAnalysis,
    LegAirspaces,
    ServiceInfo,
)
from core.contracts.aerodrome import (
    AerodromeFrequency,
    AerodromeInfo,
    AerodromeService,
    Runway,
)

__all__ = [
    # Enums
    "AerodromeStatus",
    "AirspaceType",
    "CloudCover",
    "DossierStatus",
    "ForecastModel",
    "IntersectionType",
    "LocationType",
    "SectionCompletion",
    "SectionId",
    "TrackSource",
    "VFRStatus",
    "WaypointRole",
    "WaypointSource",
    # Common
    "FirestoreModel",
    "GeoPoint",
    # Result
    "ServiceError",
    "ServiceResult",
    # Domain models
    "Waypoint",
    "UserWaypoint",
    "waypoint_id",
    "ProjectionAssumptions",
    "Route",
    "RouteLeg",
    "RouteProjection",
    "RouteWaypointRef",
    "Aircraft",
    "EnvelopePoint",
    "FuelProfile",
    "LoadingStation",
    "StationType",
    "Dossier",
    "StationLoad",
    "Track",
    "WaypointPassageTime",
    "CloudLayer",
    "ForecastData",
    "ModelPoint",
    "ModelResult",
    "ObservationData",
    "VFRIndex",
    "WaypointContext",
    "WeatherSimulation",
    "AirspaceIntersection",
    "FrequencyInfo",
    "RouteAirspaceAnalysis",
    "LegAirspaces",
    "ServiceInfo",
    "AerodromeFrequency",
    "AerodromeInfo",
    "AerodromeService",
    "Runway",
]
