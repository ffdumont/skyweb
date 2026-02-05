"""Tests for Dossier and Track contracts."""

from datetime import datetime, timezone

from core.contracts.dossier import Dossier, StationLoad, Track, WaypointPassageTime
from core.contracts.enums import DossierStatus, SectionCompletion, TrackSource


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
            gpx_ref="gs://skyweb-users/user1/dossiers/d1/track.gpx",
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


class TestDossier:
    def test_default_status(self):
        dossier = Dossier(
            name="LFMT → LFBO",
            route_id="route1",
            departure_datetime_utc=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
        )
        assert dossier.status == DossierStatus.DRAFT
        assert dossier.track is None

    def test_default_sections(self):
        dossier = Dossier(
            name="LFMT → LFBO",
            route_id="route1",
            departure_datetime_utc=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
        )
        assert len(dossier.sections) == 9
        assert all(v == SectionCompletion.EMPTY.value for v in dossier.sections.values())
        assert "route" in dossier.sections
        assert "meteo" in dossier.sections

    def test_dossier_with_track(self):
        dossier = Dossier(
            name="LFMT → LFBO",
            route_id="route1",
            departure_datetime_utc=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
            status=DossierStatus.ARCHIVED,
            track=Track(gpx_ref="gs://bucket/track.gpx"),
        )
        assert dossier.track is not None
        assert dossier.track.gpx_ref == "gs://bucket/track.gpx"

    def test_dossier_with_station_loads(self):
        dossier = Dossier(
            name="LFMT → LFBO",
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
        assert len(dossier.station_loads) == 4
        assert dossier.station_loads[0].weight_kg == 80.0

    def test_dossier_with_alternates_and_tem(self):
        dossier = Dossier(
            name="LFMT → LFBO",
            route_id="route1",
            departure_datetime_utc=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
            alternate_icao=["LFBZ", "LFBP"],
            tem_threats=["Vent traversier > 15 kt"],
            tem_mitigations=["Choix piste adaptée"],
        )
        assert dossier.alternate_icao == ["LFBZ", "LFBP"]
        assert len(dossier.tem_threats) == 1

    def test_dossier_serialization_roundtrip(self):
        dossier = Dossier(
            name="LFMT → LFBO",
            route_id="route1",
            aircraft_id="fhbct",
            departure_datetime_utc=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
            status=DossierStatus.PREPARING,
            station_loads=[
                StationLoad(station_name="Equipage", weight_kg=80.0),
                StationLoad(station_name="Carburant", weight_kg=30.0),
            ],
        )
        data = dossier.to_firestore()
        assert data["status"] == "preparing"
        assert "track" not in data  # None excluded
        assert len(data["station_loads"]) == 2
        assert len(data["sections"]) == 9

        restored = Dossier.from_firestore(data)
        assert restored.route_id == "route1"
        assert restored.station_loads[0].station_name == "Equipage"
        assert restored.name == "LFMT → LFBO"
