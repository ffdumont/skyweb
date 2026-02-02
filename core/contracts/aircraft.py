"""Aircraft configuration for a user.

Includes weight & balance envelope (centrogramme) and loading stations.

Stored at: ``/users/{user_id}/aircraft/{aircraft_id}``
"""

from enum import Enum

from pydantic import Field

from core.contracts.common import FirestoreModel


class StationType(str, Enum):
    """Type of loading station."""
    CREW = "crew"
    PASSENGER = "passenger"
    BAGGAGE = "baggage"
    FUEL = "fuel"


class FuelProfile(FirestoreModel):
    """Fuel consumption profile at various power settings."""

    cruise_ff_lph: float = Field(..., gt=0, description="Cruise fuel flow in liters/hour")
    climb_ff_lph: float | None = Field(default=None, gt=0)
    descent_ff_lph: float | None = Field(default=None, gt=0)
    taxi_ff_lph: float | None = Field(default=None, gt=0)


class EnvelopePoint(FirestoreModel):
    """A point on the weight & balance envelope (centrogramme).

    The ordered list of points forms a closed polygon.
    """

    arm_m: float = Field(..., description="Lever arm in meters")
    weight_kg: float = Field(..., ge=0, description="Weight in kg")


class LoadingStation(FirestoreModel):
    """A loading station on the aircraft with a fixed lever arm.

    Each station represents a location where weight is applied:
    crew seats, passenger seats, baggage compartment, fuel tank, etc.
    """

    name: str = Field(..., min_length=1, description="e.g. 'Equipage', 'Passager(s)'")
    station_type: StationType
    arm_m: float = Field(..., description="Lever arm in meters")
    max_weight_kg: float = Field(..., gt=0, description="Maximum weight for this station")


class Aircraft(FirestoreModel):
    """Aircraft configuration with weight & balance data."""

    id: str | None = None
    registration: str = Field(..., pattern=r"^[A-Z0-9-]+$", description="e.g. F-HBCT")
    aircraft_type: str = Field(..., min_length=1, description="e.g. CT-LS, DR400-120")
    empty_weight_kg: float = Field(..., gt=0)
    empty_arm_m: float = Field(..., description="Empty weight lever arm in meters")
    mtow_kg: float = Field(..., gt=0)
    fuel_capacity_liters: float = Field(..., gt=0)
    cruise_speed_kt: int = Field(..., gt=0, le=300, description="Typical cruise TAS in kt")

    # Weight & Balance
    envelope: list[EnvelopePoint] = Field(
        default_factory=list,
        description="Centrogramme: ordered points forming the W&B envelope polygon",
    )
    loading_stations: list[LoadingStation] = Field(
        default_factory=list,
        description="Loading stations with fixed arm and max weight",
    )

    fuel_profile: FuelProfile | None = None
    notes: str | None = None
