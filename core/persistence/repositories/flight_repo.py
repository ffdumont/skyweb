"""Repository for flights."""

from __future__ import annotations

from core.contracts.enums import FlightStatus
from core.contracts.flight import Flight
from core.persistence.repositories.base import BaseRepository


class FlightRepository(BaseRepository[Flight]):
    def __init__(self):
        super().__init__(Flight, "flights")

    async def list_by_status(
        self, user_id: str, status: FlightStatus
    ) -> list[Flight]:
        """Return all flights with a given status."""
        query = self._collection_ref(user_id).where(
            "status", "==", status.value
        )
        results: list[Flight] = []
        async for doc in query.stream():
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(Flight.from_firestore(data))
        return results
