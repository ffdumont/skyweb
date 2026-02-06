"""Repository for user-specific aerodrome VAC notes."""

from __future__ import annotations

from core.contracts.aerodrome_notes import AerodromeNotes
from core.persistence.repositories.base import BaseRepository


class AerodromeNotesRepository(BaseRepository[AerodromeNotes]):
    """CRUD for aerodrome notes stored under /users/{user_id}/aerodrome_notes/{icao}.

    The document ID is the ICAO code, providing natural deduplication.
    """

    def __init__(self):
        super().__init__(AerodromeNotes, "aerodrome_notes")

    async def get_by_icao(self, user_id: str, icao: str) -> AerodromeNotes | None:
        """Fetch notes for a specific aerodrome by ICAO code."""
        return await self.get(user_id, icao.upper())

    async def save(self, user_id: str, notes: AerodromeNotes) -> str:
        """Save or update aerodrome notes. Returns the ICAO code."""
        # Use ICAO as document ID for natural deduplication
        icao = notes.icao.upper()
        await self.update(user_id, icao, notes)
        return icao

    async def delete_by_icao(self, user_id: str, icao: str) -> None:
        """Delete notes for a specific aerodrome."""
        await self.delete(user_id, icao.upper())

    async def get_multiple(
        self, user_id: str, icao_codes: list[str]
    ) -> dict[str, AerodromeNotes]:
        """Fetch notes for multiple aerodromes. Returns a dict keyed by ICAO."""
        result: dict[str, AerodromeNotes] = {}
        for icao in icao_codes:
            notes = await self.get_by_icao(user_id, icao)
            if notes:
                result[icao.upper()] = notes
        return result
