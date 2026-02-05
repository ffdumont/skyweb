"""Dossier de Navigation — a flight preparation folder.

Stored at: ``/users/{user_id}/dossiers/{dossier_id}``
"""

from datetime import datetime, timezone

from pydantic import Field

from core.contracts.common import FirestoreModel
from core.contracts.enums import DossierStatus, SectionCompletion, SectionId, TrackSource


def _default_sections() -> dict[str, str]:
    """Return all sections initialized to 'empty'."""
    return {s.value: SectionCompletion.EMPTY.value for s in SectionId}


class WaypointPassageTime(FirestoreModel):
    """Actual passage time at a waypoint, derived from GPX track snap."""

    waypoint_id: str
    sequence_order: int
    passage_time_utc: datetime
    latitude: float | None = None
    longitude: float | None = None


class Track(FirestoreModel):
    """A real GPS trace (GPX) associated to a dossier.

    Contains passage times snapped to route waypoints.
    """

    gpx_ref: str | None = Field(default=None, description="GCS path to the GPX file")
    source: TrackSource = TrackSource.GPX_FILE
    passage_times: list[WaypointPassageTime] = Field(default_factory=list)
    recorded_at: datetime | None = None
    total_distance_nm: float | None = Field(default=None, ge=0)
    total_time_minutes: float | None = Field(default=None, ge=0)


class StationLoad(FirestoreModel):
    """Weight loaded at a specific station for a dossier.

    References a ``LoadingStation.name`` from the aircraft configuration.
    """

    station_name: str = Field(..., min_length=1, description="References LoadingStation.name")
    weight_kg: float = Field(..., ge=0, description="Actual weight loaded at this station")


class Dossier(FirestoreModel):
    """A navigation dossier — the central entity for VFR flight preparation.

    Groups all data needed to prepare a flight: route, aircraft, weather,
    NOTAMs, fuel planning, weight & balance, and generated documents.

    A Dossier captures a **frozen snapshot** of conditions at preparation time.
    Live data (weather, NOTAMs) is never re-fetched automatically — the pilot
    must explicitly refresh to get a new snapshot.

    **Persisted fields** (Firestore source of truth):
    - name, route_id, aircraft_id, departure, status, sections
    - alternate_icao, station_loads, tem_threats, tem_mitigations
    - weather_simulation_id, notam_snapshot_ref, prep_sheet_ref

    **Calculated fields** (derived at runtime, never stored):
    - RouteLeg computed fields (distance, heading, ETE per leg)
    - Weight & balance envelope check result
    - Total fuel required
    """

    id: str | None = None
    name: str = Field(..., min_length=1, description="Human-readable dossier name")
    route_id: str = Field(..., description="Reference to Route document ID")
    aircraft_id: str | None = Field(
        default=None, description="Reference to Aircraft document ID"
    )
    departure_datetime_utc: datetime = Field(
        ..., description="Planned departure date/time in UTC"
    )
    status: DossierStatus = DossierStatus.DRAFT

    # Section completion tracking (9 sections)
    sections: dict[str, str] = Field(
        default_factory=_default_sections,
        description="Completion status per section (SectionId -> SectionCompletion)",
    )

    # Alternate aerodromes
    alternate_icao: list[str] = Field(
        default_factory=list,
        description="ICAO codes of alternate aerodromes",
    )

    # Loading — references Aircraft.loading_stations by name
    station_loads: list["StationLoad"] = Field(
        default_factory=list,
        description="Weight loaded at each station for this dossier",
    )

    # GPS track (post-flight)
    track: Track | None = None

    # Snapshot references — frozen at preparation time, never auto-refreshed.
    # The pilot explicitly triggers a new collection to update these.
    weather_simulation_id: str | None = Field(
        default=None, description="Reference to WeatherSimulation collected at prep time"
    )
    notam_snapshot_ref: str | None = Field(
        default=None, description="GCS path to NOTAM snapshot collected at prep time"
    )
    prep_sheet_ref: str | None = Field(
        default=None, description="GCS path to generated preparation sheet (PDF)"
    )

    # TEM (Threat and Error Management) analysis
    tem_threats: list[str] = Field(
        default_factory=list,
        description="Identified threats for this flight",
    )
    tem_mitigations: list[str] = Field(
        default_factory=list,
        description="Planned mitigations for identified threats",
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime | None = None
