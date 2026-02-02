"""Generic async Firestore repository for user-scoped collections."""

from __future__ import annotations

from typing import Generic, TypeVar, Type

from core.contracts.common import FirestoreModel
from core.persistence.firestore_client import get_firestore_client

T = TypeVar("T", bound=FirestoreModel)


class BaseRepository(Generic[T]):
    """CRUD for a Firestore subcollection under ``/users/{user_id}/``.

    Serialization relies entirely on the contract's ``to_firestore()``
    and ``from_firestore()`` methods — no extra mapping layer.
    """

    def __init__(self, model_class: Type[T], collection_name: str):
        self._model_class = model_class
        self._collection_name = collection_name

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _collection_ref(self, user_id: str):
        db = get_firestore_client()
        return (
            db.collection("users")
            .document(user_id)
            .collection(self._collection_name)
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get(self, user_id: str, doc_id: str) -> T | None:
        """Fetch a single document by ID. Returns *None* if missing."""
        doc = await self._collection_ref(user_id).document(doc_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["id"] = doc.id
        return self._model_class.from_firestore(data)

    async def list_all(self, user_id: str) -> list[T]:
        """Stream every document in the collection."""
        results: list[T] = []
        async for doc in self._collection_ref(user_id).stream():
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(self._model_class.from_firestore(data))
        return results

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create(self, user_id: str, entity: T) -> str:
        """Create a document.

        If ``to_firestore()`` includes an ``id`` key (e.g. deterministic
        MD5 for UserWaypoint), it is used as the document ID — giving
        natural deduplication.  Otherwise Firestore auto-generates one.

        Returns the document ID.
        """
        data = entity.to_firestore()
        doc_id = data.pop("id", None)
        if doc_id:
            await self._collection_ref(user_id).document(doc_id).set(data)
            return doc_id
        ref = await self._collection_ref(user_id).add(data)
        return ref[1].id  # (write_result, doc_ref) tuple

    async def update(self, user_id: str, doc_id: str, entity: T) -> None:
        """Partial update (merge) of an existing document."""
        data = entity.to_firestore()
        data.pop("id", None)
        await (
            self._collection_ref(user_id)
            .document(doc_id)
            .set(data, merge=True)
        )

    async def delete(self, user_id: str, doc_id: str) -> None:
        """Delete a document."""
        await self._collection_ref(user_id).document(doc_id).delete()
