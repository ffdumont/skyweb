"""Enumerations shared across all SkyWeb contracts."""

from enum import Enum


class LocationType(str, Enum):
    """Intrinsic nature of a geographic location."""
    AERODROME = "aerodrome"
    NAVAID = "navaid"
    VISUAL_REFERENCE = "visual_reference"
    GPS_POINT = "gps_point"


class WaypointRole(str, Enum):
    """Role of a waypoint within a specific route."""
    DEPARTURE = "departure"
    ARRIVAL = "arrival"
    ALTERNATE = "alternate"
    ENROUTE = "enroute"


class WaypointSource(str, Enum):
    SDVFR_IMPORT = "sdvfr_import"
    KML_IMPORT = "kml_import"
    MANUAL = "manual"
    GPX_TRACE = "gpx_trace"
    ROUTE_CORRECTION = "route_correction"  # Intermediate waypoints added during altitude correction


class DossierStatus(str, Enum):
    """Lifecycle of a navigation dossier (flight preparation folder)."""
    DRAFT = "draft"
    PREPARING = "preparing"
    READY = "ready"
    ARCHIVED = "archived"


class SectionId(str, Enum):
    """Sections of a navigation dossier."""
    ROUTE = "route"
    AERODROMES = "aerodromes"
    AIRSPACES = "airspaces"
    NOTAM = "notam"
    METEO = "meteo"
    NAVIGATION = "navigation"
    FUEL = "fuel"
    PERFORMANCE = "performance"
    DOCUMENTS = "documents"


class SectionCompletion(str, Enum):
    """Completion status of a dossier section."""
    EMPTY = "empty"
    PARTIAL = "partial"
    COMPLETE = "complete"
    ALERT = "alert"


class TrackSource(str, Enum):
    GPX_FILE = "gpx_file"
    FLIGHTAWARE = "flightaware"
    MANUAL = "manual"


class ForecastModel(str, Enum):
    AROME_FRANCE = "arome_france"
    AROME_HD = "arome_hd"
    ARPEGE_EUROPE = "arpege_europe"
    ARPEGE_WORLD = "arpege_world"


class VFRStatus(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class CloudCover(str, Enum):
    CLR = "CLR"
    FEW = "FEW"
    SCT = "SCT"
    BKN = "BKN"
    OVC = "OVC"


class AirspaceType(str, Enum):
    TMA = "TMA"
    CTR = "CTR"
    SIV = "SIV"
    D = "D"
    R = "R"
    P = "P"
    TSA = "TSA"
    CBA = "CBA"
    AWY = "AWY"
    FIR = "FIR"
    OTHER = "OTHER"


class IntersectionType(str, Enum):
    CROSSES = "crosses"
    INSIDE = "inside"
    ENTRY = "entry"
    EXIT = "exit"
    NEARBY = "nearby"


class AerodromeStatus(str, Enum):
    CAP = "CAP"
    RESTRICTED = "restricted"
    MILITARY = "military"
    CLOSED = "closed"
