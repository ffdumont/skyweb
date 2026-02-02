"""Tests for Weather contracts — multi-model simulation."""

from datetime import datetime, timezone

from core.contracts.weather import (
    ForecastData,
    ModelPoint,
    ModelResult,
    ObservationData,
    VFRIndex,
    WaypointContext,
    WeatherSimulation,
)
from core.contracts.enums import ForecastModel, VFRStatus


class TestForecastData:
    def test_pressure_level_dict(self):
        fd = ForecastData(
            temperature_2m=15.0,
            temperature_levels={1000: 12.5, 925: 8.1, 850: 3.2},
            wind_speed_levels={925: 12.0, 850: 18.0},
            wind_direction_levels={925: 270, 850: 280},
        )
        assert fd.temperature_levels[925] == 8.1
        assert fd.wind_speed_levels[850] == 18.0

    def test_pressure_level_serialization(self):
        """Firestore stores dict keys as strings; Pydantic coerces back to int."""
        fd = ForecastData(temperature_levels={1000: 12.5, 925: 8.1})
        data = fd.to_firestore()
        # JSON mode converts int keys to strings
        assert "1000" in data["temperature_levels"]

        restored = ForecastData.from_firestore(data)
        assert 1000 in restored.temperature_levels
        assert restored.temperature_levels[1000] == 12.5


class TestVFRIndex:
    def test_green(self):
        idx = VFRIndex(
            status=VFRStatus.GREEN,
            visibility_ok=True,
            ceiling_ok=True,
            wind_ok=True,
            details="VMC comfortable",
        )
        assert idx.status == VFRStatus.GREEN

    def test_serialization(self):
        idx = VFRIndex(
            status=VFRStatus.RED,
            visibility_ok=False,
            ceiling_ok=False,
            wind_ok=True,
        )
        data = idx.to_firestore()
        assert data["status"] == "red"


class TestWeatherSimulation:
    def _make_simulation(self) -> WeatherSimulation:
        now = datetime(2026, 3, 14, 18, 0, tzinfo=timezone.utc)
        nav_time = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)

        waypoints = [
            WaypointContext(
                waypoint_name="LFXU",
                waypoint_index=0,
                latitude=48.9986,
                longitude=1.9417,
                icao="LFXU",
                estimated_time_utc=nav_time,
            ),
            WaypointContext(
                waypoint_name="LFFU",
                waypoint_index=1,
                latitude=46.8711,
                longitude=2.3769,
                icao="LFFU",
                estimated_time_utc=datetime(2026, 3, 15, 11, 30, tzinfo=timezone.utc),
            ),
        ]

        arome_points = [
            ModelPoint(
                waypoint_index=0,
                forecast=ForecastData(
                    temperature_2m=12.0,
                    wind_speed_10m=8.0,
                    wind_direction_10m=270,
                    visibility=9999,
                    cloud_cover=30,
                ),
                vfr_index=VFRIndex(
                    status=VFRStatus.GREEN,
                    visibility_ok=True,
                    ceiling_ok=True,
                    wind_ok=True,
                ),
            ),
            ModelPoint(
                waypoint_index=1,
                forecast=ForecastData(
                    temperature_2m=10.0,
                    wind_speed_10m=12.0,
                    wind_direction_10m=250,
                    visibility=6000,
                    cloud_cover=70,
                ),
                vfr_index=VFRIndex(
                    status=VFRStatus.YELLOW,
                    visibility_ok=True,
                    ceiling_ok=True,
                    wind_ok=False,
                    details="Wind gusts near limit",
                ),
            ),
        ]

        model_results = [
            ModelResult(
                model=ForecastModel.AROME_FRANCE,
                model_run_time=datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc),
                points=arome_points,
            ),
        ]

        return WeatherSimulation(
            id="sim001",
            route_id="route1",
            simulated_at=now,
            navigation_datetime=nav_time,
            waypoints=waypoints,
            model_results=model_results,
        )

    def test_simulation_structure(self):
        sim = self._make_simulation()
        assert len(sim.waypoints) == 2
        assert len(sim.model_results) == 1
        assert sim.model_results[0].model == ForecastModel.AROME_FRANCE
        assert len(sim.model_results[0].points) == 2

    def test_simulation_serialization_roundtrip(self):
        sim = self._make_simulation()
        data = sim.to_firestore()

        assert data["model_results"][0]["model"] == "arome_france"
        assert data["waypoints"][0]["icao"] == "LFXU"

        restored = WeatherSimulation.from_firestore(data)
        assert restored.route_id == "route1"
        assert len(restored.model_results) == 1
        assert restored.model_results[0].points[1].vfr_index.status == VFRStatus.YELLOW

    def test_observation_enrichment(self):
        """Waypoint context can carry actual observation after flight."""
        ctx = WaypointContext(
            waypoint_name="LFXU",
            waypoint_index=0,
            latitude=48.9986,
            longitude=1.9417,
            icao="LFXU",
            estimated_time_utc=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
            actual_time_utc=datetime(2026, 3, 15, 10, 5, tzinfo=timezone.utc),
            observation=ObservationData(
                observation_time=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
                icao="LFXU",
                temperature=11.0,
                wind_speed=6.0,
                wind_direction=260,
                visibility=9999,
                raw_metar="LFXU 151000Z 26006KT 9999 FEW030 11/06 Q1018",
            ),
        )
        data = ctx.to_firestore()
        assert data["observation"]["raw_metar"].startswith("LFXU")
