"""Repository for user waypoints."""

from __future__ import annotations

from core.contracts.waypoint import UserWaypoint
from core.persistence.firestore_client import get_firestore_client
from core.persistence.repositories.base import BaseRepository


class WaypointRepository(BaseRepository[UserWaypoint]):
    def __init__(self):
        super().__init__(UserWaypoint, "user_waypoints")

    async def get_by_ids(
        self, user_id: str, waypoint_ids: list[str]
    ) -> dict[str, UserWaypoint]:
        """Batch-fetch waypoints by ID. Returns ``{id: UserWaypoint}``."""
        if not waypoint_ids:
            return {}
        col = self._collection_ref(user_id)
        refs = [col.document(wid) for wid in waypoint_ids]
        db = get_firestore_client()
        result: dict[str, UserWaypoint] = {}
        async for doc in db.get_all(refs):
            if doc.exists:
                data = doc.to_dict()
                data["id"] = doc.id
                result[doc.id] = UserWaypoint.from_firestore(data)
        return result

    async def find_by_tag(
        self, user_id: str, tag: str
    ) -> list[UserWaypoint]:
        """Find waypoints that contain a specific tag."""
        query = self._collection_ref(user_id).where(
            "tags", "array_contains", tag.lower()
        )
        results: list[UserWaypoint] = []
        async for doc in query.stream():
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(UserWaypoint.from_firestore(data))
        return results
