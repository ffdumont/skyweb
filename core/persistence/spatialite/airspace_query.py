"""Spatial queries on the SpatiaLite reference database → AirspaceIntersection contracts."""

from __future__ import annotations

import logging
import sqlite3

from core.contracts.airspace import (
    AirspaceIntersection,
    FrequencyInfo,
    LegAirspaces,
    ServiceInfo,
)
from core.contracts.enums import AirspaceType, IntersectionType
from core.persistence.spatialite.db_manager import SpatiaLiteManager

logger = logging.getLogger(__name__)

# Maps SIA TypeEspace values to SkyWeb enums.
_TYPE_MAP: dict[str, AirspaceType] = {
    "TMA": AirspaceType.TMA,
    "CTR": AirspaceType.CTR,
    "SIV": AirspaceType.SIV,
    "D": AirspaceType.D,
    "R": AirspaceType.R,
    "P": AirspaceType.P,
    "TSA": AirspaceType.TSA,
    "CBA": AirspaceType.CBA,
    "AWY": AirspaceType.AWY,
    "FIR": AirspaceType.FIR,
}


class AirspaceQueryService:
    """Segment-to-airspace intersection queries backed by SpatiaLite."""

    def __init__(self, manager: SpatiaLiteManager):
        self._manager = manager

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query_segment_airspaces(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        altitude_ft: int,
    ) -> list[AirspaceIntersection]:
        """Find airspaces intersected by a segment at a given altitude.

        Uses the materialized view ``airspace_spatial_indexed`` for
        pre-joined Espace→Partie→Volume with altitudes in ft AMSL.
        """
        conn = self._manager.get_connection()
        try:
            return self._query_segment(conn, lat1, lon1, lat2, lon2, altitude_ft)
        finally:
            conn.close()

    def analyze_route(
        self,
        waypoints: list[tuple[str, float, float]],
        legs: list[tuple[int, int, int]],
        corridor_nm: float = 2.5,
    ) -> list[LegAirspaces]:
        """Analyze all legs of a route.

        Args:
            waypoints: ``[(name, lat, lon), ...]`` in sequence order (1-based index = position).
            legs: ``[(from_seq, to_seq, altitude_ft), ...]``.
            corridor_nm: half-width of the corridor for corridor airspaces.

        Returns one :class:`LegAirspaces` per leg.
        """
        # Build waypoint lookup (1-based)
        wp_map: dict[int, tuple[str, float, float]] = {}
        for i, (name, lat, lon) in enumerate(waypoints, start=1):
            wp_map[i] = (name, lat, lon)

        conn = self._manager.get_connection()
        try:
            results: list[LegAirspaces] = []
            for from_seq, to_seq, alt_ft in legs:
                name1, lat1, lon1 = wp_map[from_seq]
                name2, lat2, lon2 = wp_map[to_seq]

                route_airspaces = self._query_segment(
                    conn, lat1, lon1, lat2, lon2, alt_ft
                )
                corridor_airspaces = self._query_corridor(
                    conn, lat1, lon1, lat2, lon2, alt_ft, corridor_nm
                )

                results.append(
                    LegAirspaces(
                        from_waypoint=name1,
                        to_waypoint=name2,
                        from_seq=from_seq,
                        to_seq=to_seq,
                        planned_altitude_ft=alt_ft,
                        route_airspaces=route_airspaces,
                        corridor_airspaces=corridor_airspaces,
                    )
                )
            return results
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _query_segment(
        self,
        conn: sqlite3.Connection,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        altitude_ft: int,
    ) -> list[AirspaceIntersection]:
        """Core spatial query: segment × airspace_spatial_indexed."""
        segment_wkt = f"LINESTRING({lon1} {lat1}, {lon2} {lat2})"

        rows = conn.execute(
            """
            SELECT
                a.espace_nom,
                a.espace_type,
                a.partie_nom,
                a.Classe,
                a.altitude_floor_ft_amsl,
                a.altitude_ceiling_ft_amsl,
                a.partie_pk,
                a.volume_pk
            FROM airspace_spatial_indexed a
            WHERE ST_Intersects(a.geometry, GeomFromText(?, 4326))
              AND a.altitude_floor_ft_amsl <= ?
              AND a.altitude_ceiling_ft_amsl >= ?
            """,
            (segment_wkt, altitude_ft, altitude_ft),
        ).fetchall()

        results: list[AirspaceIntersection] = []
        for row in rows:
            # Determine intersection type (crosses vs inside)
            intersection_type = self._classify_intersection(
                conn, lat1, lon1, lat2, lon2, row["partie_pk"]
            )

            services = self._get_services(conn, row["espace_pk"] if "espace_pk" in row.keys() else None)

            results.append(
                AirspaceIntersection(
                    identifier=row["espace_nom"],
                    airspace_type=_TYPE_MAP.get(row["espace_type"], AirspaceType.OTHER),
                    airspace_class=row["Classe"],
                    lower_limit_ft=row["altitude_floor_ft_amsl"],
                    upper_limit_ft=row["altitude_ceiling_ft_amsl"],
                    intersection_type=intersection_type,
                    partie_id=str(row["partie_pk"]),
                    volume_id=str(row["volume_pk"]),
                    services=services,
                )
            )
        return results

    def _classify_intersection(
        self,
        conn: sqlite3.Connection,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        partie_pk: int,
    ) -> IntersectionType:
        """Determine if the segment crosses or is inside the airspace."""
        row = conn.execute(
            """
            SELECT
                ST_Crosses(
                    MakeLine(MakePoint(?, ?), MakePoint(?, ?)),
                    a.geometry
                ) AS crosses,
                ST_Contains(a.geometry, MakePoint(?, ?)) AS start_inside,
                ST_Contains(a.geometry, MakePoint(?, ?)) AS end_inside
            FROM airspace_spatial_indexed a
            WHERE a.partie_pk = ?
            """,
            (lon1, lat1, lon2, lat2, lon1, lat1, lon2, lat2, partie_pk),
        ).fetchone()

        if row is None:
            return IntersectionType.CROSSES

        if row["start_inside"] and row["end_inside"]:
            return IntersectionType.INSIDE
        if row["crosses"]:
            return IntersectionType.CROSSES
        if row["start_inside"]:
            return IntersectionType.EXIT
        if row["end_inside"]:
            return IntersectionType.ENTRY
        return IntersectionType.CROSSES

    def _query_corridor(
        self,
        conn: sqlite3.Connection,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        altitude_ft: int,
        corridor_nm: float,
    ) -> list[AirspaceIntersection]:
        """Find airspaces in the corridor but NOT on the direct route."""
        # Convert NM to approximate degrees (1 NM ≈ 1/60°)
        buffer_deg = corridor_nm / 60.0

        rows = conn.execute(
            """
            SELECT
                a.espace_nom,
                a.espace_type,
                a.Classe,
                a.altitude_floor_ft_amsl,
                a.altitude_ceiling_ft_amsl,
                a.partie_pk,
                a.volume_pk
            FROM airspace_spatial_indexed a
            WHERE ST_Intersects(
                    a.geometry,
                    ST_Buffer(MakeLine(MakePoint(?, ?), MakePoint(?, ?)), ?)
                  )
              AND NOT ST_Intersects(
                    a.geometry,
                    MakeLine(MakePoint(?, ?), MakePoint(?, ?))
                  )
              AND a.altitude_floor_ft_amsl <= ?
              AND a.altitude_ceiling_ft_amsl >= ?
            """,
            (
                lon1, lat1, lon2, lat2, buffer_deg,
                lon1, lat1, lon2, lat2,
                altitude_ft, altitude_ft,
            ),
        ).fetchall()

        return [
            AirspaceIntersection(
                identifier=row["espace_nom"],
                airspace_type=_TYPE_MAP.get(row["espace_type"], AirspaceType.OTHER),
                airspace_class=row["Classe"],
                lower_limit_ft=row["altitude_floor_ft_amsl"],
                upper_limit_ft=row["altitude_ceiling_ft_amsl"],
                intersection_type=IntersectionType.NEARBY,
                partie_id=str(row["partie_pk"]),
                volume_id=str(row["volume_pk"]),
            )
            for row in rows
        ]

    def _get_services(
        self, conn: sqlite3.Connection, espace_pk: int | None
    ) -> list[ServiceInfo]:
        """Fetch ATC services and frequencies for an airspace."""
        if espace_pk is None:
            return []

        rows = conn.execute(
            """
            SELECT s.IndicLieu, s.IndicService,
                   f.Frequence, f.Espacement
            FROM Service s
            LEFT JOIN Frequence f ON f.Service_pk = s.pk
            WHERE s.Espace_pk = ?
            """,
            (espace_pk,),
        ).fetchall()

        services: dict[str, ServiceInfo] = {}
        for row in rows:
            key = f"{row['IndicLieu']}:{row['IndicService']}"
            if key not in services:
                services[key] = ServiceInfo(
                    callsign=row["IndicLieu"] or "",
                    service_type=row["IndicService"] or "",
                    frequencies=[],
                )
            if row["Frequence"]:
                services[key].frequencies.append(
                    FrequencyInfo(
                        frequency_mhz=str(row["Frequence"]),
                        spacing=row["Espacement"],
                    )
                )
        return list(services.values())
