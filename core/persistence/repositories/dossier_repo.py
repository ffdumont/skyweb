"""Repository for navigation dossiers and weather simulations."""

from __future__ import annotations

from core.contracts.enums import DossierStatus, SectionCompletion, SectionId
from core.contracts.dossier import Dossier
from core.contracts.weather import WeatherSimulation
from core.persistence.firestore_client import get_firestore_client
from core.persistence.repositories.base import BaseRepository


class DossierRepository(BaseRepository[Dossier]):
    def __init__(self):
        super().__init__(Dossier, "dossiers")

    async def list_by_status(
        self, user_id: str, status: DossierStatus
    ) -> list[Dossier]:
        """Return all dossiers with a given status."""
        query = self._collection_ref(user_id).where(
            "status", "==", status.value
        )
        results: list[Dossier] = []
        async for doc in query.stream():
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(Dossier.from_firestore(data))
        return results

    async def update_section(
        self,
        user_id: str,
        dossier_id: str,
        section: SectionId,
        completion: SectionCompletion,
    ) -> None:
        """Update the completion status of a single section."""
        db = get_firestore_client()
        ref = (
            db.collection("users")
            .document(user_id)
            .collection("dossiers")
            .document(dossier_id)
        )
        await ref.update({f"sections.{section.value}": completion.value})

    # ------------------------------------------------------------------
    # Subcollection: simulations (weather)
    # ------------------------------------------------------------------

    def _sim_collection(self, user_id: str, dossier_id: str):
        return (
            self._collection_ref(user_id)
            .document(dossier_id)
            .collection("simulations")
        )

    async def add_simulation(
        self, user_id: str, dossier_id: str, simulation: WeatherSimulation
    ) -> str:
        """Add a weather simulation to a dossier. Returns the simulation ID."""
        data = simulation.to_firestore()
        data.pop("id", None)
        ref = await self._sim_collection(user_id, dossier_id).add(data)
        return ref[1].id

    async def get_simulation(
        self, user_id: str, dossier_id: str, simulation_id: str
    ) -> WeatherSimulation | None:
        """Fetch a single simulation."""
        doc = await (
            self._sim_collection(user_id, dossier_id)
            .document(simulation_id)
            .get()
        )
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["id"] = doc.id
        return WeatherSimulation.from_firestore(data)

    async def list_simulations(
        self, user_id: str, dossier_id: str
    ) -> list[WeatherSimulation]:
        """List all simulations for a dossier."""
        results: list[WeatherSimulation] = []
        async for doc in self._sim_collection(user_id, dossier_id).stream():
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(WeatherSimulation.from_firestore(data))
        return results
