"""Tests for dossier API endpoints."""

from __future__ import annotations


class TestDossierAPI:
    async def test_list_empty(self, client):
        resp = await client.get("/api/dossiers")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_and_get(self, client):
        payload = {
            "name": "LFMT → LFBO",
            "route_id": "route-123",
            "aircraft_id": "ac-456",
            "departure_datetime_utc": "2025-06-15T08:00:00",
            "status": "draft",
        }
        resp = await client.post("/api/dossiers", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["route_id"] == "route-123"
        assert data["name"] == "LFMT → LFBO"
        assert "id" in data
        assert "sections" in data
        assert len(data["sections"]) == 9

        dossier_id = data["id"]
        resp = await client.get(f"/api/dossiers/{dossier_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "draft"

    async def test_filter_by_status(self, client):
        for status in ["draft", "preparing", "draft"]:
            await client.post("/api/dossiers", json={
                "name": f"Dossier {status}",
                "route_id": "r1",
                "aircraft_id": "a1",
                "departure_datetime_utc": "2025-06-15T08:00:00",
                "status": status,
            })

        resp = await client.get("/api/dossiers", params={"status": "preparing"})
        assert resp.status_code == 200
        items = resp.json()
        assert all(d["status"] == "preparing" for d in items)

    async def test_get_not_found(self, client):
        resp = await client.get("/api/dossiers/nonexistent")
        assert resp.status_code == 404
