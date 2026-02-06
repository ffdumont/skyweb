"""User-specific VAC notes for aerodromes.

These notes are filled manually by the pilot from VAC charts and are
reusable across all their flight dossiers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from core.contracts.common import FirestoreModel


class Obstacle(FirestoreModel):
    """An obstacle near the aerodrome."""

    description: str = Field(..., description="e.g. 'Pylône électrique'")
    distance_nm: float | None = Field(default=None, ge=0)
    direction: str | None = Field(default=None, description="e.g. 'SW', 'NE'")
    height_ft: int | None = Field(default=None, ge=0)
    lit: bool | None = Field(default=None, description="Obstacle lit at night")


class AerodromeNotes(FirestoreModel):
    """User-specific VAC notes for an aerodrome.

    Stored in Firestore at: users/{user_id}/aerodrome_notes/{icao}
    The ICAO code serves as the document ID.
    """

    icao: str = Field(..., pattern=r"^[A-Z]{4}$", description="Document ID = ICAO code")

    # Circuit information
    runway_in_use: str | None = Field(
        default=None, description="Currently expected runway, e.g. '13'"
    )
    circuit_direction: dict[str, Literal["left", "right"]] | None = Field(
        default=None,
        description="Circuit direction per runway, e.g. {'13': 'left', '31': 'right'}",
    )
    pattern_altitude_ft: int | None = Field(
        default=None, ge=0, description="Traffic pattern altitude in feet AMSL"
    )

    # Entry/exit points
    entry_point: str | None = Field(
        default=None, description="Designated entry point, e.g. 'Verticale château'"
    )
    exit_point: str | None = Field(
        default=None, description="Designated exit point"
    )

    # Free-form notes
    special_procedures: str | None = Field(
        default=None, description="Special procedures, restrictions, PPR info, etc."
    )

    # Obstacles
    obstacles: list[Obstacle] = Field(default_factory=list)

    # Metadata
    updated_at: datetime | None = Field(default=None)

    def to_firestore(self) -> dict:
        """Override to use icao as document ID."""
        data = super().to_firestore()
        data["id"] = self.icao  # Use ICAO as doc ID
        return data

    def is_complete(self) -> bool:
        """Check if the minimum required fields are filled."""
        return bool(
            self.runway_in_use
            and self.circuit_direction
            and self.pattern_altitude_ft is not None
        )

    def completion_status(self) -> str:
        """Return 'complete', 'partial', or 'empty'."""
        filled = sum([
            bool(self.runway_in_use),
            bool(self.circuit_direction),
            self.pattern_altitude_ft is not None,
            bool(self.entry_point),
            bool(self.exit_point),
            bool(self.special_procedures),
        ])
        if filled == 0:
            return "empty"
        if self.is_complete():
            return "complete"
        return "partial"
