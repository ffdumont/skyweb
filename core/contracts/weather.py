"""Weather models — multi-model simulation, forecasts, observations.

Stored at: ``/users/{user_id}/dossiers/{dossier_id}/simulations/{simulation_id}``
"""

from datetime import datetime

from pydantic import Field

from core.contracts.common import FirestoreModel
from core.contracts.enums import CloudCover, ForecastModel, VFRStatus


class CloudLayer(FirestoreModel):
    """A single cloud layer from METAR observation."""

    cover: CloudCover
    base_ft: int = Field(..., ge=0, description="Cloud base in ft AGL")


class ForecastData(FirestoreModel):
    """Forecast data for a single point/time from one model."""

    # Surface temperature
    temperature_2m: float | None = Field(default=None, description="deg C")
    dewpoint_2m: float | None = Field(default=None, description="deg C")

    # Temperature at pressure levels: {1000: 12.5, 925: 8.1, 850: 3.2}
    temperature_levels: dict[int, float] = Field(
        default_factory=dict, description="{hPa: deg_C}"
    )

    # Surface wind (kt)
    wind_speed_10m: float | None = Field(default=None, ge=0, description="kt")
    wind_direction_10m: int | None = Field(default=None, ge=0, le=360)
    wind_gusts_10m: float | None = Field(default=None, ge=0, description="kt")

    # Wind at pressure levels (kt)
    wind_speed_levels: dict[int, float] = Field(
        default_factory=dict, description="{hPa: kt}"
    )
    wind_direction_levels: dict[int, int] = Field(
        default_factory=dict, description="{hPa: degrees}"
    )

    # Cloud cover (%)
    cloud_cover: int | None = Field(default=None, ge=0, le=100)
    cloud_cover_low: int | None = Field(default=None, ge=0, le=100)
    cloud_cover_mid: int | None = Field(default=None, ge=0, le=100)
    cloud_cover_high: int | None = Field(default=None, ge=0, le=100)

    # Visibility & precipitation
    visibility: int | None = Field(default=None, ge=0, description="meters")
    precipitation: float | None = Field(default=None, ge=0, description="mm")
    pressure_msl: float | None = Field(default=None, description="hPa")

    weather_code: int | None = None


class ObservationData(FirestoreModel):
    """Real weather observation (METAR)."""

    observation_time: datetime
    icao: str = Field(..., pattern=r"^[A-Z]{4}$")

    wind_direction: int | None = Field(default=None, ge=0, le=360)
    wind_speed: float | None = Field(default=None, ge=0, description="kt")
    wind_gust: float | None = Field(default=None, ge=0, description="kt")

    temperature: float | None = Field(default=None, description="deg C")
    dewpoint: float | None = Field(default=None, description="deg C")

    visibility: int | None = Field(default=None, ge=0, description="meters")
    ceiling: int | None = Field(default=None, ge=0, description="ft AGL, lowest BKN/OVC")
    clouds: list[CloudLayer] = Field(default_factory=list)
    flight_category: str | None = Field(
        default=None, pattern=r"^(VFR|MVFR|IFR|LIFR)$"
    )

    altimeter: float | None = Field(default=None, description="hPa (QNH)")
    raw_metar: str | None = None


class VFRIndex(FirestoreModel):
    """VFR safety assessment for a single point."""

    status: VFRStatus
    visibility_ok: bool
    ceiling_ok: bool
    wind_ok: bool
    details: str = Field(default="", description="Human-readable explanation")


class WaypointContext(FirestoreModel):
    """A route waypoint within a weather simulation — shared across models."""

    waypoint_name: str
    waypoint_index: int = Field(..., ge=0)
    latitude: float
    longitude: float
    icao: str | None = None

    estimated_time_utc: datetime
    actual_time_utc: datetime | None = None
    observation: ObservationData | None = None


class ModelPoint(FirestoreModel):
    """Forecast + VFR index for one waypoint, from one model."""

    waypoint_index: int = Field(..., ge=0)
    forecast: ForecastData
    vfr_index: VFRIndex


class ModelResult(FirestoreModel):
    """Complete forecast result from one model across all waypoints."""

    model: ForecastModel
    model_run_time: datetime
    points: list[ModelPoint]


class WeatherSimulation(FirestoreModel):
    """Multi-model weather simulation on a route.

    Now stored under dossier: ``/users/{uid}/dossiers/{did}/simulations/{sid}``
    """

    id: str | None = None
    route_id: str
    dossier_id: str | None = None
    simulated_at: datetime
    navigation_datetime: datetime

    waypoints: list[WaypointContext]
    model_results: list[ModelResult]
