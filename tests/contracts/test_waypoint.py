"""Tests for Waypoint and UserWaypoint contracts."""

import hashlib

import pytest

from core.contracts.waypoint import UserWaypoint, Waypoint, waypoint_id
from core.contracts.enums import LocationType, WaypointSource


class TestWaypoint:
    """Tests for the ephemeral Waypoint."""

    def test_deterministic_id(self):
        wp = Waypoint(name="LFXU - LES MUREAUX", latitude=48.9986, longitude=1.9417)
        expected = hashlib.md5("LFXU - LES MUREAUX:48.9986:1.9417".encode()).hexdigest()[:16]
        assert wp.id == expected

    def test_same_inputs_same_id(self):
        wp1 = Waypoint(name="MOR1V", latitude=48.9412, longitude=1.9532)
        wp2 = Waypoint(name="MOR1V", latitude=48.9412, longitude=1.9532)
        assert wp1.id == wp2.id

    def test_different_inputs_different_id(self):
        wp1 = Waypoint(name="MOR1V", latitude=48.9412, longitude=1.9532)
        wp2 = Waypoint(name="PXSW", latitude=48.8343, longitude=1.9305)
        assert wp1.id != wp2.id

    def test_waypoint_id_helper(self):
        wp = Waypoint(name="LFXU", latitude=48.9986, longitude=1.9417)
        assert wp.id == waypoint_id("LFXU", 48.9986, 1.9417)

    def test_default_location_type(self):
        wp = Waypoint(name="MOR1V", latitude=48.0, longitude=1.0)
        assert wp.location_type == LocationType.GPS_POINT

    def test_aerodrome_location_type(self):
        wp = Waypoint(
            name="LFXU",
            latitude=48.0,
            longitude=1.0,
            location_type=LocationType.AERODROME,
            icao_code="LFXU",
        )
        assert wp.location_type == LocationType.AERODROME

    def test_strip_name(self):
        wp = Waypoint(name="  LFXU  ", latitude=48.0, longitude=1.0)
        assert wp.name == "LFXU"

    def test_no_persistence_fields(self):
        """Ephemeral Waypoint has no source, tags, or timestamps."""
        wp = Waypoint(name="TEST", latitude=48.0, longitude=1.0)
        assert not hasattr(wp, "source")
        assert not hasattr(wp, "tags")
        assert not hasattr(wp, "created_at")


class TestUserWaypoint:
    """Tests for the persisted UserWaypoint."""

    def test_inherits_waypoint_id(self):
        wp = Waypoint(name="LFXU", latitude=48.9986, longitude=1.9417)
        uwp = UserWaypoint(name="LFXU", latitude=48.9986, longitude=1.9417)
        assert wp.id == uwp.id

    def test_default_source(self):
        wp = UserWaypoint(name="LFXU", latitude=48.0, longitude=1.0)
        assert wp.source == WaypointSource.MANUAL

    def test_lowercase_tags(self):
        wp = UserWaypoint(
            name="LFXU", latitude=48.0, longitude=1.0, tags=["IDF", " Favori "]
        )
        assert wp.tags == ["idf", "favori"]

    def test_has_timestamps(self):
        wp = UserWaypoint(name="LFXU", latitude=48.0, longitude=1.0)
        assert wp.created_at is not None
        assert wp.updated_at is None


class TestWaypointValidation:
    def test_empty_name_rejected(self):
        with pytest.raises(Exception):
            Waypoint(name="", latitude=48.0, longitude=1.0)

    def test_latitude_bounds(self):
        with pytest.raises(Exception):
            Waypoint(name="TEST", latitude=91.0, longitude=1.0)

    def test_longitude_bounds(self):
        with pytest.raises(Exception):
            Waypoint(name="TEST", latitude=48.0, longitude=181.0)

    def test_icao_code_pattern(self):
        wp = Waypoint(name="LFXU", latitude=48.0, longitude=1.0, icao_code="LFXU")
        assert wp.icao_code == "LFXU"

    def test_icao_code_invalid(self):
        with pytest.raises(Exception):
            Waypoint(name="LFXU", latitude=48.0, longitude=1.0, icao_code="abc")


class TestUserWaypointSerialization:
    def test_roundtrip(self):
        wp = UserWaypoint(
            name="LFXU - LES MUREAUX",
            latitude=48.9986,
            longitude=1.9417,
            location_type=LocationType.AERODROME,
            source=WaypointSource.SDVFR_IMPORT,
            tags=["idf"],
            icao_code="LFXU",
        )
        data = wp.to_firestore()
        restored = UserWaypoint.from_firestore(data)

        assert restored.name == wp.name
        assert restored.latitude == wp.latitude
        assert restored.longitude == wp.longitude
        assert restored.id == wp.id
        assert restored.tags == wp.tags

    def test_exclude_none(self):
        wp = UserWaypoint(name="TEST", latitude=48.0, longitude=1.0)
        data = wp.to_firestore()
        assert "description" not in data
        assert "icao_code" not in data
        assert "updated_at" not in data

    def test_enum_as_string(self):
        wp = UserWaypoint(
            name="LFXU",
            latitude=48.0,
            longitude=1.0,
            location_type=LocationType.AERODROME,
        )
        data = wp.to_firestore()
        assert data["location_type"] == "aerodrome"
        assert data["source"] == "manual"
