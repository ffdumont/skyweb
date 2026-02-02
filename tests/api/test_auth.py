"""Tests for auth middleware."""

from __future__ import annotations

import os
from unittest.mock import patch

import httpx
import pytest

from core.api.app import app
from core.api.deps import get_current_user
from core.persistence.spatialite.db_manager import SpatiaLiteManager
from tests.persistence.fake_firestore import FakeFirestoreClient


class TestAuth:
    async def test_missing_auth_header(self):
        """Requests without auth should return 401 when auth is enabled."""
        # Remove the dependency override so real auth runs
        overrides = dict(app.dependency_overrides)
        app.dependency_overrides.clear()

        fake = FakeFirestoreClient()
        with patch(
            "core.persistence.repositories.base.get_firestore_client",
            return_value=fake,
        ):
            app.state.spatialite_manager = SpatiaLiteManager()
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/waypoints")
                assert resp.status_code in (401, 422)  # 422 if header missing validation

        # Restore overrides
        app.dependency_overrides = overrides

    async def test_dev_auth_bypass(self):
        """When SKYWEB_AUTH_DISABLED=1, auth should be bypassed."""
        fake = FakeFirestoreClient()

        app.dependency_overrides.clear()
        with patch(
            "core.persistence.repositories.base.get_firestore_client",
            return_value=fake,
        ), patch.dict(os.environ, {"SKYWEB_AUTH_DISABLED": "1"}):
            app.state.spatialite_manager = SpatiaLiteManager()
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get(
                    "/api/waypoints",
                    headers={"Authorization": "Bearer fake-token"},
                )
                assert resp.status_code == 200

        app.dependency_overrides.clear()

    async def test_health_no_auth(self, client):
        """Health endpoint should work without auth."""
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
