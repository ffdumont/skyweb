"""Unit tests for Firestore repositories using FakeFirestoreClient."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from core.contracts.enums import (
    LocationType,
    WaypointRole,
    WaypointSource,
)
from core.contracts.route import Route, RouteLeg, RouteWaypointRef
from core.contracts.waypoint import UserWaypoint
from core.persistence.repositories.aircraft_repo import AircraftRepository
from core.persistence.repositories.route_repo import RouteRepository
from core.persistence.repositories.waypoint_repo import WaypointRepository
from tests.persistence.fake_firestore import FakeFirestoreClient

USER_ID = "test-user-123"


@pytest.fixture
def fake_client():
    return FakeFirestoreClient()


@pytest.fixture(autouse=True)
def patch_firestore(fake_client):
    with patch(
        "core.persistence.firestore_client.get_firestore_client",
        return_value=fake_client,
    ):
        # Also patch in each repo module that imports it
        with patch(
            "core.persistence.repositories.base.get_firestore_client",
            return_value=fake_client,
        ):
            with patch(
                "core.persistence.repositories.waypoint_repo.get_firestore_client",
                return_value=fake_client,
            ):
                with patch(
                    "core.persistence.repositories.route_repo.get_firestore_client",
                    return_value=fake_client,
                ):
                    yield


def _make_waypoint(name: str, lat: float, lon: float) -> UserWaypoint:
    return UserWaypoint(
        name=name,
        latitude=lat,
        longitude=lon,
        location_type=LocationType.GPS_POINT,
        source=WaypointSource.MANUAL,
        tags=["test"],
        created_at=datetime.now(timezone.utc),
    )


def _make_route(waypoints: list[UserWaypoint]) -> Route:
    refs = []
    for i, wp in enumerate(waypoints):
        if i == 0:
            role = WaypointRole.DEPARTURE
        elif i == len(waypoints) - 1:
            role = WaypointRole.ARRIVAL
        else:
            role = WaypointRole.ENROUTE
        refs.append(RouteWaypointRef(
            waypoint_id=wp.id, sequence_order=i + 1, role=role
        ))

    legs = [
        RouteLeg(from_seq=i + 1, to_seq=i + 2, planned_altitude_ft=1500)
        for i in range(len(waypoints) - 1)
    ]

    return Route(name="Test Route", waypoints=refs, legs=legs)


# ---------------------------------------------------------------------------
# WaypointRepository
# ---------------------------------------------------------------------------


class TestWaypointRepository:
    @pytest.mark.asyncio
    async def test_create_and_get(self):
        repo = WaypointRepository()
        wp = _make_waypoint("POINT A", 48.0, 2.0)

        doc_id = await repo.create(USER_ID, wp)
        assert doc_id == wp.id  # Deterministic ID

        restored = await repo.get(USER_ID, doc_id)
        assert restored is not None
        assert restored.name == "POINT A"
        assert restored.latitude == 48.0
        assert restored.id == wp.id

    @pytest.mark.asyncio
    async def test_create_deduplication(self):
        repo = WaypointRepository()
        wp = _make_waypoint("POINT A", 48.0, 2.0)

        id1 = await repo.create(USER_ID, wp)
        id2 = await repo.create(USER_ID, wp)
        assert id1 == id2  # Same waypoint → same document

    @pytest.mark.asyncio
    async def test_list_all(self):
        repo = WaypointRepository()
        wp1 = _make_waypoint("ALPHA", 48.0, 2.0)
        wp2 = _make_waypoint("BRAVO", 49.0, 3.0)

        await repo.create(USER_ID, wp1)
        await repo.create(USER_ID, wp2)

        all_wps = await repo.list_all(USER_ID)
        assert len(all_wps) == 2
        names = {wp.name for wp in all_wps}
        assert names == {"ALPHA", "BRAVO"}

    @pytest.mark.asyncio
    async def test_get_by_ids(self):
        repo = WaypointRepository()
        wp1 = _make_waypoint("ALPHA", 48.0, 2.0)
        wp2 = _make_waypoint("BRAVO", 49.0, 3.0)

        await repo.create(USER_ID, wp1)
        await repo.create(USER_ID, wp2)

        result = await repo.get_by_ids(USER_ID, [wp1.id, wp2.id])
        assert len(result) == 2
        assert result[wp1.id].name == "ALPHA"
        assert result[wp2.id].name == "BRAVO"

    @pytest.mark.asyncio
    async def test_get_by_ids_empty(self):
        repo = WaypointRepository()
        result = await repo.get_by_ids(USER_ID, [])
        assert result == {}

    @pytest.mark.asyncio
    async def test_find_by_tag(self):
        repo = WaypointRepository()
        wp = _make_waypoint("CHARLIE", 48.5, 2.5)
        await repo.create(USER_ID, wp)

        results = await repo.find_by_tag(USER_ID, "test")
        assert len(results) == 1
        assert results[0].name == "CHARLIE"

    @pytest.mark.asyncio
    async def test_delete(self):
        repo = WaypointRepository()
        wp = _make_waypoint("DELTA", 47.0, 1.0)
        doc_id = await repo.create(USER_ID, wp)

        await repo.delete(USER_ID, doc_id)

        result = await repo.get(USER_ID, doc_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        repo = WaypointRepository()
        result = await repo.get(USER_ID, "does-not-exist")
        assert result is None

    @pytest.mark.asyncio
    async def test_user_isolation(self):
        repo = WaypointRepository()
        wp = _make_waypoint("ECHO", 48.0, 2.0)
        await repo.create("user-A", wp)

        # Different user cannot see the waypoint
        result = await repo.get("user-B", wp.id)
        assert result is None


# ---------------------------------------------------------------------------
# RouteRepository
# ---------------------------------------------------------------------------


class TestRouteRepository:
    @pytest.mark.asyncio
    async def test_save_with_waypoints(self):
        repo = RouteRepository()
        wp1 = _make_waypoint("DEP", 48.0, 2.0)
        wp2 = _make_waypoint("ARR", 47.0, 3.0)
        route = _make_route([wp1, wp2])

        route_id = await repo.save_with_waypoints(USER_ID, route, [wp1, wp2])
        assert route_id is not None

        # Route should be retrievable
        restored = await repo.get(USER_ID, route_id)
        assert restored is not None
        assert restored.name == "Test Route"
        assert len(restored.waypoints) == 2
        assert len(restored.legs) == 1

    @pytest.mark.asyncio
    async def test_save_promotes_waypoints(self, fake_client):
        repo = RouteRepository()
        wp_repo = WaypointRepository()

        wp1 = _make_waypoint("DEP", 48.0, 2.0)
        wp2 = _make_waypoint("ARR", 47.0, 3.0)
        route = _make_route([wp1, wp2])

        await repo.save_with_waypoints(USER_ID, route, [wp1, wp2])

        # Waypoints should exist in the waypoint collection
        restored_wp = await wp_repo.get(USER_ID, wp1.id)
        assert restored_wp is not None
        assert restored_wp.name == "DEP"

    @pytest.mark.asyncio
    async def test_route_roundtrip(self):
        repo = RouteRepository()
        wp1 = _make_waypoint("A", 48.0, 2.0)
        wp2 = _make_waypoint("B", 48.5, 2.5)
        wp3 = _make_waypoint("C", 47.0, 3.0)
        route = _make_route([wp1, wp2, wp3])

        route_id = await repo.save_with_waypoints(USER_ID, route, [wp1, wp2, wp3])
        restored = await repo.get(USER_ID, route_id)

        assert restored is not None
        assert len(restored.waypoints) == 3
        assert len(restored.legs) == 2
        assert restored.legs[0].planned_altitude_ft == 1500

    @pytest.mark.asyncio
    async def test_list_all(self):
        repo = RouteRepository()
        wp1 = _make_waypoint("A", 48.0, 2.0)
        wp2 = _make_waypoint("B", 47.0, 3.0)

        route1 = Route(
            name="Route 1",
            waypoints=[
                RouteWaypointRef(waypoint_id=wp1.id, sequence_order=1, role=WaypointRole.DEPARTURE),
                RouteWaypointRef(waypoint_id=wp2.id, sequence_order=2, role=WaypointRole.ARRIVAL),
            ],
            legs=[RouteLeg(from_seq=1, to_seq=2, planned_altitude_ft=2000)],
        )
        route2 = Route(
            name="Route 2",
            waypoints=[
                RouteWaypointRef(waypoint_id=wp2.id, sequence_order=1, role=WaypointRole.DEPARTURE),
                RouteWaypointRef(waypoint_id=wp1.id, sequence_order=2, role=WaypointRole.ARRIVAL),
            ],
            legs=[RouteLeg(from_seq=1, to_seq=2, planned_altitude_ft=3000)],
        )

        await repo.create(USER_ID, route1)
        await repo.create(USER_ID, route2)

        all_routes = await repo.list_all(USER_ID)
        assert len(all_routes) == 2


# ---------------------------------------------------------------------------
# Roundtrip: to_firestore → store → from_firestore preserves data
# ---------------------------------------------------------------------------


class TestFirestoreRoundtrip:
    @pytest.mark.asyncio
    async def test_waypoint_roundtrip_preserves_all_fields(self):
        repo = WaypointRepository()
        wp = UserWaypoint(
            name="LFXU - LES MUREAUX",
            latitude=48.998611,
            longitude=1.941667,
            location_type=LocationType.AERODROME,
            icao_code="LFXU",
            source=WaypointSource.SDVFR_IMPORT,
            tags=["departure", "ile-de-france"],
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        doc_id = await repo.create(USER_ID, wp)
        restored = await repo.get(USER_ID, doc_id)

        assert restored is not None
        assert restored.name == wp.name
        assert restored.latitude == wp.latitude
        assert restored.longitude == wp.longitude
        assert restored.location_type == wp.location_type
        assert restored.icao_code == wp.icao_code
        assert restored.source == wp.source
        assert restored.tags == wp.tags
        assert restored.id == wp.id

    @pytest.mark.asyncio
    async def test_route_roundtrip_preserves_all_fields(self):
        repo = RouteRepository()
        wp1 = _make_waypoint("DEP", 48.0, 2.0)
        wp2 = _make_waypoint("MID", 48.5, 2.5)
        wp3 = _make_waypoint("ARR", 47.0, 3.0)

        route = Route(
            name="LFXU-LFFU",
            waypoints=[
                RouteWaypointRef(waypoint_id=wp1.id, sequence_order=1, role=WaypointRole.DEPARTURE),
                RouteWaypointRef(waypoint_id=wp2.id, sequence_order=2, role=WaypointRole.ENROUTE),
                RouteWaypointRef(waypoint_id=wp3.id, sequence_order=3, role=WaypointRole.ARRIVAL),
            ],
            legs=[
                RouteLeg(from_seq=1, to_seq=2, planned_altitude_ft=1400),
                RouteLeg(from_seq=2, to_seq=3, planned_altitude_ft=2500),
            ],
        )

        route_id = await repo.save_with_waypoints(USER_ID, route, [wp1, wp2, wp3])
        restored = await repo.get(USER_ID, route_id)

        assert restored is not None
        assert restored.name == "LFXU-LFFU"
        assert restored.waypoints[0].role == WaypointRole.DEPARTURE
        assert restored.waypoints[2].role == WaypointRole.ARRIVAL
        assert restored.legs[0].planned_altitude_ft == 1400
        assert restored.legs[1].planned_altitude_ft == 2500
