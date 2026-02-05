"""Repository for routes."""

from __future__ import annotations

from core.contracts.route import Route
from core.contracts.waypoint import UserWaypoint
from core.persistence.firestore_client import get_firestore_client
from core.persistence.repositories.base import BaseRepository


class RouteRepository(BaseRepository[Route]):
    def __init__(self):
        super().__init__(Route, "routes")

    # ------------------------------------------------------------------
    # Atomic save: route + waypoint promotion
    # ------------------------------------------------------------------

    async def save_with_waypoints(
        self,
        user_id: str,
        route: Route,
        waypoints: list[UserWaypoint],
    ) -> str:
        """Atomically promote ephemeral waypoints and save the route.

        Uses a Firestore batch write (up to 500 operations) to guarantee
        that a persisted route never references non-persisted waypoints.
        Returns the route document ID.
        """
        db = get_firestore_client()
        batch = db.batch()

        # Promote waypoints
        wp_col = (
            db.collection("users")
            .document(user_id)
            .collection("user_waypoints")
        )
        for wp in waypoints:
            data = wp.to_firestore()
            wp_id = data.pop("id")
            batch.set(wp_col.document(wp_id), data)

        # Save route
        route_data = route.to_firestore()
        route_id = route_data.pop("id", None)
        route_col = self._collection_ref(user_id)
        if route_id:
            batch.set(route_col.document(route_id), route_data)
        else:
            route_ref = route_col.document()
            route_id = route_ref.id
            batch.set(route_ref, route_data)

        await batch.commit()
        return route_id

