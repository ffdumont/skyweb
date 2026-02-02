"""Base classes and shared types for SkyWeb contracts.

Unit conventions (all contracts and API responses):
- **Distances**: nautical miles (NM) — suffix ``_nm``
- **Speeds**: knots (kt) — suffix ``_kt``
- **Altitudes**: feet AMSL — suffix ``_ft``
- **Weights**: kilograms (kg) — suffix ``_kg``
- **Lever arms**: meters (m) — suffix ``_m``
- **Fuel volumes**: liters — suffix ``_liters``
- **Headings/angles**: degrees — suffix ``_deg``
- **Datetimes**: always UTC, ISO 8601 in serialized form
- **Coordinates**: WGS84 decimal degrees

Internal services (e.g. SpatiaLite queries) may use metric units,
but must convert to the above before returning to the API layer.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class FirestoreModel(BaseModel):
    """Base model with Firestore-friendly serialization.

    - Enums serialize as string values (Firestore stores strings).
    - ``to_firestore()`` produces a JSON-safe dict (datetimes as ISO 8601).
    - ``from_firestore()`` hydrates from a Firestore document dict.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
    )

    def to_firestore(self) -> dict[str, Any]:
        """Dump to Firestore-compatible dict."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)

    @classmethod
    def from_firestore(cls, data: dict[str, Any]) -> "FirestoreModel":
        """Create model instance from Firestore document dict."""
        return cls.model_validate(data)


class GeoPoint(BaseModel):
    """WGS84 geographic coordinate."""

    latitude: float
    longitude: float

    model_config = ConfigDict(frozen=True)
