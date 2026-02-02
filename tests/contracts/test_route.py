"""Tests for Route, RouteLeg, RouteProjection contracts."""

from datetime import datetime, timezone

import pytest

from core.contracts.route import (
    ProjectionAssumptions,
    Route,
    RouteLeg,
    RouteProjection,
    RouteWaypointRef,
)
from core.contracts.enums import WaypointRole


class TestRouteLeg:
    def test_valid_leg(self):
        leg = RouteLeg(from_seq=1, to_seq=2, planned_altitude_ft=1400)
        assert leg.from_seq == 1
        assert leg.to_seq == 2

    def test_non_consecutive_rejected(self):
        with pytest.raises(Exception, match="to_seq"):
            RouteLeg(from_seq=1, to_seq=3, planned_altitude_ft=1400)

    def test_altitude_bounds(self):
        with pytest.raises(Exception):
            RouteLeg(from_seq=1, to_seq=2, planned_altitude_ft=-100)

    def test_altitude_upper_bound(self):
        with pytest.raises(Exception):
            RouteLeg(from_seq=1, to_seq=2, planned_altitude_ft=20000)

    def test_computed_fields_default_none(self):
        leg = RouteLeg(from_seq=1, to_seq=2, planned_altitude_ft=1400)
        assert leg.distance_nm is None
        assert leg.true_heading_deg is None
        assert leg.ground_speed_kt is None

    def test_leg_with_computed_fields(self):
        leg = RouteLeg(
            from_seq=3,
            to_seq=4,
            planned_altitude_ft=1800,
            distance_nm=28.7,
            true_heading_deg=180.0,
            magnetic_heading_deg=178.5,
            ground_speed_kt=95.0,
            estimated_time_minutes=18.1,
            wind_correction_deg=-3.2,
            fuel_consumption_liters=5.4,
        )
        assert leg.estimated_time_minutes == 18.1
        assert leg.fuel_consumption_liters == 5.4

    def test_computed_fields_excluded_from_firestore_when_none(self):
        leg = RouteLeg(from_seq=1, to_seq=2, planned_altitude_ft=1400)
        data = leg.to_firestore()
        assert "distance_nm" not in data
        assert "true_heading_deg" not in data
        assert data["planned_altitude_ft"] == 1400

    def test_computed_fields_included_when_set(self):
        leg = RouteLeg(
            from_seq=1,
            to_seq=2,
            planned_altitude_ft=1400,
            distance_nm=15.0,
            true_heading_deg=90.0,
            ground_speed_kt=100.0,
        )
        data = leg.to_firestore()
        assert data["distance_nm"] == 15.0
        assert "magnetic_heading_deg" not in data
        restored = RouteLeg.from_firestore(data)
        assert restored.true_heading_deg == 90.0
        assert restored.magnetic_heading_deg is None


