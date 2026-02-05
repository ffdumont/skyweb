"""Airspace intersection models — route airspace analysis results."""

from pydantic import Field

from core.contracts.common import FirestoreModel
from core.contracts.enums import AirspaceType, IntersectionType


class FrequencyInfo(FirestoreModel):
    """Radio frequency for a service."""

    frequency_mhz: str = Field(..., description="e.g. '119.250'")
    spacing: str | None = Field(default=None, description="'25' or '8.33' kHz")
    hours_code: str | None = None
    hours_text: str | None = Field(default=None, description="e.g. 'H24', 'HJ'")


class ServiceInfo(FirestoreModel):
    """ATC/FIS service information."""

    callsign: str = Field(..., description="e.g. 'PARIS'")
    service_type: str = Field(..., description="e.g. 'TWR', 'APP', 'AFIS', 'SIV'")
    language: str | None = None
    frequencies: list[FrequencyInfo] = Field(default_factory=list)


class AirspaceIntersection(FirestoreModel):
    """An airspace intersected by a route leg."""

    identifier: str = Field(..., description="e.g. 'TMA PARIS 1'")
    airspace_type: AirspaceType
    airspace_class: str | None = Field(
        default=None, pattern=r"^[A-G]$", description="ICAO class A-G"
    )
    lower_limit_ft: int = Field(..., description="Lower limit in ft AMSL")
    upper_limit_ft: int = Field(..., description="Upper limit in ft AMSL")
    intersection_type: IntersectionType
    color_html: str | None = Field(default=None, description="HTML hex color")
    services: list[ServiceInfo] = Field(default_factory=list)

    # SkyPath alignment fields
    partie_id: str | None = None
    volume_id: str | None = None

    # GeoJSON geometry for map rendering (Polygon or MultiPolygon)
    geometry_geojson: dict | None = Field(
        default=None, description="GeoJSON geometry for 3D rendering"
    )


class LegAirspaces(FirestoreModel):
    """Airspace analysis result for a single route leg."""

    from_waypoint: str
    to_waypoint: str
    from_seq: int
    to_seq: int
    planned_altitude_ft: int
    route_airspaces: list[AirspaceIntersection] = Field(default_factory=list)
    corridor_airspaces: list[AirspaceIntersection] = Field(default_factory=list)


class RouteAirspaceAnalysis(FirestoreModel):
    """Complete airspace analysis for an entire route."""

    route_id: str
    legs: list[LegAirspaces]
    analyzed_at: str | None = None
