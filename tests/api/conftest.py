"""Shared fixtures for API tests."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from core.api.app import app
from core.api.auth import UserClaims
from core.api.deps import get_current_user
from core.persistence.spatialite.db_manager import SpatiaLiteManager
from tests.persistence.fake_firestore import FakeFirestoreClient

TEST_USER_ID = "api-test-user"


@pytest.fixture
def fake_client():
    """In-memory Firestore fake, shared across all repos in a single test."""
    return FakeFirestoreClient()


@pytest.fixture
def test_app(fake_client):
    """FastAPI app with dependency overrides for testing."""
    # Override auth to return a fixed test user
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID

    # Patch get_firestore_client everywhere it's imported
    with patch(
        "core.persistence.repositories.base.get_firestore_client",
        return_value=fake_client,
    ), patch(
        "core.persistence.repositories.route_repo.get_firestore_client",
        return_value=fake_client,
    ), patch(
        "core.persistence.repositories.community_repo.get_firestore_client",
        return_value=fake_client,
    ):
        # Set a dummy SpatiaLiteManager on app.state
        manager = SpatiaLiteManager()
        app.state.spatialite_manager = manager
        yield app

    app.dependency_overrides.clear()


@pytest.fixture
async def client(test_app):
    """httpx AsyncClient wired to the test app."""
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
