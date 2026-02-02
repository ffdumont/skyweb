"""Tests for Open-Meteo client with mocked HTTP responses."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from core.contracts.enums import ForecastModel
from core.services.weather.openmeteo_client import OpenMeteoClient

# Sample meta.json response
META_RESPONSE = {
    "last_run_initialisation_time": 1718438400,  # 2024-06-15T12:00:00Z
    "last_run_modification_time": 1718445600,
    "last_run_availability_time": 1718449200,
}

# Sample hourly forecast response
FORECAST_RESPONSE = {
    "hourly": {
        "time": ["2025-06-15T08:00"],
        "temperature_2m": [18.5],
        "dewpoint_2m": [12.3],
        "temperature_1000hPa": [17.2],
        "temperature_925hPa": [12.1],
        "temperature_850hPa": [7.5],
        "temperature_700hPa": [-1.2],
        "wind_speed_10m": [8.5],
        "wind_direction_10m": [270],
        "wind_gusts_10m": [15.2],
        "wind_speed_1000hPa": [10.3],
        "wind_speed_925hPa": [18.7],
        "wind_speed_850hPa": [25.1],
        "wind_speed_700hPa": [32.0],
        "wind_direction_1000hPa": [265],
        "wind_direction_925hPa": [275],
        "wind_direction_850hPa": [280],
        "wind_direction_700hPa": [290],
        "cloud_cover": [45],
        "cloud_cover_low": [20],
        "cloud_cover_mid": [30],
        "cloud_cover_high": [10],
        "visibility": [15000],
        "precipitation": [0.0],
        "pressure_msl": [1015.3],
        "weather_code": [1],
    }
}


class TestOpenMeteoClient:
    async def test_get_model_run_time(self):
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=META_RESPONSE)
        )
        async with httpx.AsyncClient(transport=transport) as http:
            client = OpenMeteoClient(http_client=http)
            run_time = await client.get_model_run_time(ForecastModel.AROME_FRANCE)
            assert isinstance(run_time, datetime)
            assert run_time.tzinfo == timezone.utc

    async def test_get_forecast_parses_correctly(self):
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=FORECAST_RESPONSE)
        )
        async with httpx.AsyncClient(transport=transport) as http:
            client = OpenMeteoClient(http_client=http)
            target = datetime(2025, 6, 15, 8, 0, tzinfo=timezone.utc)
            forecast = await client.get_forecast(
                ForecastModel.AROME_FRANCE, 48.99, 1.88, target
            )
            assert forecast.temperature_2m == 18.5
            assert forecast.wind_speed_10m == 8.5
            assert forecast.wind_gusts_10m == 15.2
            assert forecast.visibility == 15000
            assert forecast.cloud_cover == 45
            assert 850 in forecast.temperature_levels
            assert forecast.temperature_levels[850] == 7.5
            assert 925 in forecast.wind_speed_levels
            assert forecast.wind_direction_levels[700] == 290

    async def test_get_forecast_url_params(self):
        """Verify correct URL parameters are sent."""
        captured_request = None

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = request
            return httpx.Response(200, json=FORECAST_RESPONSE)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http:
            client = OpenMeteoClient(http_client=http)
            target = datetime(2025, 6, 15, 8, 0, tzinfo=timezone.utc)
            await client.get_forecast(ForecastModel.ARPEGE_EUROPE, 48.0, 2.0, target)

        assert captured_request is not None
        url = str(captured_request.url)
        assert "meteofrance_arpege_europe" in url
        assert "wind_speed_unit=kn" in url
