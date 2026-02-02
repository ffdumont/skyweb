"""In-memory Firestore fake for repository unit tests.

Mimics the google-cloud-firestore AsyncClient interface just enough
to test BaseRepository and concrete repositories without network access.
"""

from __future__ import annotations

import uuid
from typing import Any


class FakeDocumentSnapshot:
    def __init__(self, data: dict[str, Any] | None, doc_id: str):
        self._data = data
        self.id = doc_id
        self.exists = data is not None

    def to_dict(self) -> dict[str, Any]:
        if self._data is None:
            raise ValueError("Document does not exist")
        return dict(self._data)


class FakeDocumentRef:
    def __init__(self, store: dict[str, dict], path: str):
        self._store = store
        self._path = path
        self.id = path.rsplit("/", 1)[-1]

    async def get(self) -> FakeDocumentSnapshot:
        data = self._store.get(self._path)
        return FakeDocumentSnapshot(data, self.id)

    async def set(self, data: dict, merge: bool = False) -> None:
        if merge and self._path in self._store:
            self._store[self._path].update(data)
        else:
            self._store[self._path] = dict(data)

    async def delete(self) -> None:
        self._store.pop(self._path, None)

    def collection(self, name: str) -> "FakeCollectionRef":
        return FakeCollectionRef(self._store, f"{self._path}/{name}")


class FakeWriteResult:
    pass


class FakeBatch:
    def __init__(self, store: dict[str, dict]):
        self._store = store
        self._ops: list[tuple[str, str, dict | None]] = []

    def set(self, doc_ref: FakeDocumentRef, data: dict, merge: bool = False) -> None:
        self._ops.append(("set", doc_ref._path, dict(data)))

    async def commit(self) -> None:
        for op, path, data in self._ops:
            if op == "set" and data is not None:
                self._store[path] = data


class FakeCollectionRef:
    def __init__(self, store: dict[str, dict], path: str):
        self._store = store
        self._path = path

    def document(self, doc_id: str | None = None) -> FakeDocumentRef:
        if doc_id is None:
            doc_id = uuid.uuid4().hex[:20]
        return FakeDocumentRef(self._store, f"{self._path}/{doc_id}")

    async def add(self, data: dict) -> tuple[FakeWriteResult, FakeDocumentRef]:
        doc_id = uuid.uuid4().hex[:20]
        doc_ref = self.document(doc_id)
        self._store[doc_ref._path] = dict(data)
        return FakeWriteResult(), doc_ref

    async def stream(self):
        prefix = self._path + "/"
        for path, data in sorted(self._store.items()):
            if path.startswith(prefix):
                rest = path[len(prefix):]
                # Only yield direct children (no nested subcollections)
                if "/" not in rest:
                    yield FakeDocumentSnapshot(dict(data), rest)

    def where(self, field: str, op: str, value: Any) -> "FakeQuery":
        return FakeQuery(self._store, self._path, field, op, value)


class FakeQuery:
    def __init__(
        self,
        store: dict[str, dict],
        path: str,
        field: str,
        op: str,
        value: Any,
    ):
        self._store = store
        self._path = path
        self._field = field
        self._op = op
        self._value = value

    async def stream(self):
        prefix = self._path + "/"
        for path, data in sorted(self._store.items()):
            if path.startswith(prefix):
                rest = path[len(prefix):]
                if "/" not in rest:
                    if self._matches(data):
                        yield FakeDocumentSnapshot(dict(data), rest)

    def _matches(self, data: dict) -> bool:
        val = data.get(self._field)
        if self._op == "==":
            return val == self._value
        if self._op == "array_contains":
            return isinstance(val, list) and self._value in val
        return False


class FakeFirestoreClient:
    """Drop-in replacement for ``google.cloud.firestore.AsyncClient``."""

    def __init__(self):
        self.store: dict[str, dict] = {}

    def collection(self, name: str) -> FakeCollectionRef:
        return FakeCollectionRef(self.store, name)

    def batch(self) -> FakeBatch:
        return FakeBatch(self.store)

    async def get_all(self, refs: list[FakeDocumentRef]):
        for ref in refs:
            data = self.store.get(ref._path)
            yield FakeDocumentSnapshot(data, ref.id)
