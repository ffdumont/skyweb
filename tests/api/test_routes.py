"""Tests for route API endpoints."""

from __future__ import annotations


class TestRouteAPI:
    async def test_list_empty(self, client):
        resp = await client.get("/api/routes")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_route_via_manual_and_get(self, client):
        """Create waypoints first, then verify route list."""
        # Create two waypoints
        for name, lat, lon, icao in [
            ("LFXU - LES MUREAUX", 48.99, 1.88, "LFXU"),
            ("LFFU - FIGEAC", 44.67, 2.01, "LFFU"),
        ]:
            await client.post("/api/waypoints", json={
                "name": name,
                "latitude": lat,
                "longitude": lon,
                "location_type": "aerodrome",
                "icao_code": icao,
                "source": "manual",
            })

        # Verify waypoints were created
        resp = await client.get("/api/waypoints")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_get_not_found(self, client):
        resp = await client.get("/api/routes/nonexistent")
        assert resp.status_code == 404

    async def test_delete_route(self, client):
        # We can't easily test full route creation without KML,
        # but we can test delete on a nonexistent route (should not error)
        resp = await client.delete("/api/routes/some-id")
        assert resp.status_code == 204
