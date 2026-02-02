"""Tests for flight API endpoints."""

from __future__ import annotations


class TestFlightAPI:
    async def test_list_empty(self, client):
        resp = await client.get("/api/flights")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_and_get(self, client):
        payload = {
            "route_id": "route-123",
            "aircraft_id": "ac-456",
            "departure_datetime_utc": "2025-06-15T08:00:00",
            "status": "draft",
        }
        resp = await client.post("/api/flights", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["route_id"] == "route-123"
        assert "id" in data

        flight_id = data["id"]
        resp = await client.get(f"/api/flights/{flight_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "draft"

    async def test_filter_by_status(self, client):
        for status in ["draft", "planned", "draft"]:
            await client.post("/api/flights", json={
                "route_id": "r1",
                "aircraft_id": "a1",
                "departure_datetime_utc": "2025-06-15T08:00:00",
                "status": status,
            })

        resp = await client.get("/api/flights", params={"status": "planned"})
        assert resp.status_code == 200
        items = resp.json()
        assert all(f["status"] == "planned" for f in items)

    async def test_get_not_found(self, client):
        resp = await client.get("/api/flights/nonexistent")
        assert resp.status_code == 404
