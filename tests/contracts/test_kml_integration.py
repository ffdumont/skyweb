"""Integration tests — validate contracts with real LFXU-LFFU KML data.

These tests parse the actual SD VFR KML file, build SkyWeb contract objects,
and verify Firestore roundtrip serialization on the complete data graph.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.adapters.kml_parser import build_route_from_kml, parse_kml_waypoints
from core.contracts import (
    AerodromeFrequency,
    AerodromeInfo,
    AerodromeService,
    AerodromeStatus,
    AirspaceIntersection,
    AirspaceType,
    CloudCover,
    CloudLayer,
    ForecastData,
    ForecastModel,
    FrequencyInfo,
    IntersectionType,
    LegAirspaces,
    LocationType,
    ModelPoint,
    ModelResult,
    ObservationData,
    Route,
    RouteAirspaceAnalysis,
    Runway,
    ServiceInfo,
    ServiceResult,
    VFRIndex,
    VFRStatus,
    Waypoint,
    WaypointContext,
    WaypointRole,
    WeatherSimulation,
)

KML_PATH = Path(
    r"C:\Users\franc\dev\skytools\skypath\data\routes"
    r"\LFXU-LFFU-2025-09-25-14-51-39.kml"
)
ROUTE_NAME = "LFXU-LFFU"
PLANNED_ALTITUDES_FT = [1400, 1400, 1800, 1800, 2300, 3100, 3100, 2900]

EXPECTED_NAMES = [
    "LFXU - LES MUREAUX",
    "MOR1V",
    "PXSW",
    "HOLAN",
    "ARNOU",
    "OXWW",
    "LFFF/OE",
    "BEVRO",
    "LFFU - CHATEAUNEUF SUR CHER",
]

requires_kml = pytest.mark.skipif(
    not KML_PATH.exists(), reason="SkyPath KML file not available"
)


@pytest.fixture
def kml_data():
    return parse_kml_waypoints(KML_PATH)


@pytest.fixture
def route_data():
    return build_route_from_kml(KML_PATH, ROUTE_NAME, PLANNED_ALTITUDES_FT)


# ---------------------------------------------------------------------------
# 1. KML Parsing → Waypoint contracts
# ---------------------------------------------------------------------------


@requires_kml
class TestKmlParsing:
    def test_parses_9_waypoints(self, kml_data):
        assert len(kml_data) == 9

    def test_waypoint_names_match(self, kml_data):
        names = [wp["name"] for wp in kml_data]
        assert names == EXPECTED_NAMES

    def test_coordinates_in_france(self, kml_data):
        for wp in kml_data:
            assert 45.0 <= wp["latitude"] <= 50.0, f"{wp['name']} lat out of range"
            assert 0.0 <= wp["longitude"] <= 4.0, f"{wp['name']} lon out of range"

    def test_departure_is_aerodrome(self, route_data):
        waypoints, _ = route_data
        dep = waypoints[0]
        assert dep.location_type == LocationType.AERODROME
        assert dep.icao_code == "LFXU"

    def test_arrival_is_aerodrome(self, route_data):
        waypoints, _ = route_data
        arr = waypoints[-1]
        assert arr.location_type == LocationType.AERODROME
        assert arr.icao_code == "LFFU"

    def test_enroute_are_gps_points(self, route_data):
        waypoints, _ = route_data
        for wp in waypoints[1:-1]:
            assert wp.location_type == LocationType.GPS_POINT
            assert wp.icao_code is None

    def test_deterministic_ids_unique(self, route_data):
        waypoints, _ = route_data
        ids = [wp.id for wp in waypoints]
        assert len(set(ids)) == 9
        assert all(len(wid) == 16 for wid in ids)

    def test_waypoint_firestore_roundtrip(self, route_data):
        waypoints, _ = route_data
        for wp in waypoints:
            data = wp.to_firestore()
            restored = Waypoint.from_firestore(data)
            assert restored.name == wp.name
            assert restored.latitude == wp.latitude
            assert restored.longitude == wp.longitude
            assert restored.id == wp.id
            assert restored.location_type == wp.location_type
            assert restored.icao_code == wp.icao_code


# ---------------------------------------------------------------------------
# 2. Route assembly and validation
# ---------------------------------------------------------------------------


@requires_kml
class TestRouteFromKml:
    def test_route_counts(self, route_data):
        waypoints, route = route_data
        assert len(waypoints) == 9
        assert len(route.waypoints) == 9
        assert len(route.legs) == 8

    def test_waypoint_roles(self, route_data):
        _, route = route_data
        roles = [ref.role for ref in route.waypoints]
        assert roles[0] == WaypointRole.DEPARTURE
        assert roles[-1] == WaypointRole.ARRIVAL
        assert all(r == WaypointRole.ENROUTE for r in roles[1:-1])

    def test_leg_sequences_consecutive(self, route_data):
        _, route = route_data
        for i, leg in enumerate(route.legs):
            assert leg.from_seq == i + 1
            assert leg.to_seq == i + 2

    def test_planned_altitudes(self, route_data):
        _, route = route_data
        alts = [leg.planned_altitude_ft for leg in route.legs]
        assert alts == PLANNED_ALTITUDES_FT

    def test_computed_fields_absent_in_firestore(self, route_data):
        _, route = route_data
        data = route.to_firestore()
        for leg_dict in data["legs"]:
            assert "distance_nm" not in leg_dict
            assert "true_heading_deg" not in leg_dict
            assert "ground_speed_kt" not in leg_dict
            assert "estimated_time_minutes" not in leg_dict

    def test_route_firestore_roundtrip(self, route_data):
        _, route = route_data
        data = route.to_firestore()
        restored = Route.from_firestore(data)
        assert restored.name == route.name
        assert len(restored.waypoints) == 9
        assert len(restored.legs) == 8
        for orig, rest in zip(route.legs, restored.legs):
            assert rest.from_seq == orig.from_seq
            assert rest.to_seq == orig.to_seq
            assert rest.planned_altitude_ft == orig.planned_altitude_ft


# ---------------------------------------------------------------------------
# 3. Airspace contracts with realistic simulated data
# ---------------------------------------------------------------------------


def _make_tma_paris():
    return AirspaceIntersection(
        identifier="TMA PARIS 1",
        airspace_type=AirspaceType.TMA,
        airspace_class="D",
        lower_limit_ft=1500,
        upper_limit_ft=4500,
        intersection_type=IntersectionType.CROSSES,
        color_html="#0066CC",
        services=[
            ServiceInfo(
                callsign="PARIS APPROCHE",
                service_type="APP",
                frequencies=[
                    FrequencyInfo(frequency_mhz="119.250", spacing="25"),
                ],
            )
        ],
    )


def _make_siv_paris():
    return AirspaceIntersection(
        identifier="SIV PARIS",
        airspace_type=AirspaceType.SIV,
        airspace_class=None,
        lower_limit_ft=0,
        upper_limit_ft=5000,
        intersection_type=IntersectionType.INSIDE,
        color_html="#90EE90",
        services=[
            ServiceInfo(
                callsign="PARIS INFO",
                service_type="SIV",
                frequencies=[
                    FrequencyInfo(frequency_mhz="120.850", spacing="25"),
                ],
            )
        ],
    )


def _make_analysis(route_id: str) -> RouteAirspaceAnalysis:
    """Build a realistic 8-leg airspace analysis for LFXU-LFFU."""
    tma = _make_tma_paris()
    siv = _make_siv_paris()
    names = EXPECTED_NAMES

    legs = []
    for i in range(8):
        route_as = []
        corridor_as = []

        # Legs 1-4 cross/are inside TMA PARIS
        if i < 4:
            route_as.append(tma)
        # SIV PARIS is present on all legs
        route_as.append(siv)

        legs.append(LegAirspaces(
            from_waypoint=names[i],
            to_waypoint=names[i + 1],
            from_seq=i + 1,
            to_seq=i + 2,
            planned_altitude_ft=PLANNED_ALTITUDES_FT[i],
            route_airspaces=route_as,
            corridor_airspaces=corridor_as,
        ))

    return RouteAirspaceAnalysis(
        route_id=route_id,
        legs=legs,
        analyzed_at=datetime.now(tz=timezone.utc).isoformat(),
    )


class TestAirspaceContracts:
    def test_airspace_intersection_creation(self):
        ai = _make_tma_paris()
        assert ai.identifier == "TMA PARIS 1"
        assert ai.airspace_class == "D"
        assert len(ai.services) == 1
        assert len(ai.services[0].frequencies) == 1

    def test_enum_values_serialized_as_strings(self):
        ai = _make_tma_paris()
        data = ai.to_firestore()
        assert data["airspace_type"] == "TMA"
        assert data["intersection_type"] == "crosses"

    def test_service_nested_roundtrip(self):
        ai = _make_tma_paris()
        data = ai.to_firestore()
        restored = AirspaceIntersection.from_firestore(data)
        assert restored.services[0].callsign == "PARIS APPROCHE"
        assert restored.services[0].frequencies[0].frequency_mhz == "119.250"

    def test_route_airspace_analysis_structure(self):
        analysis = _make_analysis("test-route-id")
        assert len(analysis.legs) == 8
        # First leg has TMA + SIV
        assert len(analysis.legs[0].route_airspaces) == 2
        # Last legs have SIV only
        assert len(analysis.legs[7].route_airspaces) == 1

    def test_analysis_firestore_roundtrip(self):
        analysis = _make_analysis("test-route-id")
        data = analysis.to_firestore()
        restored = RouteAirspaceAnalysis.from_firestore(data)
        assert len(restored.legs) == 8
        assert restored.legs[0].route_airspaces[0].identifier == "TMA PARIS 1"
        assert restored.legs[7].route_airspaces[0].identifier == "SIV PARIS"


# ---------------------------------------------------------------------------
# 4. End-to-end roundtrip: full flight preparation graph
# ---------------------------------------------------------------------------


def _make_aerodrome_lfxu() -> AerodromeInfo:
    return AerodromeInfo(
        icao="LFXU",
        name="LES MUREAUX",
        status=AerodromeStatus.CAP,
        latitude=48.998611,
        longitude=1.941667,
        elevation_ft=259,
        runways=[
            Runway(
                designator="08/26",
                length_m=730,
                width_m=50,
                is_main=True,
                surface="HERBE",
            ),
        ],
        services=[
            AerodromeService(
                service_type="AFIS",
                callsign="LES MUREAUX",
                frequencies=[
                    AerodromeFrequency(frequency_mhz=123.500, spacing="25"),
                ],
            ),
        ],
        airac_cycle="2603",
    )


def _make_aerodrome_lffu() -> AerodromeInfo:
    return AerodromeInfo(
        icao="LFFU",
        name="CHATEAUNEUF SUR CHER",
        status=AerodromeStatus.CAP,
        latitude=46.871111,
        longitude=2.376944,
        elevation_ft=548,
        runways=[
            Runway(designator="02/20", length_m=800, surface="HERBE"),
        ],
        airac_cycle="2603",
    )


def _make_weather(route_data, route_id: str) -> WeatherSimulation:
    """Build a realistic weather simulation for the LFXU-LFFU route."""
    waypoints_raw, _ = route_data
    now = datetime(2026, 2, 5, 9, 0, tzinfo=timezone.utc)

    wp_contexts = []
    for i, wp in enumerate(waypoints_raw):
        wp_contexts.append(WaypointContext(
            waypoint_name=wp.name,
            waypoint_index=i,
            latitude=wp.latitude,
            longitude=wp.longitude,
            icao=wp.icao_code,
            estimated_time_utc=datetime(2026, 2, 5, 9 + i // 3, i * 7 % 60, tzinfo=timezone.utc),
        ))

    model_points = []
    for i in range(9):
        model_points.append(ModelPoint(
            waypoint_index=i,
            forecast=ForecastData(
                temperature_2m=8.0 - i * 0.5,
                wind_speed_10m=12.0,
                wind_direction_10m=270,
                cloud_cover=30 + i * 5,
                visibility=8000,
                pressure_msl=1018.0,
                temperature_levels={1000: 10.0, 925: 5.0, 850: 1.0},
                wind_speed_levels={1000: 12.0, 925: 18.0, 850: 25.0},
                wind_direction_levels={1000: 270, 925: 280, 850: 290},
            ),
            vfr_index=VFRIndex(
                status=VFRStatus.GREEN,
                visibility_ok=True,
                ceiling_ok=True,
                wind_ok=True,
                details="VMC confortable",
            ),
        ))

    return WeatherSimulation(
        route_id=route_id,
        simulated_at=now,
        navigation_datetime=now,
        waypoints=wp_contexts,
        model_results=[
            ModelResult(
                model=ForecastModel.AROME_FRANCE,
                model_run_time=datetime(2026, 2, 5, 0, 0, tzinfo=timezone.utc),
                points=model_points,
            ),
        ],
    )


@requires_kml
class TestEndToEndRoundtrip:
    def test_full_flight_preparation_roundtrip(self, route_data):
        """Roundtrip every piece of the flight preparation data graph."""
        waypoints, route = route_data

        # Aerodromes
        lfxu = _make_aerodrome_lfxu()
        lffu = _make_aerodrome_lffu()

        # Airspace analysis
        analysis = _make_analysis(route.name)

        # Weather
        weather = _make_weather(route_data, route.name)

        # Roundtrip everything
        for label, obj, cls in [
            ("Route", route, Route),
            ("LFXU", lfxu, AerodromeInfo),
            ("LFFU", lffu, AerodromeInfo),
            ("Airspaces", analysis, RouteAirspaceAnalysis),
            ("Weather", weather, WeatherSimulation),
        ]:
            data = obj.to_firestore()
            restored = cls.from_firestore(data)

            # Core structural check
            data2 = restored.to_firestore()
            assert data == data2, f"{label}: double roundtrip produced different dicts"

    def test_aerodrome_nested_lists_survive(self):
        lfxu = _make_aerodrome_lfxu()
        data = lfxu.to_firestore()
        restored = AerodromeInfo.from_firestore(data)

        assert len(restored.runways) == 1
        assert restored.runways[0].designator == "08/26"
        assert restored.runways[0].surface == "HERBE"

        assert len(restored.services) == 1
        assert restored.services[0].service_type == "AFIS"
        assert len(restored.services[0].frequencies) == 1
        assert restored.services[0].frequencies[0].frequency_mhz == 123.500

    def test_weather_pressure_levels_roundtrip(self, route_data):
        weather = _make_weather(route_data, "test")
        data = weather.to_firestore()
        restored = WeatherSimulation.from_firestore(data)

        # Pressure level dict keys survive JSON roundtrip (str→int coercion)
        forecast = restored.model_results[0].points[0].forecast
        assert 1000 in forecast.temperature_levels
        assert 925 in forecast.wind_speed_levels
        assert forecast.temperature_levels[1000] == 10.0

    def test_service_result_wraps_route(self, route_data):
        _, route = route_data
        result = ServiceResult[Route].ok(route, duration_ms=42.5)
        assert result.success is True
        assert result.data is not None
        assert result.data.name == ROUTE_NAME
        assert result.duration_ms == 42.5

    def test_service_result_fail(self):
        result = ServiceResult.fail(
            "KML_PARSE_ERROR", "Invalid coordinate format", line=42
        )
        assert result.success is False
        assert result.error is not None
        assert result.error.code == "KML_PARSE_ERROR"
        assert result.error.details["line"] == 42

    def test_observation_enrichment(self):
        """Verify post-flight METAR observation attaches to WaypointContext."""
        ctx = WaypointContext(
            waypoint_name="LFXU - LES MUREAUX",
            waypoint_index=0,
            latitude=48.998611,
            longitude=1.941667,
            icao="LFXU",
            estimated_time_utc=datetime(2026, 2, 5, 9, 0, tzinfo=timezone.utc),
        )

        # Simulate post-flight enrichment
        obs = ObservationData(
            observation_time=datetime(2026, 2, 5, 9, 0, tzinfo=timezone.utc),
            icao="LFXU",
            wind_direction=270,
            wind_speed=8.0,
            temperature=9.0,
            dewpoint=3.0,
            visibility=9999,
            ceiling=3500,
            clouds=[
                CloudLayer(cover=CloudCover.FEW, base_ft=3500),
            ],
            flight_category="VFR",
            altimeter=1018.0,
            raw_metar="LFXU 050900Z 27008KT 9999 FEW035 09/03 Q1018",
        )

        enriched = ctx.model_copy(update={
            "actual_time_utc": datetime(2026, 2, 5, 9, 2, tzinfo=timezone.utc),
            "observation": obs,
        })

        data = enriched.to_firestore()
        restored = WaypointContext.from_firestore(data)

        assert restored.actual_time_utc is not None
        assert restored.observation is not None
        assert restored.observation.icao == "LFXU"
        assert restored.observation.raw_metar.startswith("LFXU")
        assert len(restored.observation.clouds) == 1
