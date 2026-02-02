"""Waypoint and UserWaypoint — geographic locations for navigation.

A ``Waypoint`` is an ephemeral location used within a single route.
A ``UserWaypoint`` is a persisted waypoint saved for reuse across routes.

Stored at: ``/users/{user_id}/user_waypoints/{waypoint_id}``
"""

import hashlib
from datetime import datetime, timezone

from pydantic import Field, computed_field, field_validator

from core.contracts.common import FirestoreModel
from core.contracts.enums import LocationType, WaypointSource


def waypoint_id(name: str, latitude: float, longitude: float) -> str:
    """Deterministic waypoint ID: MD5(name:lat:lon)[:16]."""
    raw = f"{name}:{latitude}:{longitude}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


class Waypoint(FirestoreModel):
    """A geographic location — ephemeral, used within a single route.

    Not persisted to Firestore on its own.  Created during route import
    or flight planning and embedded in the route context.
    """

    name: str = Field(..., min_length=1, max_length=100)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    location_type: LocationType = LocationType.GPS_POINT
    icao_code: str | None = Field(
        default=None,
        pattern=r"^[A-Z]{4}$",
        description="ICAO code if location is an aerodrome",
    )
    description: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def id(self) -> str:
        """Deterministic ID: MD5(name:lat:lon)[:16]."""
        return waypoint_id(self.name, self.latitude, self.longitude)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class UserWaypoint(Waypoint):
    """A waypoint persisted by a user for reuse across multiple routes.

    Extends ``Waypoint`` with ownership metadata (source, tags, timestamps).
    The ``id`` (inherited) is used as the Firestore document key.
    """

    source: WaypointSource = WaypointSource.MANUAL
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def lowercase_tags(cls, v: list[str]) -> list[str]:
        return [tag.lower().strip() for tag in v]
