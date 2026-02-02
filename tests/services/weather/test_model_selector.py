"""Tests for model selection logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.contracts.enums import ForecastModel
from core.services.weather.model_selector import select_models


class TestModelSelector:
    def test_short_horizon_returns_three_models(self):
        now = datetime(2025, 6, 15, 8, 0, tzinfo=timezone.utc)
        nav = now + timedelta(hours=12)
        models = select_models(now, nav)
        assert ForecastModel.AROME_FRANCE in models
        assert ForecastModel.AROME_HD in models
        assert ForecastModel.ARPEGE_EUROPE in models
        assert len(models) == 3

    def test_48h_boundary_still_short(self):
        now = datetime(2025, 6, 15, 8, 0, tzinfo=timezone.utc)
        nav = now + timedelta(hours=48)
        models = select_models(now, nav)
        assert len(models) == 3

    def test_medium_horizon_returns_two_models(self):
        now = datetime(2025, 6, 15, 8, 0, tzinfo=timezone.utc)
        nav = now + timedelta(hours=72)
        models = select_models(now, nav)
        assert models == [ForecastModel.ARPEGE_EUROPE, ForecastModel.ARPEGE_WORLD]

    def test_96h_boundary_still_medium(self):
        now = datetime(2025, 6, 15, 8, 0, tzinfo=timezone.utc)
        nav = now + timedelta(hours=96)
        models = select_models(now, nav)
        assert len(models) == 2

    def test_long_horizon_returns_one_model(self):
        now = datetime(2025, 6, 15, 8, 0, tzinfo=timezone.utc)
        nav = now + timedelta(hours=100)
        models = select_models(now, nav)
        assert models == [ForecastModel.ARPEGE_EUROPE]
