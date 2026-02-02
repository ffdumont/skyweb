"""Firestore async client singleton."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_client: Any = None


def get_firestore_client() -> Any:
    """Return a lazy-initialized Firestore AsyncClient.

    Uses Application Default Credentials (ADC).
    Falls back to an in-memory fake client when google-cloud-firestore
    is not installed (local dev without GCP).
    """
    global _client
    if _client is not None:
        return _client

    try:
        from google.cloud.firestore import AsyncClient
        _client = AsyncClient()
        logger.info("Using Google Cloud Firestore")
    except ImportError:
        from tests.persistence.fake_firestore import FakeFirestoreClient
        _client = FakeFirestoreClient()
        logger.warning("google-cloud-firestore not installed — using in-memory fake")

    return _client


def _reset_client() -> None:
    """Reset the singleton (for testing only)."""
    global _client
    _client = None
