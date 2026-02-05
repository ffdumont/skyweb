"""Weather service — fetch forecasts from Open-Meteo API.

Based on SkyVerify implementation patterns:
- meteofrance_seamless for AROME (Météo-France, 48h horizon)
- ecmwf_ifs for ECMWF (96h horizon, includes visibility)
- gfs_seamless for GFS (NOAA)
- icon_seamless for ICON (DWD)

CRITICAL: Wind speeds ALWAYS in knots via wind_speed_unit=kn
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from core.contracts.enums import ForecastModel, VFRStatus
from core.contracts.weather import (
    ForecastData,
    ModelPoint,
    ModelResult,
    VFRIndex,
    WaypointContext,
    WeatherSimulation,
)

logger = logging.getLogger(__name__)

# Open-Meteo base URL
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Weather variables to fetch
FORECAST_VARIABLES = [
    "temperature_2m",
    "dewpoint_2m",
    "relative_humidity_2m",
    "pressure_msl",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "precipitation",
    "weather_code",
]

# Model configurations matching SkyVerify patterns
MODELS = {
    "arome": {
        "api_model": "meteofrance_seamless",
        "name": "AROME",
        "provider": "Météo-France",
        "horizon_hours": 48,
        "color": "#0066cc",
        "enum": ForecastModel.AROME_FRANCE,
    },
    "ecmwf": {
        "api_model": "ecmwf_ifs",
        "name": "ECMWF IFS",
        "provider": "ECMWF",
        "horizon_hours": 96,
        "color": "#009966",
        "extra_vars": ["visibility"],  # Not available in AROME
        "enum": ForecastModel.ARPEGE_EUROPE,
    },
    "gfs": {
        "api_model": "gfs_seamless",
        "name": "GFS",
        "provider": "NOAA",
        "horizon_hours": 384,
        "color": "#cc6600",
        "enum": ForecastModel.ARPEGE_WORLD,
    },
    "icon": {
        "api_model": "icon_seamless",
        "name": "ICON",
        "provider": "DWD",
        "horizon_hours": 180,
        "color": "#9933cc",
        "enum": ForecastModel.ARPEGE_EUROPE,
    },
}


class WeatherService:
    """Fetch multi-model weather forecasts from Open-Meteo."""

    def __init__(self, timeout: float = 30.0):
        self._timeout = timeout

    async def run_simulation(
        self,
        waypoints: list[dict[str, Any]],
        departure_datetime: datetime,
        cruise_speed_kt: float = 100.0,
        cruise_altitude_ft: int = 3500,
        models: list[str] | None = None,
    ) -> WeatherSimulation:
        """Run a weather simulation for a route.

        Args:
            waypoints: List of waypoints with {name, lat, lon}
            departure_datetime: Departure time (UTC)
            cruise_speed_kt: Cruise speed in knots
            cruise_altitude_ft: Cruise altitude in feet
            models: List of models to query (default: arome, ecmwf)

        Returns:
            WeatherSimulation with forecast data from all models
        """
        if models is None:
            models = ["arome", "ecmwf"]

        # Validate models
        models = [m for m in models if m in MODELS]
        if not models:
            models = ["arome", "ecmwf"]

        # Calculate passage times for each waypoint (with per-waypoint altitude)
        waypoint_contexts = self._calculate_passage_times(
            waypoints, departure_datetime, cruise_speed_kt, cruise_altitude_ft
        )

        # Query each model in parallel (altitude now in waypoint contexts)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            tasks = [
                self._query_model(client, model_id, waypoint_contexts)
                for model_id in models
            ]
            model_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out errors
        valid_results: list[ModelResult] = []
        for model_id, result in zip(models, model_results):
            if isinstance(result, Exception):
                logger.error("Failed to query model %s: %s", model_id, result)
            else:
                valid_results.append(result)

        return WeatherSimulation(
            route_id="",  # Set by caller
            simulated_at=datetime.utcnow(),
            navigation_datetime=departure_datetime,
            waypoints=waypoint_contexts,
            model_results=valid_results,
        )

    def _calculate_passage_times(
        self,
        waypoints: list[dict[str, Any]],
        departure_datetime: datetime,
        cruise_speed_kt: float,
        default_altitude_ft: int,
    ) -> list[WaypointContext]:
        """Calculate estimated passage times for each waypoint."""
        from math import atan2, cos, radians, sin, sqrt

        def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            """Calculate distance in NM between two points."""
            R = 3440.065  # Earth radius in NM
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            return 2 * R * atan2(sqrt(a), sqrt(1 - a))

        contexts: list[WaypointContext] = []
        cumulative_time = timedelta()

        for i, wp in enumerate(waypoints):
            if i > 0:
                prev = waypoints[i - 1]
                dist_nm = haversine(prev["lat"], prev["lon"], wp["lat"], wp["lon"])
                time_hours = dist_nm / cruise_speed_kt
                cumulative_time += timedelta(hours=time_hours)

            passage_time = departure_datetime + cumulative_time
            # Use per-waypoint altitude if provided, otherwise default
            altitude_ft = wp.get("altitude_ft") or default_altitude_ft

            contexts.append(
                WaypointContext(
                    waypoint_name=wp["name"],
                    waypoint_index=i,
                    latitude=wp["lat"],
                    longitude=wp["lon"],
                    icao=wp.get("icao"),
                    altitude_ft=altitude_ft,
                    estimated_time_utc=passage_time,
                )
            )

        return contexts

    async def _query_model(
        self,
        client: httpx.AsyncClient,
        model_id: str,
        waypoints: list[WaypointContext],
    ) -> ModelResult:
        """Query Open-Meteo for a single model across all waypoints.

        Each waypoint is queried with its specific altitude's pressure level.
        """
        model_config = MODELS[model_id]

        # Build base variables list
        base_variables = FORECAST_VARIABLES.copy()
        if "extra_vars" in model_config:
            base_variables.extend(model_config["extra_vars"])

        # Query each waypoint separately with its specific altitude
        points: list[ModelPoint] = []
        for wp in waypoints:
            # Determine pressure level for this waypoint's altitude
            pressure_level = self._altitude_to_pressure(wp.altitude_ft)

            # Add pressure level variables for this waypoint
            variables = base_variables.copy()
            variables.extend([
                f"temperature_{pressure_level}hPa",
                f"wind_speed_{pressure_level}hPa",
                f"wind_direction_{pressure_level}hPa",
            ])

            params = {
                "latitude": wp.latitude,
                "longitude": wp.longitude,
                "hourly": ",".join(variables),
                "models": model_config["api_model"],
                "wind_speed_unit": "kn",  # CRITICAL: Force wind speeds in knots
                "forecast_hours": model_config["horizon_hours"],
            }

            try:
                response = await client.get(OPEN_METEO_URL, params=params)
                response.raise_for_status()
                data = response.json()

                hourly = data.get("hourly", {})
                point = self._parse_waypoint_forecast_single(
                    wp, hourly, pressure_level
                )
                points.append(point)
            except httpx.HTTPError as e:
                logger.warning("Failed to fetch forecast for %s: %s", wp.waypoint_name, e)
                # Create empty point on error
                points.append(ModelPoint(
                    waypoint_index=wp.waypoint_index,
                    forecast=ForecastData(),
                    vfr_index=VFRIndex(
                        status=VFRStatus.YELLOW,
                        visibility_ok=True,
                        ceiling_ok=True,
                        wind_ok=True,
                        details="Données non disponibles",
                    ),
                ))

        return ModelResult(
            model=model_config["enum"],
            model_run_time=datetime.utcnow(),
            points=points,
        )

    def _parse_waypoint_forecast_single(
        self,
        wp: WaypointContext,
        hourly: dict[str, Any],
        pressure_level: int,
        location_idx: int | None = None,
    ) -> ModelPoint:
        """Parse forecast data for a single waypoint from hourly arrays."""
        # Find closest time index
        times = hourly.get("time", [])
        target_time = wp.estimated_time_utc.strftime("%Y-%m-%dT%H:00")

        try:
            time_idx = times.index(target_time)
        except ValueError:
            # Find closest time
            time_idx = 0
            for i, t in enumerate(times):
                if t >= target_time:
                    time_idx = i
                    break

        def get_value(key: str) -> Any:
            vals = hourly.get(key, [])
            if isinstance(vals, list) and len(vals) > time_idx:
                return vals[time_idx]
            return None

        # Build forecast data
        forecast = ForecastData(
            temperature_2m=get_value("temperature_2m"),
            dewpoint_2m=get_value("dewpoint_2m"),
            wind_speed_10m=get_value("wind_speed_10m"),
            wind_direction_10m=get_value("wind_direction_10m"),
            wind_gusts_10m=get_value("wind_gusts_10m"),
            cloud_cover=get_value("cloud_cover"),
            cloud_cover_low=get_value("cloud_cover_low"),
            cloud_cover_mid=get_value("cloud_cover_mid"),
            cloud_cover_high=get_value("cloud_cover_high"),
            visibility=get_value("visibility"),
            precipitation=get_value("precipitation"),
            pressure_msl=get_value("pressure_msl"),
            weather_code=get_value("weather_code"),
            temperature_levels={
                pressure_level: get_value(f"temperature_{pressure_level}hPa")
            } if get_value(f"temperature_{pressure_level}hPa") is not None else {},
            wind_speed_levels={
                pressure_level: get_value(f"wind_speed_{pressure_level}hPa")
            } if get_value(f"wind_speed_{pressure_level}hPa") is not None else {},
            wind_direction_levels={
                pressure_level: int(get_value(f"wind_direction_{pressure_level}hPa") or 0)
            } if get_value(f"wind_direction_{pressure_level}hPa") is not None else {},
        )

        # Calculate VFR index
        vfr_index = self._calculate_vfr_index(forecast)

        return ModelPoint(
            waypoint_index=wp.waypoint_index,
            forecast=forecast,
            vfr_index=vfr_index,
        )

    def _calculate_vfr_index(self, forecast: ForecastData) -> VFRIndex:
        """Calculate VFR safety index from forecast data."""
        visibility_ok = True
        ceiling_ok = True
        wind_ok = True
        issues: list[str] = []

        # Visibility check (VFR minimum: 5km)
        if forecast.visibility is not None:
            vis_km = forecast.visibility / 1000 if forecast.visibility > 100 else forecast.visibility
            visibility_ok = vis_km >= 5
            if not visibility_ok:
                issues.append(f"Visibilité {vis_km:.1f}km < 5km")

        # Cloud/ceiling check (estimate from cloud cover)
        low_clouds = forecast.cloud_cover_low or 0
        if low_clouds > 75:  # Rough BKN/OVC equivalent
            ceiling_ok = False
            issues.append(f"Nuages bas {low_clouds}%")

        # Wind check (crosswind/gusts)
        wind_speed = forecast.wind_speed_10m or 0
        wind_gusts = forecast.wind_gusts_10m or 0
        if wind_gusts > 25:
            wind_ok = False
            issues.append(f"Rafales {wind_gusts:.0f}kt")
        elif wind_speed > 20:
            wind_ok = False
            issues.append(f"Vent {wind_speed:.0f}kt")

        # Determine status
        if visibility_ok and ceiling_ok and wind_ok:
            status = VFRStatus.GREEN
            details = "Conditions VFR favorables"
        elif not visibility_ok or not ceiling_ok:
            status = VFRStatus.RED
            details = "; ".join(issues)
        else:
            status = VFRStatus.YELLOW
            details = "; ".join(issues)

        return VFRIndex(
            status=status,
            visibility_ok=visibility_ok,
            ceiling_ok=ceiling_ok,
            wind_ok=wind_ok,
            details=details,
        )

    def _altitude_to_pressure(self, altitude_ft: int) -> int:
        """Convert altitude in feet to nearest available pressure level.

        Open-Meteo supports: 1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, ...
        """
        # Standard atmosphere approximation
        pressure_map = [
            (0, 1000),
            (1500, 950),
            (3000, 925),
            (4500, 900),
            (6000, 850),
            (8000, 800),
            (10000, 700),
            (14000, 600),
            (18000, 500),
        ]

        for alt, pressure in reversed(pressure_map):
            if altitude_ft >= alt:
                return pressure
        return 1000

    @staticmethod
    def get_available_models() -> list[dict[str, Any]]:
        """Return list of available weather models."""
        return [
            {
                "id": model_id,
                "name": config["name"],
                "provider": config["provider"],
                "horizon_hours": config["horizon_hours"],
                "color": config["color"],
            }
            for model_id, config in MODELS.items()
        ]
