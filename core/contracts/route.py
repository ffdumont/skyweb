"""Route, RouteLeg, RouteProjection — ordered waypoint sequence with altitude intentions.

Route and RouteLeg are **persisted** at: ``/users/{user_id}/routes/{route_id}``

RouteProjection and ProjectionAssumptions are **calculated** API response
models — never stored in Firestore.
"""

from datetime import datetime, timezone
from typing import Self

from pydantic import Field, model_validator

from core.contracts.common import FirestoreModel
from core.contracts.enums import WaypointRole


class RouteWaypointRef(FirestoreModel):
    """Reference to a waypoint within a Route, with ordering and role.

    The ``waypoint_id`` may reference a persisted ``UserWaypoint``
    or an ephemeral ``Waypoint`` created for this route only.
    """

    waypoint_id: str = Field(..., min_length=1, max_length=16)
    sequence_order: int = Field(..., ge=1)
    role: WaypointRole = WaypointRole.ENROUTE


class RouteLeg(FirestoreModel):
    """A leg between two consecutive waypoints.

    Combines the pilot's **intention** (persisted) and the system's
    **computed projection** (populated at runtime, not persisted).

    Persisted fields: ``from_seq``, ``to_seq``, ``planned_altitude_ft``.
    Computed fields (all optional): filled by the nav log builder from
    waypoint coordinates, wind data, and aircraft performance.
    ``to_firestore()`` with ``exclude_none=True`` naturally omits them
    when they haven't been computed yet.
    """

    # --- Persisted: pilot intention ---
    from_seq: int = Field(..., ge=1)
    to_seq: int = Field(..., ge=2)
    planned_altitude_ft: int = Field(
        ..., ge=0, le=19500, description="Planned cruise altitude in ft AMSL"
    )

    # --- Computed: filled at runtime by nav log builder ---
    distance_nm: float | None = Field(
        default=None, ge=0, description="Great-circle distance in NM"
    )
    true_heading_deg: float | None = Field(
        default=None, ge=0, lt=360, description="True heading in degrees"
    )
    magnetic_heading_deg: float | None = Field(
        default=None, ge=0, lt=360, description="Magnetic heading (true + declination)"
    )
    ground_speed_kt: float | None = Field(
        default=None, gt=0, description="Ground speed accounting for wind"
    )
    estimated_time_minutes: float | None = Field(
        default=None, ge=0, description="Estimated time for this leg"
    )
    wind_correction_deg: float | None = Field(
        default=None, description="Wind correction angle applied"
    )
    fuel_consumption_liters: float | None = Field(
        default=None, ge=0, description="Estimated fuel burn for this leg"
    )

    @model_validator(mode="after")
    def validate_consecutive(self) -> Self:
        if self.to_seq != self.from_seq + 1:
            raise ValueError(
                f"to_seq ({self.to_seq}) must equal from_seq + 1 ({self.from_seq + 1})"
            )
        return self


class Route(FirestoreModel):
    """An ordered sequence of waypoints with altitude intentions per leg.

    References UserWaypoint IDs — does NOT embed full waypoints.
    """

    id: str | None = None
    name: str = Field(..., min_length=1, max_length=200)
    waypoints: list[RouteWaypointRef] = Field(..., min_length=2)
    legs: list[RouteLeg] = Field(default_factory=list)
    source_kml_ref: str | None = Field(
        default=None, description="GCS path to the original KML file"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_route_integrity(self) -> Self:
        # sequence_orders must be consecutive 1..N
        orders = sorted(wp.sequence_order for wp in self.waypoints)
        expected = list(range(1, len(self.waypoints) + 1))
        if orders != expected:
            raise ValueError(
                f"Waypoint sequence_orders must be consecutive 1..N, got {orders}"
            )

        # legs must reference valid sequence_orders
        max_seq = len(self.waypoints)
        for leg in self.legs:
            if leg.from_seq > max_seq or leg.to_seq > max_seq:
                raise ValueError(
                    f"Leg ({leg.from_seq}->{leg.to_seq}) references "
                    f"sequence_order beyond {max_seq}"
                )

        # if legs provided, count must be N-1
        if self.legs and len(self.legs) != len(self.waypoints) - 1:
            raise ValueError(
                f"Expected {len(self.waypoints) - 1} legs for "
                f"{len(self.waypoints)} waypoints, got {len(self.legs)}"
            )

        return self


# ---------------------------------------------------------------------------
# API response models — calculated, never persisted
# ---------------------------------------------------------------------------


class ProjectionAssumptions(FirestoreModel):
    """Hypotheses used to compute a RouteProjection.

    Makes explicit every parameter that influences the calculated result.
    A change in any assumption produces a different projection.
    """

    aircraft_id: str | None = Field(
        default=None, description="Aircraft used for TAS and fuel profile"
    )
    cruise_speed_kt: int | None = Field(
        default=None, gt=0, le=300, description="TAS override (if no aircraft)"
    )
    departure_datetime_utc: datetime | None = Field(
        default=None, description="Departure time — drives wind interpolation"
    )
    wind_source: str | None = Field(
        default=None, description="e.g. 'arome_france', 'manual', 'none'"
    )


class RouteProjection(FirestoreModel):
    """Calculated projection of a Route under explicit assumptions.

    Returned by ``GET /api/routes/{route_id}/projection``.
    **Never persisted** — can be recomputed at any time.
    Results are **not guaranteed stable**: a different wind forecast
    or a different aircraft yields a different projection.
    """

    route_id: str = Field(..., description="Source Route ID")
    route_name: str = Field(..., description="Route name (denormalized for display)")
    legs: list[RouteLeg] = Field(
        ..., description="Legs with computed fields populated"
    )
    assumptions: ProjectionAssumptions = Field(
        ..., description="Hypotheses used for this projection"
    )

    # Totals
    total_distance_nm: float = Field(..., ge=0, description="Sum of leg distances")
    total_time_minutes: float = Field(..., ge=0, description="Sum of leg ETEs")
    total_fuel_liters: float | None = Field(
        default=None, ge=0, description="Sum of leg fuel consumption"
    )

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="When this projection was computed",
    )
