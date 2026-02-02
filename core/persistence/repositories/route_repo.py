"""Repository for routes and weather simulations (subcollection)."""

from __future__ import annotations

from core.contracts.route import Route
from core.contracts.waypoint import UserWaypoint
from core.contracts.weather import WeatherSimulation
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

    # ------------------------------------------------------------------
    # Subcollection: simulations
    # ------------------------------------------------------------------

    def _sim_collection(self, user_id: str, route_id: str):
        return (
            self._collection_ref(user_id)
            .document(route_id)
            .collection("simulations")
        )

    async def add_simulation(
        self, user_id: str, route_id: str, simulation: WeatherSimulation
    ) -> str:
        """Add a weather simulation to a route. Returns the simulation ID."""
        data = simulation.to_firestore()
        data.pop("id", None)
        ref = await self._sim_collection(user_id, route_id).add(data)
        return ref[1].id

    async def get_simulation(
        self, user_id: str, route_id: str, simulation_id: str
    ) -> WeatherSimulation | None:
        """Fetch a single simulation."""
        doc = await (
            self._sim_collection(user_id, route_id)
            .document(simulation_id)
            .get()
        )
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["id"] = doc.id
        return WeatherSimulation.from_firestore(data)

    async def list_simulations(
        self, user_id: str, route_id: str
    ) -> list[WeatherSimulation]:
        """List all simulations for a route."""
        results: list[WeatherSimulation] = []
        async for doc in self._sim_collection(user_id, route_id).stream():
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(WeatherSimulation.from_firestore(data))
        return results
