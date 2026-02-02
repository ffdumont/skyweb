"""Repository for shared community collections (VAC notes, TDP database)."""

from __future__ import annotations

from datetime import datetime, timezone

from core.persistence.firestore_client import get_firestore_client


class CommunityRepository:
    """CRUD for ``/community/`` collections — not scoped by user_id."""

    # ------------------------------------------------------------------
    # VAC notes
    # ------------------------------------------------------------------

    async def get_vac_notes(self, icao: str) -> dict | None:
        db = get_firestore_client()
        doc = await (
            db.collection("community")
            .document("vac_notes")
            .collection("entries")
            .document(icao.upper())
            .get()
        )
        return doc.to_dict() if doc.exists else None

    async def set_vac_notes(
        self, icao: str, data: dict, user_id: str
    ) -> None:
        """Merge VAC notes for an aerodrome. Stamps updated_by/at."""
        db = get_firestore_client()
        data["updated_by"] = user_id
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await (
            db.collection("community")
            .document("vac_notes")
            .collection("entries")
            .document(icao.upper())
            .set(data, merge=True)
        )

    # ------------------------------------------------------------------
    # TDP database
    # ------------------------------------------------------------------

    async def get_tdp(self, icao: str) -> dict | None:
        db = get_firestore_client()
        doc = await (
            db.collection("community")
            .document("tdp_database")
            .collection("entries")
            .document(icao.upper())
            .get()
        )
        return doc.to_dict() if doc.exists else None
