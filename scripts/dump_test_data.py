"""Dump all contract test data as a single structured JSON file."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
    ModelPoint,
    ModelResult,
    ObservationData,
    RouteAirspaceAnalysis,
    Runway,
    ServiceInfo,
    VFRIndex,
    VFRStatus,
    WaypointContext,
    WeatherSimulation,
)

KML_PATH = Path(
    r"C:\Users\franc\dev\skytools\skypath\data\routes"
    r"\LFXU-LFFU-2025-09-25-14-51-39.kml"
)
ROUTE_NAME = "LFXU-LFFU"
PLANNED_ALTITUDES_FT = [1400, 1400, 1800, 1800, 2300, 3100, 3100, 2900]

EXPECTED_NAMES = [
    "LFXU - LES MUREAUX", "MOR1V", "PXSW", "HOLAN", "ARNOU",
    "OXWW", "LFFF/OE", "BEVRO", "LFFU - CHATEAUNEUF SUR CHER",
]

OUTPUT_PATH = Path(__file__).resolve().parent / "test_data_dump.json"


def main():
    if not KML_PATH.exists():
        print(f"KML introuvable : {KML_PATH}")
        sys.exit(1)

    # ── 1. Raw KML + Waypoints + Route ────────────────────────────────────
    raw = parse_kml_waypoints(KML_PATH)
    waypoints, route = build_route_from_kml(KML_PATH, ROUTE_NAME, PLANNED_ALTITUDES_FT)

    # ── 2. Aerodromes ─────────────────────────────────────────────────────
    lfxu = AerodromeInfo(
        icao="LFXU", name="LES MUREAUX", status=AerodromeStatus.CAP,
        latitude=48.998611, longitude=1.941667, elevation_ft=259,
        runways=[Runway(designator="08/26", length_m=730, width_m=50, is_main=True, surface="HERBE")],
        services=[AerodromeService(
            service_type="AFIS", callsign="LES MUREAUX",
            frequencies=[AerodromeFrequency(frequency_mhz=123.500, spacing="25")],
        )],
        airac_cycle="2603",
    )
    lffu = AerodromeInfo(
        icao="LFFU", name="CHATEAUNEUF SUR CHER", status=AerodromeStatus.CAP,
        latitude=46.871111, longitude=2.376944, elevation_ft=548,
        runways=[Runway(designator="02/20", length_m=800, surface="HERBE")],
        airac_cycle="2603",
    )

    # ── 3. Airspace analysis ──────────────────────────────────────────────
    tma = AirspaceIntersection(
        identifier="TMA PARIS 1", airspace_type=AirspaceType.TMA,
        airspace_class="D", lower_limit_ft=1500, upper_limit_ft=4500,
        intersection_type=IntersectionType.CROSSES, color_html="#0066CC",
        services=[ServiceInfo(
            callsign="PARIS APPROCHE", service_type="APP",
            frequencies=[FrequencyInfo(frequency_mhz="119.250", spacing="25")],
        )],
    )
    siv = AirspaceIntersection(
        identifier="SIV PARIS", airspace_type=AirspaceType.SIV,
        airspace_class=None, lower_limit_ft=0, upper_limit_ft=5000,
        intersection_type=IntersectionType.INSIDE, color_html="#90EE90",
        services=[ServiceInfo(
            callsign="PARIS INFO", service_type="SIV",
            frequencies=[FrequencyInfo(frequency_mhz="120.850", spacing="25")],
        )],
    )
    legs_air = []
    for i in range(8):
        route_as = []
        if i < 4:
            route_as.append(tma)
        route_as.append(siv)
        legs_air.append(LegAirspaces(
            from_waypoint=EXPECTED_NAMES[i], to_waypoint=EXPECTED_NAMES[i + 1],
            from_seq=i + 1, to_seq=i + 2,
            planned_altitude_ft=PLANNED_ALTITUDES_FT[i],
            route_airspaces=route_as, corridor_airspaces=[],
        ))

    analysis = RouteAirspaceAnalysis(
        route_id=route.name, legs=legs_air,
        analyzed_at=datetime(2026, 2, 5, 8, 0, tzinfo=timezone.utc).isoformat(),
    )

    # ── 4. Weather simulation ─────────────────────────────────────────────
    now = datetime(2026, 2, 5, 9, 0, tzinfo=timezone.utc)

    wp_contexts = []
    for i, wp in enumerate(waypoints):
        wp_contexts.append(WaypointContext(
            waypoint_name=wp.name, waypoint_index=i,
            latitude=wp.latitude, longitude=wp.longitude, icao=wp.icao_code,
            estimated_time_utc=datetime(2026, 2, 5, 9 + i // 3, i * 7 % 60, tzinfo=timezone.utc),
        ))

    model_points = []
    for i in range(9):
        model_points.append(ModelPoint(
            waypoint_index=i,
            forecast=ForecastData(
                temperature_2m=8.0 - i * 0.5, wind_speed_10m=12.0, wind_direction_10m=270,
                cloud_cover=30 + i * 5, visibility=8000, pressure_msl=1018.0,
                temperature_levels={1000: 10.0, 925: 5.0, 850: 1.0},
                wind_speed_levels={1000: 12.0, 925: 18.0, 850: 25.0},
                wind_direction_levels={1000: 270, 925: 280, 850: 290},
            ),
            vfr_index=VFRIndex(
                status=VFRStatus.GREEN, visibility_ok=True,
                ceiling_ok=True, wind_ok=True, details="VMC confortable",
            ),
        ))

    weather = WeatherSimulation(
        route_id=route.name, simulated_at=now, navigation_datetime=now,
        waypoints=wp_contexts,
        model_results=[ModelResult(
            model=ForecastModel.AROME_FRANCE,
            model_run_time=datetime(2026, 2, 5, 0, 0, tzinfo=timezone.utc),
            points=model_points,
        )],
    )

    # ── 5. Observation METAR ──────────────────────────────────────────────
    obs = ObservationData(
        observation_time=datetime(2026, 2, 5, 9, 0, tzinfo=timezone.utc),
        icao="LFXU", wind_direction=270, wind_speed=8.0,
        temperature=9.0, dewpoint=3.0, visibility=9999, ceiling=3500,
        clouds=[CloudLayer(cover=CloudCover.FEW, base_ft=3500)],
        flight_category="VFR", altimeter=1018.0,
        raw_metar="LFXU 050900Z 27008KT 9999 FEW035 09/03 Q1018",
    )

    # ── Assemble single JSON ──────────────────────────────────────────────
    output = {
        "kml_raw": raw,
        "waypoints": [wp.to_firestore() for wp in waypoints],
        "route": route.to_firestore(),
        "aerodromes": {
            "LFXU": lfxu.to_firestore(),
            "LFFU": lffu.to_firestore(),
        },
        "airspace_analysis": analysis.to_firestore(),
        "weather_simulation": weather.to_firestore(),
        "observation_metar": obs.to_firestore(),
    }

    OUTPUT_PATH.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Écrit : {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size:,} octets)")


if __name__ == "__main__":
    main()
