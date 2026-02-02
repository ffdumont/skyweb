"""Tests for aircraft API endpoints."""

from __future__ import annotations


class TestAircraftAPI:
    async def test_list_empty(self, client):
        resp = await client.get("/api/aircraft")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_and_get(self, client):
        payload = {
            "registration": "F-GKXU",
            "aircraft_type": "DR400/120",
            "empty_weight_kg": 570.0,
            "empty_arm_m": 0.413,
            "mtow_kg": 900.0,
            "fuel_capacity_liters": 110.0,
            "cruise_speed_kt": 105,
            "envelope": [],
            "loading_stations": [],
        }
        resp = await client.post("/api/aircraft", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["registration"] == "F-GKXU"
        assert "id" in data

        ac_id = data["id"]
        resp = await client.get(f"/api/aircraft/{ac_id}")
        assert resp.status_code == 200
        assert resp.json()["aircraft_type"] == "DR400/120"

    async def test_delete(self, client):
        payload = {
            "registration": "F-TEST",
            "aircraft_type": "C172",
            "empty_weight_kg": 650.0,
            "empty_arm_m": 0.4,
            "mtow_kg": 1100.0,
            "fuel_capacity_liters": 160.0,
            "cruise_speed_kt": 110,
            "envelope": [],
            "loading_stations": [],
        }
        resp = await client.post("/api/aircraft", json=payload)
        ac_id = resp.json()["id"]

        resp = await client.delete(f"/api/aircraft/{ac_id}")
        assert resp.status_code == 204

    async def test_get_not_found(self, client):
        resp = await client.get("/api/aircraft/nonexistent")
        assert resp.status_code == 404
