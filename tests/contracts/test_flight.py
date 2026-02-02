"""Tests for Flight and Track contracts."""

from datetime import datetime, timezone

from core.contracts.flight import Flight, StationLoad, Track, WaypointPassageTime
from core.contracts.enums import FlightStatus, TrackSource


class TestTrack:
    def test_empty_track(self):
        track = Track()
        assert track.passage_times == []
        assert track.source == TrackSource.GPX_FILE

    def test_track_with_passages(self):
        passages = [
            WaypointPassageTime(
                waypoint_id="wp01",
                sequence_order=1,
                passage_time_utc=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
                latitude=48.9986,
                longitude=1.9417,
            ),
            WaypointPassageTime(
                waypoint_id="wp02",
                sequence_order=2,
                passage_time_utc=datetime(2026, 3, 15, 10, 12, tzinfo=timezone.utc),
            ),
        ]
        track = Track(
            gpx_ref="gs://skyweb-users/user1/flights/f1/track.gpx",
            passage_times=passages,
            total_distance_nm=45.2,
            total_time_minutes=72.5,
        )
        assert len(track.passage_times) == 2
        assert track.passage_times[0].latitude == 48.9986

    def test_track_serialization(self):
        track = Track(
            gpx_ref="gs://bucket/track.gpx",
            passage_times=[
                WaypointPassageTime(
                    waypoint_id="wp01",
                    sequence_order=1,
                    passage_time_utc=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
                ),
            ],
        )
        data = track.to_firestore()
        ts = data["passage_times"][0]["passage_time_utc"]
        assert ts.endswith("Z") or ts.endswith("+00:00")
        restored = Track.from_firestore(data)
        assert restored.passage_times[0].waypoint_id == "wp01"


class TestFlight:
    def test_default_status(self):
        flight = Flight(
            route_id="route1",
            departure_datetime_utc=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
        )
        assert flight.status == FlightStatus.DRAFT
        assert flight.track is None

    def test_flight_with_track(self):
        flight = Flight(
            route_id="route1",
            departure_datetime_utc=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
            status=FlightStatus.COMPLETED,
            track=Track(gpx_ref="gs://bucket/track.gpx"),
        )
        assert flight.track is not None
        assert flight.track.gpx_ref == "gs://bucket/track.gpx"

    def test_flight_with_station_loads(self):
        flight = Flight(
            route_id="route1",
            aircraft_id="fhbct",
            departure_datetime_utc=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
            station_loads=[
                StationLoad(station_name="Equipage", weight_kg=80.0),
                StationLoad(station_name="Passager(s)", weight_kg=75.0),
                StationLoad(station_name="Bagages", weight_kg=10.0),
                StationLoad(station_name="Carburant", weight_kg=30.0),
            ],
        )
        assert len(flight.station_loads) == 4
        assert flight.station_loads[0].weight_kg == 80.0

    def test_flight_serialization_roundtrip(self):
        flight = Flight(
            route_id="route1",
            aircraft_id="fhbct",
            departure_datetime_utc=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
            status=FlightStatus.PLANNED,
            station_loads=[
                StationLoad(station_name="Equipage", weight_kg=80.0),
                StationLoad(station_name="Carburant", weight_kg=30.0),
            ],
        )
        data = flight.to_firestore()
        assert data["status"] == "planned"
        assert "track" not in data  # None excluded
        assert len(data["station_loads"]) == 2

        restored = Flight.from_firestore(data)
        assert restored.route_id == "route1"
        assert restored.station_loads[0].station_name == "Equipage"
