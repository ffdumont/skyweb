"""Persistence-specific exceptions."""


class PersistenceError(Exception):
    """Base exception for all persistence errors."""


class DocumentNotFoundError(PersistenceError):
    """Raised when a Firestore document does not exist."""

    def __init__(self, collection: str, doc_id: str):
        self.collection = collection
        self.doc_id = doc_id
        super().__init__(f"{collection}/{doc_id} not found")


class SpatiaLiteNotReadyError(PersistenceError):
    """Raised when the SpatiaLite database is not yet downloaded."""


class AIRACCycleError(PersistenceError):
    """Raised when AIRAC cycle operations fail."""
