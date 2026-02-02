"""Open-Meteo API client for forecast data."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from core.contracts.enums import ForecastModel
from core.contracts.weather import ForecastData
from core.services.weather.model_selector import MODEL_SLUGS

BASE_URL = "https://api.open-meteo.com"

# Hourly variables to request
_HOURLY_VARS = [
    "temperature_2m",
    "dewpoint_2m",
    "temperature_1000hPa",
    "temperature_925hPa",
    "temperature_850hPa",
    "temperature_700hPa",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "wind_speed_1000hPa",
    "wind_speed_925hPa",
    "wind_speed_850hPa",
    "wind_speed_700hPa",
    "wind_direction_1000hPa",
    "wind_direction_925hPa",
    "wind_direction_850hPa",
    "wind_direction_700hPa",
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "visibility",
    "precipitation",
    "pressure_msl",
    "weather_code",
]


class OpenMeteoClient:
    """Async HTTP client for the Open-Meteo Météo-France API."""

    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self._client = http_client or httpx.AsyncClient(timeout=30.0)

    async def get_model_run_time(self, model: ForecastModel) -> datetime:
        """Fetch the last model initialisation time from the meta endpoint."""
        slug = MODEL_SLUGS[model]
        url = f"{BASE_URL}/data/{slug}/static/meta.json"
        resp = await self._client.get(url)
        resp.raise_for_status()
        data = resp.json()
        ts = data["last_run_initialisation_time"]
        return datetime.fromtimestamp(ts, tz=timezone.utc)

    async def get_forecast(
        self,
        model: ForecastModel,
        latitude: float,
        longitude: float,
        target_time: datetime,
    ) -> ForecastData:
        """Fetch hourly forecast data for a single point/time."""
        slug = MODEL_SLUGS[model]
        hour_str = target_time.strftime("%Y-%m-%dT%H:00")
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(_HOURLY_VARS),
            "models": slug,
            "start_hour": hour_str,
            "end_hour": hour_str,
            "wind_speed_unit": "kn",
        }
        resp = await self._client.get(f"{BASE_URL}/v1/meteofrance", params=params)
        resp.raise_for_status()
        return _parse_forecast(resp.json())


def _parse_forecast(data: dict) -> ForecastData:
    """Parse Open-Meteo hourly response into ForecastData."""
    hourly = data.get("hourly", {})

    def _first(key: str):
        values = hourly.get(key, [])
        return values[0] if values else None

    def _first_int(key: str):
        v = _first(key)
        return int(v) if v is not None else None

    # Pressure level temperatures
    temp_levels: dict[int, float] = {}
    for hpa in [1000, 925, 850, 700]:
        v = _first(f"temperature_{hpa}hPa")
        if v is not None:
            temp_levels[hpa] = v

    # Pressure level winds
    speed_levels: dict[int, float] = {}
    dir_levels: dict[int, int] = {}
    for hpa in [1000, 925, 850, 700]:
        ws = _first(f"wind_speed_{hpa}hPa")
        wd = _first(f"wind_direction_{hpa}hPa")
        if ws is not None:
            speed_levels[hpa] = ws
        if wd is not None:
            dir_levels[hpa] = int(wd)

    return ForecastData(
        temperature_2m=_first("temperature_2m"),
        dewpoint_2m=_first("dewpoint_2m"),
        temperature_levels=temp_levels,
        wind_speed_10m=_first("wind_speed_10m"),
        wind_direction_10m=_first_int("wind_direction_10m"),
        wind_gusts_10m=_first("wind_gusts_10m"),
        wind_speed_levels=speed_levels,
        wind_direction_levels=dir_levels,
        cloud_cover=_first_int("cloud_cover"),
        cloud_cover_low=_first_int("cloud_cover_low"),
        cloud_cover_mid=_first_int("cloud_cover_mid"),
        cloud_cover_high=_first_int("cloud_cover_high"),
        visibility=_first_int("visibility"),
        precipitation=_first("precipitation"),
        pressure_msl=_first("pressure_msl"),
        weather_code=_first_int("weather_code"),
    )
