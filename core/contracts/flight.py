"""Flight and Track — a specific instance of flying a route.

Stored at: ``/users/{user_id}/flights/{flight_id}``
"""

from datetime import datetime, timezone

from pydantic import Field

from core.contracts.common import FirestoreModel
from core.contracts.enums import FlightStatus, TrackSource


class WaypointPassageTime(FirestoreModel):
    """Actual passage time at a waypoint, derived from GPX track snap."""

    waypoint_id: str
    sequence_order: int
    passage_time_utc: datetime
    latitude: float | None = None
    longitude: float | None = None


class Track(FirestoreModel):
    """A real GPS trace (GPX) associated to a flight.

    Contains passage times snapped to route waypoints.
    """

    gpx_ref: str | None = Field(default=None, description="GCS path to the GPX file")
    source: TrackSource = TrackSource.GPX_FILE
    passage_times: list[WaypointPassageTime] = Field(default_factory=list)
    recorded_at: datetime | None = None
    total_distance_nm: float | None = Field(default=None, ge=0)
    total_time_minutes: float | None = Field(default=None, ge=0)


class StationLoad(FirestoreModel):
    """Weight loaded at a specific station for a flight.

    References a ``LoadingStation.name`` from the aircraft configuration.
    """

    station_name: str = Field(..., min_length=1, description="References LoadingStation.name")
    weight_kg: float = Field(..., ge=0, description="Actual weight loaded at this station")


class Flight(FirestoreModel):
    """A specific instance of flying a route on a date.

    A Flight captures a **frozen snapshot** of conditions at preparation time.
    Live data (weather, NOTAMs) is never re-fetched automatically — the pilot
    must explicitly refresh to get a new snapshot.

    **Persisted fields** (Firestore source of truth):
    - route_id, aircraft_id, departure, status, station_loads
    - weather_simulation_id, notam_snapshot_ref, prep_sheet_ref

    **Calculated fields** (derived at runtime, never stored):
    - RouteLeg computed fields (distance, heading, ETE per leg)
    - Weight & balance envelope check result
    - Total fuel required
    """

    id: str | None = None
    route_id: str = Field(..., description="Reference to Route document ID")
    aircraft_id: str | None = Field(
        default=None, description="Reference to Aircraft document ID"
    )
    departure_datetime_utc: datetime = Field(
        ..., description="Planned departure date/time in UTC"
    )
    status: FlightStatus = FlightStatus.DRAFT

    # Loading — references Aircraft.loading_stations by name
    station_loads: list["StationLoad"] = Field(
        default_factory=list,
        description="Weight loaded at each station for this flight",
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

    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime | None = None
