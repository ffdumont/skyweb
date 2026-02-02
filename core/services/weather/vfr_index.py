"""VFR condition assessment from forecast data."""

from __future__ import annotations

from core.contracts.enums import VFRStatus
from core.contracts.weather import ForecastData, VFRIndex

# Surface S threshold (approx 3000 ft AMSL / 1000 ft AGL in France)
_SURFACE_S_FT = 3000

# Thresholds
_VIS_BELOW_S = 1500  # meters
_VIS_ABOVE_S = 5000  # meters
_VIS_RED = 800  # meters — IFR/danger
_WIND_SUSTAINED_MAX = 25  # kt
_WIND_GUST_MAX = 35  # kt
_CEILING_MIN_FT = 1500  # ft AGL — below BKN/OVC


def compute_vfr_index(forecast: ForecastData, altitude_ft: int) -> VFRIndex:
    """Evaluate VFR conditions from forecast data.

    Below Surface S (3000 ft AMSL):
        - Visibility >= 1500 m
        - Clear of clouds
    Above Surface S:
        - Visibility >= 5000 m
    """
    details_parts: list[str] = []

    # --- Visibility ---
    visibility_ok = True
    if forecast.visibility is not None:
        threshold = _VIS_BELOW_S if altitude_ft < _SURFACE_S_FT else _VIS_ABOVE_S
        visibility_ok = forecast.visibility >= threshold
        if not visibility_ok:
            details_parts.append(
                f"Visibility {forecast.visibility}m < {threshold}m"
            )
    else:
        details_parts.append("Visibility data unavailable")

    # --- Ceiling (using cloud_cover_low as proxy for low ceiling) ---
    ceiling_ok = True
    if forecast.cloud_cover_low is not None and forecast.cloud_cover_low >= 75:
        # BKN/OVC low clouds — check if altitude is close to cloud base
        ceiling_ok = False
        details_parts.append(f"Low cloud cover {forecast.cloud_cover_low}%")
    if forecast.cloud_cover is not None and forecast.cloud_cover >= 90:
        ceiling_ok = False
        details_parts.append(f"Total cloud cover {forecast.cloud_cover}%")

    # --- Wind ---
    wind_ok = True
    if forecast.wind_speed_10m is not None and forecast.wind_speed_10m > _WIND_SUSTAINED_MAX:
        wind_ok = False
        details_parts.append(f"Wind {forecast.wind_speed_10m}kt > {_WIND_SUSTAINED_MAX}kt")
    if forecast.wind_gusts_10m is not None and forecast.wind_gusts_10m > _WIND_GUST_MAX:
        wind_ok = False
        details_parts.append(f"Gusts {forecast.wind_gusts_10m}kt > {_WIND_GUST_MAX}kt")

    # --- Status ---
    if visibility_ok and ceiling_ok and wind_ok:
        status = VFRStatus.GREEN
    elif (
        forecast.visibility is not None
        and forecast.visibility < _VIS_RED
    ):
        status = VFRStatus.RED
    elif not wind_ok and forecast.wind_gusts_10m is not None and forecast.wind_gusts_10m > 45:
        status = VFRStatus.RED
    else:
        status = VFRStatus.YELLOW

    return VFRIndex(
        status=status,
        visibility_ok=visibility_ok,
        ceiling_ok=ceiling_ok,
        wind_ok=wind_ok,
        details="; ".join(details_parts) if details_parts else "VMC conditions",
    )
