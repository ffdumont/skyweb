"""Aerodrome queries on the SpatiaLite reference database → AerodromeInfo contracts."""

from __future__ import annotations

import sqlite3

from core.contracts.aerodrome import (
    AerodromeFrequency,
    AerodromeInfo,
    AerodromeService,
    Runway,
)
from core.contracts.enums import AerodromeStatus
from core.persistence.spatialite.db_manager import SpatiaLiteManager


class AerodromeQueryService:
    """Read-only aerodrome lookups backed by SpatiaLite.

    Supports both the new schema (aerodrome/aerodrome_runway/aerodrome_service tables)
    and the legacy schema (Ad/Rwy/Service tables) for backward compatibility.

    Note on ICAO codes:
        The new schema stores ICAO codes WITHOUT the country prefix (e.g., "XU" for LFXU).
        This service accepts full ICAO codes and handles the prefix stripping internally.
    """

    def __init__(self, manager: SpatiaLiteManager):
        self._manager = manager
        self._use_new_schema: bool | None = None  # Detect on first query

    # ------------------------------------------------------------------
    # Schema detection
    # ------------------------------------------------------------------

    def _detect_schema(self, conn: sqlite3.Connection) -> bool:
        """Check if new aerodrome tables exist. Returns True for new schema."""
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='aerodrome'"
        )
        return cursor.fetchone() is not None

    @staticmethod
    def _strip_icao_prefix(icao: str) -> str:
        """Strip country prefix from ICAO code for new schema lookup.

        Examples:
            LFXU -> XU (France)
            LFPG -> PG (France)
            EGLL -> LL (UK) - though not in French DB
        """
        icao = icao.upper().strip()
        if len(icao) == 4 and icao[:2] in ("LF", "TF"):
            return icao[2:]
        return icao

    @staticmethod
    def _add_icao_prefix(short_icao: str) -> str:
        """Add LF prefix to short ICAO code from new schema."""
        if len(short_icao) == 2:
            return f"LF{short_icao}"
        return short_icao

    @staticmethod
    def _is_valid_icao(icao: str) -> bool:
        """Check if ICAO code is valid (4 uppercase letters)."""
        return len(icao) == 4 and icao.isalpha() and icao.isupper()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_by_icao(self, icao: str) -> AerodromeInfo | None:
        """Lookup a single aerodrome by ICAO code (full join)."""
        conn = self._manager.get_connection()
        try:
            # Detect schema on first use
            if self._use_new_schema is None:
                self._use_new_schema = self._detect_schema(conn)

            if self._use_new_schema:
                return self._get_by_icao_new(conn, icao)
            else:
                return self._get_by_icao_legacy(conn, icao)
        finally:
            conn.close()

    def _get_by_icao_new(self, conn: sqlite3.Connection, icao: str) -> AerodromeInfo | None:
        """Query using new aerodrome schema."""
        short_icao = self._strip_icao_prefix(icao)
        row = conn.execute(
            "SELECT * FROM aerodrome WHERE icao = ?", (short_icao,)
        ).fetchone()
        if row is None:
            return None

        runways = self._get_runways_new(conn, short_icao)
        services = self._get_services_new(conn, short_icao)

        return AerodromeInfo(
            icao=self._add_icao_prefix(row["icao"]),
            name=row["name"] or "",
            status=self._map_status(row["status"]),
            vfr=row["vfr"] == "oui" if row["vfr"] else True,
            private=row["private"] == "oui" if row["private"] else False,
            latitude=row["latitude"],
            longitude=row["longitude"],
            elevation_ft=int(row["elevation_ft"]) if row["elevation_ft"] else None,
            mag_variation=row["mag_variation"],
            ref_temperature=row["ref_temperature"],
            runways=runways,
            services=services,
        )

    def _get_by_icao_legacy(self, conn: sqlite3.Connection, icao: str) -> AerodromeInfo | None:
        """Query using legacy Ad schema."""
        row = conn.execute(
            "SELECT * FROM Ad WHERE AdCode = ?", (icao.upper(),)
        ).fetchone()
        if row is None:
            return None

        ad_pk = row["pk"]
        runways = self._get_runways_legacy(conn, ad_pk)
        services = self._get_services_legacy(conn, ad_pk)

        return AerodromeInfo(
            icao=row["AdCode"],
            name=row["AdNomComplet"] or row["AdNomCarto"] or "",
            status=self._map_status(row["AdStatut"]),
            vfr=row["TfcVfr"] == "OUI" if row["TfcVfr"] else True,
            private=row["TfcPrive"] == "OUI" if row["TfcPrive"] else False,
            latitude=row["ArpLat"],
            longitude=row["ArpLong"],
            elevation_ft=row["AdRefAltFt"],
            mag_variation=row["AdMagVar"],
            ref_temperature=row["AdRefTemp"],
            runways=runways,
            services=services,
        )

    def search_bbox(
        self,
        lat_min: float,
        lon_min: float,
        lat_max: float,
        lon_max: float,
    ) -> list[AerodromeInfo]:
        """Find aerodromes within a bounding box (lightweight, no joins)."""
        conn = self._manager.get_connection()
        try:
            # Detect schema on first use
            if self._use_new_schema is None:
                self._use_new_schema = self._detect_schema(conn)

            if self._use_new_schema:
                return self._search_bbox_new(conn, lat_min, lon_min, lat_max, lon_max)
            else:
                return self._search_bbox_legacy(conn, lat_min, lon_min, lat_max, lon_max)
        finally:
            conn.close()

    def _search_bbox_new(
        self,
        conn: sqlite3.Connection,
        lat_min: float,
        lon_min: float,
        lat_max: float,
        lon_max: float,
    ) -> list[AerodromeInfo]:
        """Search using new aerodrome schema."""
        rows = conn.execute(
            """
            SELECT icao, name, latitude, longitude, elevation_ft, status, vfr, private
            FROM aerodrome
            WHERE latitude BETWEEN ? AND ?
              AND longitude BETWEEN ? AND ?
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            """,
            (lat_min, lat_max, lon_min, lon_max),
        ).fetchall()

        results = []
        for r in rows:
            full_icao = self._add_icao_prefix(r["icao"])
            # Skip entries with invalid ICAO codes (e.g., numeric codes like "41")
            if not self._is_valid_icao(full_icao):
                continue
            results.append(
                AerodromeInfo(
                    icao=full_icao,
                    name=r["name"] or "",
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    elevation_ft=int(r["elevation_ft"]) if r["elevation_ft"] else None,
                    status=self._map_status(r["status"]),
                    vfr=r["vfr"] == "oui" if r["vfr"] else True,
                    private=r["private"] == "oui" if r["private"] else False,
                )
            )
        return results

    def _search_bbox_legacy(
        self,
        conn: sqlite3.Connection,
        lat_min: float,
        lon_min: float,
        lat_max: float,
        lon_max: float,
    ) -> list[AerodromeInfo]:
        """Search using legacy Ad schema."""
        rows = conn.execute(
            """
            SELECT AdCode, AdNomComplet, AdNomCarto, ArpLat, ArpLong,
                   AdRefAltFt, AdStatut, TfcVfr, TfcPrive
            FROM Ad
            WHERE ArpLat BETWEEN ? AND ?
              AND ArpLong BETWEEN ? AND ?
              AND ArpLat IS NOT NULL
              AND ArpLong IS NOT NULL
            """,
            (lat_min, lat_max, lon_min, lon_max),
        ).fetchall()

        return [
            AerodromeInfo(
                icao=r["AdCode"],
                name=r["AdNomComplet"] or r["AdNomCarto"] or "",
                latitude=r["ArpLat"],
                longitude=r["ArpLong"],
                elevation_ft=r["AdRefAltFt"],
                status=self._map_status(r["AdStatut"]),
                vfr=r["TfcVfr"] == "OUI" if r["TfcVfr"] else True,
                private=r["TfcPrive"] == "OUI" if r["TfcPrive"] else False,
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Private - New schema helpers
    # ------------------------------------------------------------------

    def _get_runways_new(self, conn: sqlite3.Connection, short_icao: str) -> list[Runway]:
        """Get runways using new aerodrome_runway schema."""
        rows = conn.execute(
            """
            SELECT designator, length_m, width_m, is_main, surface, lda1_m, lda2_m
            FROM aerodrome_runway
            WHERE icao = ?
            """,
            (short_icao,),
        ).fetchall()

        return [
            Runway(
                designator=r["designator"] or "",
                length_m=r["length_m"],
                width_m=r["width_m"],
                is_main=r["is_main"] == "oui" if r["is_main"] else False,
                surface=r["surface"],
                lda1_m=r["lda1_m"],
                lda2_m=r["lda2_m"],
            )
            for r in rows
        ]

    def _get_services_new(self, conn: sqlite3.Connection, short_icao: str) -> list[AerodromeService]:
        """Get services using new aerodrome_service schema with frequencies from Frequence table."""
        # Query services with frequencies via Service_pk join
        # Note: aerodrome_service uses 'id' column, Frequence uses 'Service_pk'
        rows = conn.execute(
            """
            SELECT s.id, s.service_type, s.callsign, s.hours_code, s.hours_text,
                   f.Frequence, f.Espacement
            FROM aerodrome_service s
            LEFT JOIN Frequence f ON f.Service_pk = s.id
            WHERE s.icao = ?
            """,
            (short_icao,),
        ).fetchall()

        # Group frequencies by service
        services: dict[int, AerodromeService] = {}
        for r in rows:
            s_pk = r["id"]
            if s_pk not in services:
                services[s_pk] = AerodromeService(
                    service_type=r["service_type"] or "",
                    callsign=r["callsign"] or "",
                    hours_code=r["hours_code"],
                    hours_text=r["hours_text"],
                    frequencies=[],
                )
            if r["Frequence"]:
                services[s_pk].frequencies.append(
                    AerodromeFrequency(
                        frequency_mhz=r["Frequence"],
                        spacing=r["Espacement"],
                    )
                )
        return list(services.values())

    # ------------------------------------------------------------------
    # Private - Legacy schema helpers
    # ------------------------------------------------------------------

    def _get_runways_legacy(self, conn: sqlite3.Connection, ad_pk: int) -> list[Runway]:
        """Get runways using legacy Rwy schema."""
        rows = conn.execute(
            """
            SELECT Rwy, Longueur, Largeur, Principale, Revetement,
                   Lda1, Lda2
            FROM Rwy
            WHERE Ad_pk = ?
            """,
            (ad_pk,),
        ).fetchall()

        return [
            Runway(
                designator=r["Rwy"] or "",
                length_m=r["Longueur"],
                width_m=r["Largeur"],
                is_main=r["Principale"] == "OUI" if r["Principale"] else False,
                surface=r["Revetement"],
                lda1_m=r["Lda1"],
                lda2_m=r["Lda2"],
            )
            for r in rows
        ]

    def _get_services_legacy(
        self, conn: sqlite3.Connection, ad_pk: int
    ) -> list[AerodromeService]:
        """Get services using legacy Service/Frequence schema."""
        rows = conn.execute(
            """
            SELECT s.pk, s.Service, s.IndicLieu, s.HorCode, s.HorTxt,
                   f.Frequence, f.Espacement
            FROM Service s
            LEFT JOIN Frequence f ON f.Service_pk = s.pk
            WHERE s.Ad_pk = ?
            """,
            (ad_pk,),
        ).fetchall()

        services: dict[int, AerodromeService] = {}
        for r in rows:
            s_pk = r["pk"]
            if s_pk not in services:
                services[s_pk] = AerodromeService(
                    service_type=r["Service"] or "",
                    callsign=r["IndicLieu"] or "",
                    hours_code=r["HorCode"],
                    hours_text=r["HorTxt"],
                    frequencies=[],
                )
            if r["Frequence"]:
                services[s_pk].frequencies.append(
                    AerodromeFrequency(
                        frequency_mhz=r["Frequence"],
                        spacing=r["Espacement"],
                    )
                )
        return list(services.values())

    def search_near_route(
        self,
        route_coords: list[tuple[float, float]],
        buffer_nm: float = 15.0,
        exclude_icaos: list[str] | None = None,
    ) -> list[AerodromeInfo]:
        """Find aerodromes within a buffer around the route path.

        Args:
            route_coords: List of (lat, lon) tuples defining the route
            buffer_nm: Search buffer in nautical miles (default 15)
            exclude_icaos: ICAO codes to exclude (typically DEP/ARR)

        Returns:
            List of AerodromeInfo objects found near the route
        """
        if len(route_coords) < 2:
            return []

        # Build bounding box with buffer
        lats = [c[0] for c in route_coords]
        lons = [c[1] for c in route_coords]
        # ~1 degree latitude = 60 nm, ~1 degree longitude = 60 * cos(lat) nm
        avg_lat = sum(lats) / len(lats)
        lat_buffer = buffer_nm / 60.0
        lon_buffer = buffer_nm / (60.0 * max(0.1, abs(__import__("math").cos(__import__("math").radians(avg_lat)))))

        lat_min = min(lats) - lat_buffer
        lat_max = max(lats) + lat_buffer
        lon_min = min(lons) - lon_buffer
        lon_max = max(lons) + lon_buffer

        # Get all aerodromes in bounding box
        candidates = self.search_bbox(lat_min, lon_min, lat_max, lon_max)

        # Filter to those actually within buffer distance of the route
        exclude_set = set(ic.upper() for ic in (exclude_icaos or []))
        results = []
        for ad in candidates:
            if ad.icao in exclude_set:
                continue
            # Check if aerodrome is within buffer of any route segment
            if self._is_within_buffer(ad.latitude, ad.longitude, route_coords, buffer_nm):
                results.append(ad)

        return results

    @staticmethod
    def _is_within_buffer(
        lat: float,
        lon: float,
        route_coords: list[tuple[float, float]],
        buffer_nm: float,
    ) -> bool:
        """Check if a point is within buffer distance of any route segment."""
        import math

        def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            la1, lo1 = math.radians(lat1), math.radians(lon1)
            la2, lo2 = math.radians(lat2), math.radians(lon2)
            dlat = la2 - la1
            dlon = lo2 - lo1
            a = math.sin(dlat / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlon / 2) ** 2
            return 2 * math.asin(math.sqrt(a)) * 3440.065

        def point_to_segment_dist_nm(
            plat: float, plon: float, lat1: float, lon1: float, lat2: float, lon2: float
        ) -> float:
            """Approximate cross-track distance from point to segment."""
            # Distance to endpoints
            d1 = haversine_nm(plat, plon, lat1, lon1)
            d2 = haversine_nm(plat, plon, lat2, lon2)
            seg_len = haversine_nm(lat1, lon1, lat2, lon2)

            if seg_len < 0.1:
                return d1

            # Check if point projects onto segment (using along-track position)
            # Simplified: if d1 or d2 is less than buffer, it's close enough
            # Otherwise, estimate cross-track distance
            d12 = haversine_nm(lat1, lon1, lat2, lon2)
            if d12 < 0.1:
                return d1

            # Cross-track distance approximation using triangle area
            # area = 0.5 * base * height => height = 2 * area / base
            # For small distances, we can approximate
            s = (d1 + d2 + d12) / 2
            if s <= d1 or s <= d2 or s <= d12:
                return min(d1, d2)
            area_sq = s * (s - d1) * (s - d2) * (s - d12)
            if area_sq <= 0:
                return min(d1, d2)
            area = math.sqrt(area_sq)
            height = 2 * area / d12

            # Check if point is "between" the segment endpoints
            # by checking if along-track distance is within segment
            along1 = math.sqrt(max(0, d1 * d1 - height * height))
            along2 = math.sqrt(max(0, d2 * d2 - height * height))

            # If along1 + along2 ≈ d12, point projects onto segment
            if along1 <= d12 and along2 <= d12 and abs(along1 + along2 - d12) < d12 * 0.5:
                return height

            return min(d1, d2)

        for i in range(len(route_coords) - 1):
            lat1, lon1 = route_coords[i]
            lat2, lon2 = route_coords[i + 1]
            dist = point_to_segment_dist_nm(lat, lon, lat1, lon1, lat2, lon2)
            if dist <= buffer_nm:
                return True

        return False

    @staticmethod
    def _map_status(raw: str | None) -> AerodromeStatus:
        """Map status string to enum. Case-insensitive for compatibility."""
        if not raw:
            return AerodromeStatus.CAP
        status = raw.upper().strip()
        if status == "CAP":
            return AerodromeStatus.CAP
        if status in ("MIL", "MILITARY"):
            return AerodromeStatus.MILITARY
        if status in ("RES", "RESTRICTED", "RESTREINT"):
            return AerodromeStatus.RESTRICTED
        return AerodromeStatus.CAP