class TestRoute:
    def _make_waypoints(self, n: int) -> list[RouteWaypointRef]:
        return [
            RouteWaypointRef(waypoint_id=f"wp{i:02d}", sequence_order=i)
            for i in range(1, n + 1)
        ]

    def _make_legs(self, n_waypoints: int) -> list[RouteLeg]:
        return [
            RouteLeg(from_seq=i, to_seq=i + 1, planned_altitude_ft=1400 + i * 100)
            for i in range(1, n_waypoints)
        ]

    def test_valid_route(self):
        wps = self._make_waypoints(3)
        legs = self._make_legs(3)
        route = Route(name="LFXU-LFFU", waypoints=wps, legs=legs)
        assert len(route.waypoints) == 3
        assert len(route.legs) == 2

    def test_route_without_legs(self):
        wps = self._make_waypoints(3)
        route = Route(name="LFXU-LFFU", waypoints=wps)
        assert route.legs == []

    def test_minimum_two_waypoints(self):
        with pytest.raises(Exception):
            Route(
                name="SHORT",
                waypoints=[RouteWaypointRef(waypoint_id="wp01", sequence_order=1)],
            )

    def test_non_consecutive_sequence_rejected(self):
        with pytest.raises(Exception, match="consecutive"):
            Route(
                name="BAD",
                waypoints=[
                    RouteWaypointRef(waypoint_id="wp01", sequence_order=1),
                    RouteWaypointRef(waypoint_id="wp02", sequence_order=3),
                ],
            )

    def test_wrong_number_of_legs_rejected(self):
        wps = self._make_waypoints(3)
        with pytest.raises(Exception, match="legs"):
            Route(
                name="BAD",
                waypoints=wps,
                legs=[RouteLeg(from_seq=1, to_seq=2, planned_altitude_ft=1400)],
            )
        # only 1 leg for 3 waypoints, should need 2

    def test_leg_references_beyond_waypoints_rejected(self):
        wps = self._make_waypoints(2)
        with pytest.raises(Exception):
            Route(
                name="BAD",
                waypoints=wps,
                legs=[RouteLeg(from_seq=5, to_seq=6, planned_altitude_ft=1400)],
            )

    def test_serialization_roundtrip(self):
        wps = self._make_waypoints(4)
        legs = self._make_legs(4)
        route = Route(name="LFXU-LFFU", waypoints=wps, legs=legs)
        data = route.to_firestore()
        restored = Route.from_firestore(data)
        assert restored.name == route.name
        assert len(restored.waypoints) == 4
        assert len(restored.legs) == 3
        assert restored.legs[0].planned_altitude_ft == 1500

    def test_default_role_is_enroute(self):
        ref = RouteWaypointRef(waypoint_id="wp01", sequence_order=1)
        assert ref.role == WaypointRole.ENROUTE

    def test_role_serialization(self):
        ref = RouteWaypointRef(
            waypoint_id="wp01", sequence_order=1, role=WaypointRole.DEPARTURE
        )
        data = ref.to_firestore()
        assert data["role"] == "departure"

    def test_lfxu_lffu_example(self):
        """Real route example: LFXU → LFFU with 9 waypoints and roles."""
        wp_names = [
            "lfxu", "mor1v", "pxsw", "holan",
            "arnou", "oxww", "lfff_oe", "bevro", "lffu",
        ]
        roles = [
            WaypointRole.DEPARTURE,
            *[WaypointRole.ENROUTE] * 7,
            WaypointRole.ARRIVAL,
        ]
        wps = [
            RouteWaypointRef(waypoint_id=name, sequence_order=i + 1, role=role)
            for i, (name, role) in enumerate(zip(wp_names, roles))
        ]
        altitudes = [1400, 1400, 1800, 1800, 2300, 3100, 3100, 2900]
        legs = [
            RouteLeg(from_seq=i + 1, to_seq=i + 2, planned_altitude_ft=alt)
            for i, alt in enumerate(altitudes)
        ]
        route = Route(name="LFXU-LFFU", waypoints=wps, legs=legs)
        assert len(route.waypoints) == 9
        assert len(route.legs) == 8
        assert route.waypoints[0].role == WaypointRole.DEPARTURE
        assert route.waypoints[4].role == WaypointRole.ENROUTE
        assert route.waypoints[8].role == WaypointRole.ARRIVAL


class TestRouteProjection:
    """RouteProjection is an API response DTO — never persisted."""

    def test_projection_with_computed_legs(self):
        legs = [
            RouteLeg(
                from_seq=1,
                to_seq=2,
                planned_altitude_ft=1400,
                distance_nm=12.3,
                true_heading_deg=245.0,
                ground_speed_kt=95.0,
                estimated_time_minutes=7.8,
                fuel_consumption_liters=2.1,
            ),
            RouteLeg(
                from_seq=2,
                to_seq=3,
                planned_altitude_ft=1800,
                distance_nm=18.5,
                true_heading_deg=190.0,
                ground_speed_kt=100.0,
                estimated_time_minutes=11.1,
                fuel_consumption_liters=3.0,
            ),
        ]
        proj = RouteProjection(
            route_id="route1",
            route_name="LFXU-LFFU",
            legs=legs,
            assumptions=ProjectionAssumptions(
                aircraft_id="fhbct",
                cruise_speed_kt=100,
                departure_datetime_utc=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
                wind_source="arome_france",
            ),
            total_distance_nm=30.8,
            total_time_minutes=18.9,
            total_fuel_liters=5.1,
        )
        assert len(proj.legs) == 2
        assert proj.assumptions.wind_source == "arome_france"
        assert proj.total_distance_nm == 30.8
        assert proj.generated_at is not None

    def test_projection_without_fuel(self):
        """Fuel may be absent if no aircraft/fuel profile provided."""
        proj = RouteProjection(
            route_id="route1",
            route_name="Test",
            legs=[
                RouteLeg(
                    from_seq=1,
                    to_seq=2,
                    planned_altitude_ft=1400,
                    distance_nm=10.0,
                    true_heading_deg=90.0,
                ),
            ],
            assumptions=ProjectionAssumptions(cruise_speed_kt=100),
            total_distance_nm=10.0,
            total_time_minutes=6.0,
        )
        assert proj.total_fuel_liters is None
        assert proj.assumptions.aircraft_id is None

    def test_projection_serialization(self):
        proj = RouteProjection(
            route_id="route1",
            route_name="LFXU-LFFU",
            legs=[
                RouteLeg(
                    from_seq=1,
                    to_seq=2,
                    planned_altitude_ft=1400,
                    distance_nm=15.0,
                    true_heading_deg=90.0,
                ),
            ],
            assumptions=ProjectionAssumptions(cruise_speed_kt=100),
            total_distance_nm=15.0,
            total_time_minutes=9.0,
        )
        data = proj.to_firestore()
        assert data["assumptions"]["cruise_speed_kt"] == 100
        assert "total_fuel_liters" not in data  # None excluded
        assert "generated_at" in data
