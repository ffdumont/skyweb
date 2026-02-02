"""Tests for waypoint API endpoints."""

from __future__ import annotations

import pytest


class TestWaypointAPI:
    async def test_list_empty(self, client):
        resp = await client.get("/api/waypoints")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_and_get(self, client):
        payload = {
            "name": "LFXU - LES MUREAUX",
            "latitude": 48.9897,
            "longitude": 1.8815,
            "location_type": "aerodrome",
            "icao_code": "LFXU",
            "source": "manual",
            "tags": ["training"],
        }
        resp = await client.post("/api/waypoints", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "LFXU - LES MUREAUX"
        assert "id" in data

        # Fetch it back
        wp_id = data["id"]
        resp = await client.get(f"/api/waypoints/{wp_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "LFXU - LES MUREAUX"

    async def test_get_not_found(self, client):
        resp = await client.get("/api/waypoints/nonexistent")
        assert resp.status_code == 404

    async def test_delete(self, client):
        payload = {
            "name": "Test Point",
            "latitude": 48.0,
            "longitude": 2.0,
            "location_type": "gps_point",
            "source": "manual",
        }
        resp = await client.post("/api/waypoints", json=payload)
        wp_id = resp.json()["id"]

        resp = await client.delete(f"/api/waypoints/{wp_id}")
        assert resp.status_code == 204

    async def test_list_returns_created(self, client):
        payload = {
            "name": "Point A",
            "latitude": 47.0,
            "longitude": 1.0,
            "location_type": "gps_point",
            "source": "manual",
        }
        await client.post("/api/waypoints", json=payload)

        resp = await client.get("/api/waypoints")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1

    async def test_search_by_tag(self, client):
        payload = {
            "name": "Tagged Point",
            "latitude": 46.0,
            "longitude": 0.5,
            "location_type": "gps_point",
            "source": "manual",
            "tags": ["vfr", "training"],
        }
        await client.post("/api/waypoints", json=payload)

        resp = await client.get("/api/waypoints/search", params={"tag": "vfr"})
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1
        assert any("vfr" in wp.get("tags", []) for wp in items)
