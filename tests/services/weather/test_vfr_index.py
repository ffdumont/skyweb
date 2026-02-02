"""Tests for VFR index calculation."""

from __future__ import annotations

from core.contracts.enums import VFRStatus
from core.contracts.weather import ForecastData
from core.services.weather.vfr_index import compute_vfr_index


class TestVFRIndex:
    def test_green_good_conditions(self):
        forecast = ForecastData(
            visibility=10000,
            cloud_cover=20,
            cloud_cover_low=10,
            wind_speed_10m=10.0,
            wind_gusts_10m=15.0,
        )
        result = compute_vfr_index(forecast, altitude_ft=2000)
        assert result.status == VFRStatus.GREEN
        assert result.visibility_ok
        assert result.ceiling_ok
        assert result.wind_ok

    def test_yellow_low_visibility(self):
        forecast = ForecastData(
            visibility=1200,  # Below 1500m threshold for below S
            cloud_cover=30,
            cloud_cover_low=20,
            wind_speed_10m=10.0,
        )
        result = compute_vfr_index(forecast, altitude_ft=2000)
        assert result.status == VFRStatus.YELLOW
        assert not result.visibility_ok

    def test_red_very_low_visibility(self):
        forecast = ForecastData(
            visibility=500,  # Below 800m → RED
            cloud_cover=80,
            cloud_cover_low=60,
            wind_speed_10m=10.0,
        )
        result = compute_vfr_index(forecast, altitude_ft=2000)
        assert result.status == VFRStatus.RED

    def test_yellow_high_wind(self):
        forecast = ForecastData(
            visibility=10000,
            cloud_cover=10,
            cloud_cover_low=5,
            wind_speed_10m=30.0,  # > 25 kt
            wind_gusts_10m=30.0,
        )
        result = compute_vfr_index(forecast, altitude_ft=2000)
        assert result.status == VFRStatus.YELLOW
        assert not result.wind_ok

    def test_red_extreme_gusts(self):
        forecast = ForecastData(
            visibility=10000,
            cloud_cover=10,
            cloud_cover_low=5,
            wind_speed_10m=30.0,
            wind_gusts_10m=50.0,  # > 45 kt → RED
        )
        result = compute_vfr_index(forecast, altitude_ft=2000)
        assert result.status == VFRStatus.RED

    def test_yellow_low_ceiling(self):
        forecast = ForecastData(
            visibility=10000,
            cloud_cover=95,  # Very overcast
            cloud_cover_low=80,  # BKN/OVC low clouds
            wind_speed_10m=10.0,
        )
        result = compute_vfr_index(forecast, altitude_ft=2000)
        assert result.status == VFRStatus.YELLOW
        assert not result.ceiling_ok

    def test_above_surface_s_needs_more_visibility(self):
        forecast = ForecastData(
            visibility=3000,  # OK below S (≥1500) but not above S (≥5000)
            cloud_cover=20,
            cloud_cover_low=10,
            wind_speed_10m=10.0,
        )
        below = compute_vfr_index(forecast, altitude_ft=2000)
        above = compute_vfr_index(forecast, altitude_ft=4000)
        assert below.visibility_ok
        assert not above.visibility_ok

    def test_missing_data_reports_unavailable(self):
        forecast = ForecastData()  # All None
        result = compute_vfr_index(forecast, altitude_ft=2000)
        assert "unavailable" in result.details.lower()

    def test_details_message_on_green(self):
        forecast = ForecastData(
            visibility=10000,
            cloud_cover=10,
            cloud_cover_low=5,
            wind_speed_10m=8.0,
        )
        result = compute_vfr_index(forecast, altitude_ft=2000)
        assert result.details == "VMC conditions"
