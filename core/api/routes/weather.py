"""Weather simulation endpoints — fetch multi-model forecasts from Open-Meteo."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.api.deps import get_current_user
from core.services.weather_service import WeatherService

router = APIRouter(prefix="/weather", tags=["weather"])


class WaypointInput(BaseModel):
    """Waypoint for weather simulation."""

    name: str
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    icao: str | None = None


class SimulationRequest(BaseModel):
    """Request to run a weather simulation."""

    waypoints: list[WaypointInput] = Field(
        ..., min_length=1, description="List of waypoints"
    )
    departure_datetime: datetime = Field(
        ..., description="Departure time in UTC"
    )
    cruise_speed_kt: float = Field(
        default=100.0, ge=50, le=300, description="Cruise speed in knots"
    )
    cruise_altitude_ft: int = Field(
        default=3500, ge=0, le=20000, description="Cruise altitude in feet"
    )
    models: list[str] | None = Field(
        default=None, description="Models to query: arome, ecmwf, gfs, icon"
    )


@router.post("/simulations")
async def run_simulation(
    request: SimulationRequest,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Run a new weather simulation for a route.

    Fetches forecasts from multiple weather models (AROME, ECMWF, GFS, ICON)
    for each waypoint at the estimated passage time.
    """
    service = WeatherService()

    # Convert waypoints to dict format
    waypoints = [
        {"name": wp.name, "lat": wp.lat, "lon": wp.lon, "icao": wp.icao}
        for wp in request.waypoints
    ]

    # Get validated models list
    requested_models = request.models or ["arome", "ecmwf"]

    try:
        simulation = await service.run_simulation(
            waypoints=waypoints,
            departure_datetime=request.departure_datetime,
            cruise_speed_kt=request.cruise_speed_kt,
            cruise_altitude_ft=request.cruise_altitude_ft,
            models=requested_models,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather API error: {e}")

    # Convert to JSON-serializable format
    return _simulation_to_dict(simulation, requested_models)


@router.get("/models")
async def list_models() -> list[dict[str, Any]]:
    """List available weather models."""
    return WeatherService.get_available_models()


def _simulation_to_dict(simulation, requested_models: list[str]) -> dict[str, Any]:
    """Convert WeatherSimulation to JSON-serializable dict."""
    waypoints_data = [
        {
            "waypoint_name": wp.waypoint_name,
            "waypoint_index": wp.waypoint_index,
            "latitude": wp.latitude,
            "longitude": wp.longitude,
            "icao": wp.icao,
            "estimated_time_utc": wp.estimated_time_utc.isoformat(),
        }
        for wp in simulation.waypoints
    ]

    model_results_data = []
    # Zip model results with requested model IDs (they're in the same order)
    for model_id, mr in zip(requested_models, simulation.model_results):
        points_data = []
        for pt in mr.points:
            forecast = pt.forecast
            points_data.append({
                "waypoint_index": pt.waypoint_index,
                "forecast": {
                    "temperature_2m": forecast.temperature_2m,
                    "dewpoint_2m": forecast.dewpoint_2m,
                    "wind_speed_10m": forecast.wind_speed_10m,
                    "wind_direction_10m": forecast.wind_direction_10m,
                    "wind_gusts_10m": forecast.wind_gusts_10m,
                    "temperature_levels": forecast.temperature_levels,
                    "wind_speed_levels": forecast.wind_speed_levels,
                    "wind_direction_levels": forecast.wind_direction_levels,
                    "cloud_cover": forecast.cloud_cover,
                    "cloud_cover_low": forecast.cloud_cover_low,
                    "cloud_cover_mid": forecast.cloud_cover_mid,
                    "cloud_cover_high": forecast.cloud_cover_high,
                    "visibility": forecast.visibility,
                    "precipitation": forecast.precipitation,
                    "pressure_msl": forecast.pressure_msl,
                    "weather_code": forecast.weather_code,
                },
                "vfr_index": {
                    "status": pt.vfr_index.status.value if hasattr(pt.vfr_index.status, 'value') else pt.vfr_index.status,
                    "visibility_ok": pt.vfr_index.visibility_ok,
                    "ceiling_ok": pt.vfr_index.ceiling_ok,
                    "wind_ok": pt.vfr_index.wind_ok,
                    "details": pt.vfr_index.details,
                },
            })

        model_results_data.append({
            "model": model_id,  # Use the requested model ID, not the enum
            "model_run_time": mr.model_run_time.isoformat(),
            "points": points_data,
        })

    return {
        "simulation_id": f"sim_{int(simulation.simulated_at.timestamp())}",
        "simulated_at": simulation.simulated_at.isoformat(),
        "navigation_datetime": simulation.navigation_datetime.isoformat(),
        "waypoints": waypoints_data,
        "model_results": model_results_data,
    }
