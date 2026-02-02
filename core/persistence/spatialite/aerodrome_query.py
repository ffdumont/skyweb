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
    """Read-only aerodrome lookups backed by SpatiaLite."""

    def __init__(self, manager: SpatiaLiteManager):
        self._manager = manager

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_by_icao(self, icao: str) -> AerodromeInfo | None:
        """Lookup a single aerodrome by ICAO code (full join)."""
        conn = self._manager.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM Ad WHERE AdCode = ?", (icao.upper(),)
            ).fetchone()
            if row is None:
                return None

            ad_pk = row["pk"]
            runways = self._get_runways(conn, ad_pk)
            services = self._get_services(conn, ad_pk)

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
        finally:
            conn.close()

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
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _get_runways(self, conn: sqlite3.Connection, ad_pk: int) -> list[Runway]:
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

    def _get_services(
        self, conn: sqlite3.Connection, ad_pk: int
    ) -> list[AerodromeService]:
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

    @staticmethod
    def _map_status(raw: str | None) -> AerodromeStatus:
        if raw == "CAP":
            return AerodromeStatus.CAP
        if raw == "MIL":
            return AerodromeStatus.MILITARY
        if raw == "RES":
            return AerodromeStatus.RESTRICTED
        return AerodromeStatus.CAP
