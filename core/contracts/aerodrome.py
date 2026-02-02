"""Aerodrome models — read model from XML SIA reference data."""

from pydantic import Field

from core.contracts.common import FirestoreModel
from core.contracts.enums import AerodromeStatus


class AerodromeFrequency(FirestoreModel):
    """A radio frequency at an aerodrome."""

    frequency_mhz: float = Field(..., gt=100.0, lt=200.0)
    spacing: str | None = None
    hours_code: str | None = None
    hours_text: str | None = None
    sector: str | None = None
    remarks: str | None = None


class AerodromeService(FirestoreModel):
    """An ATC/FIS service at an aerodrome."""

    service_type: str = Field(..., description="TWR, AFIS, APP, SIV, etc.")
    callsign: str | None = None
    indicator: str | None = None
    language: str | None = None
    hours_code: str | None = None
    hours_text: str | None = None
    remarks: str | None = None
    frequencies: list[AerodromeFrequency] = Field(default_factory=list)


class Runway(FirestoreModel):
    """Runway information from XML SIA."""

    designator: str = Field(..., description="e.g. '08/26'")
    length_m: int | None = None
    width_m: int | None = None
    is_main: bool = False
    surface: str | None = Field(default=None, description="e.g. 'DUR', 'HERBE'")
    pcn: str | None = None
    orientation_geo: float | None = None

    lat_thr1: float | None = None
    lon_thr1: float | None = None
    alt_ft_thr1: int | None = None
    lda1_m: int | None = Field(default=None, description="Landing Distance Available (m)")

    lat_thr2: float | None = None
    lon_thr2: float | None = None
    alt_ft_thr2: int | None = None
    lda2_m: int | None = None


class AerodromeInfo(FirestoreModel):
    """Aerodrome information consolidated from XML SIA.

    Read model — populated from the SIA ETL pipeline, not stored per-user.
    """

    icao: str = Field(..., pattern=r"^[A-Z]{4}$")
    name: str
    status: AerodromeStatus | None = None
    vfr: bool = True
    private: bool = False

    latitude: float
    longitude: float
    elevation_ft: int | None = None
    mag_variation: float | None = None
    ref_temperature: float | None = Field(default=None, description="deg C")

    ats_hours: str | None = None
    fuel_available: str | None = None
    fuel_remarks: str | None = None
    met_centre: str | None = None
    met_briefing: str | None = None

    sslia_category: int | None = None

    management: str | None = None
    phone: str | None = None
    remarks: str | None = None

    runways: list[Runway] = Field(default_factory=list)
    services: list[AerodromeService] = Field(default_factory=list)

    airac_cycle: str | None = None
