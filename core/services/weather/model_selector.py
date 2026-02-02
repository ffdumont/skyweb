"""Model selection logic based on forecast horizon."""

from __future__ import annotations

from datetime import datetime, timedelta

from core.contracts.enums import ForecastModel

# Open-Meteo model slug mapping
MODEL_SLUGS: dict[ForecastModel, str] = {
    ForecastModel.AROME_FRANCE: "meteofrance_arome_france_hd",
    ForecastModel.AROME_HD: "meteofrance_arome_france_hd",
    ForecastModel.ARPEGE_EUROPE: "meteofrance_arpege_europe",
    ForecastModel.ARPEGE_WORLD: "meteofrance_arpege_world025",
}

# Maximum forecast horizon per model
MODEL_HORIZONS: dict[ForecastModel, timedelta] = {
    ForecastModel.AROME_FRANCE: timedelta(hours=48),
    ForecastModel.AROME_HD: timedelta(hours=48),
    ForecastModel.ARPEGE_EUROPE: timedelta(hours=102),
    ForecastModel.ARPEGE_WORLD: timedelta(hours=96),
}


def select_models(
    simulated_at: datetime,
    navigation_datetime: datetime,
) -> list[ForecastModel]:
    """Select forecast models based on the time horizon.

    - ≤ 48h: AROME France + AROME HD + ARPEGE Europe (high-res + comparison)
    - 48h–96h: ARPEGE Europe + ARPEGE World
    - > 96h: ARPEGE Europe only (longest horizon at 102h)
    """
    horizon = navigation_datetime - simulated_at

    if horizon <= timedelta(hours=48):
        return [
            ForecastModel.AROME_FRANCE,
            ForecastModel.AROME_HD,
            ForecastModel.ARPEGE_EUROPE,
        ]
    elif horizon <= timedelta(hours=96):
        return [
            ForecastModel.ARPEGE_EUROPE,
            ForecastModel.ARPEGE_WORLD,
        ]
    else:
        return [ForecastModel.ARPEGE_EUROPE]
