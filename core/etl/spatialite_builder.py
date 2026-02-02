"""Build a SpatiaLite database from parsed SIA data."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from core.etl.sia_parser import ParsedSIA

logger = logging.getLogger(__name__)


class SpatiaLiteBuilder:
    """Builds the SpatiaLite reference database used by query services."""

    def __init__(self, db_path: Path):
        self._db_path = db_path

    def build(self, data: ParsedSIA) -> Path:
        """Build the complete SpatiaLite database.

        Steps:
        1. Create tables
        2. Insert parsed data
        3. Build spatial geometries from WKT
        4. Create materialized view with altitude conversion
        5. Build R-tree spatial index
        """
        conn = sqlite3.connect(str(self._db_path))
        try:
            self._load_spatialite(conn)
            self._create_tables(conn)
            self._insert_data(conn, data)
            self._build_spatial_geometries(conn)
            self._create_materialized_view(conn)
            self._create_spatial_index(conn)
            conn.execute("VACUUM")
            conn.commit()
        finally:
            conn.close()

        size = self._db_path.stat().st_size
        logger.info("Built SpatiaLite DB: %s (%d bytes)", self._db_path, size)
        return self._db_path

    def _load_spatialite(self, conn: sqlite3.Connection) -> None:
        conn.enable_load_extension(True)
        from core.persistence.spatialite.db_manager import _load_spatialite
        _load_spatialite(conn)
        conn.execute("SELECT InitSpatialMetadata(1)")

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS Espace (
                pk INTEGER PRIMARY KEY AUTOINCREMENT,
                EspaceId TEXT,
                Nom TEXT,
                TypeEspace TEXT,
                Classe TEXT
            );

            CREATE TABLE IF NOT EXISTS Partie (
                pk INTEGER PRIMARY KEY AUTOINCREMENT,
                espace_pk INTEGER REFERENCES Espace(pk),
                PartieId TEXT,
                Nom TEXT
            );

            CREATE TABLE IF NOT EXISTS Volume (
                pk INTEGER PRIMARY KEY AUTOINCREMENT,
                partie_pk INTEGER REFERENCES Partie(pk),
                VolumeId TEXT,
                Plancher TEXT,
                PlancherRef TEXT,
                PlancherVal TEXT,
                Plafond TEXT,
                PlafondRef TEXT,
                PlafondVal TEXT,
                HorCode TEXT
            );

            CREATE TABLE IF NOT EXISTS Geometrie (
                pk INTEGER PRIMARY KEY AUTOINCREMENT,
                partie_pk INTEGER REFERENCES Partie(pk),
                WKT TEXT
            );

            CREATE TABLE IF NOT EXISTS Service (
                pk INTEGER PRIMARY KEY AUTOINCREMENT,
                IndicLieu TEXT,
                Indicatif TEXT,
                TypeService TEXT,
                Langue TEXT,
                HorCode TEXT,
                HorTxt TEXT
            );

            CREATE TABLE IF NOT EXISTS Frequence (
                pk INTEGER PRIMARY KEY AUTOINCREMENT,
                service_pk INTEGER,
                IndicLieu TEXT,
                Frequence TEXT,
                Espacement TEXT,
                HorCode TEXT,
                HorTxt TEXT,
                Secteur TEXT,
                Remarques TEXT
            );

            CREATE TABLE IF NOT EXISTS Ad (
                pk INTEGER PRIMARY KEY AUTOINCREMENT,
                AdCode TEXT UNIQUE,
                AdNomComplet TEXT,
                AdStatut TEXT,
                ArpLat REAL,
                ArpLon REAL,
                AdRefAltFt REAL,
                DecMag REAL,
                TempRef REAL,
                HorCode TEXT,
                Carburant TEXT,
                CarburantRem TEXT,
                MetCentre TEXT,
                MetBriefing TEXT,
                CatSSLIA TEXT,
                Gestionnaire TEXT,
                Telephone TEXT,
                Remarques TEXT
            );

            CREATE TABLE IF NOT EXISTS Rwy (
                pk INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_pk INTEGER REFERENCES Ad(pk),
                AdCode TEXT,
                Identifiant TEXT,
                Longueur REAL,
                Largeur REAL,
                Principal INTEGER,
                Revetement TEXT,
                PCN TEXT,
                OrientationGeo REAL,
                LatSeuil1 REAL,
                LonSeuil1 REAL,
                AltFtSeuil1 REAL,
                LDA1 REAL,
                LatSeuil2 REAL,
                LonSeuil2 REAL,
                AltFtSeuil2 REAL,
                LDA2 REAL
            );
        """)

    def _insert_data(self, conn: sqlite3.Connection, data: ParsedSIA) -> None:
        espace_pk_map: dict[str, int] = {}
        partie_pk_map: dict[str, int] = {}
        ad_pk_map: dict[str, int] = {}

        # Espaces
        for e in data.espaces:
            cur = conn.execute(
                "INSERT INTO Espace (EspaceId, Nom, TypeEspace, Classe) VALUES (?,?,?,?)",
                (e.get("pk", e.get("EspaceId", "")),
                 e.get("Nom", ""),
                 e.get("TypeEspace", ""),
                 e.get("Classe", "")),
            )
            espace_pk_map[e.get("pk", e.get("EspaceId", ""))] = cur.lastrowid

        # Parties
        for p in data.parties:
            esp_pk = espace_pk_map.get(p.get("espace_pk", p.get("EspaceId", "")), None)
            cur = conn.execute(
                "INSERT INTO Partie (espace_pk, PartieId, Nom) VALUES (?,?,?)",
                (esp_pk, p.get("pk", p.get("PartieId", "")), p.get("Nom", "")),
            )
            partie_pk_map[p.get("pk", p.get("PartieId", ""))] = cur.lastrowid

        # Volumes
        for v in data.volumes:
            part_pk = partie_pk_map.get(v.get("partie_pk", v.get("PartieId", "")), None)
            conn.execute(
                """INSERT INTO Volume
                   (partie_pk, VolumeId, Plancher, PlancherRef, PlancherVal,
                    Plafond, PlafondRef, PlafondVal, HorCode)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (part_pk, v.get("pk", v.get("VolumeId", "")),
                 v.get("Plancher", ""), v.get("PlancherRef", ""), v.get("PlancherVal", ""),
                 v.get("Plafond", ""), v.get("PlafondRef", ""), v.get("PlafondVal", ""),
                 v.get("HorCode", "")),
            )

        # Geometries
        for g in data.geometries:
            part_pk = partie_pk_map.get(g.get("partie_pk", g.get("PartieId", "")), None)
            conn.execute(
                "INSERT INTO Geometrie (partie_pk, WKT) VALUES (?,?)",
                (part_pk, g.get("WKT", g.get("wkt", ""))),
            )

        # Services
        service_pk_map: dict[str, int] = {}
        for s in data.services:
            cur = conn.execute(
                """INSERT INTO Service
                   (IndicLieu, Indicatif, TypeService, Langue, HorCode, HorTxt)
                   VALUES (?,?,?,?,?,?)""",
                (s.get("IndicLieu", ""), s.get("Indicatif", ""),
                 s.get("TypeService", ""), s.get("Langue", ""),
                 s.get("HorCode", ""), s.get("HorTxt", "")),
            )
            service_pk_map[s.get("pk", s.get("IndicLieu", ""))] = cur.lastrowid

        # Frequencies
        for f in data.frequencies:
            svc_pk = service_pk_map.get(f.get("service_pk", f.get("IndicLieu", "")), None)
            conn.execute(
                """INSERT INTO Frequence
                   (service_pk, IndicLieu, Frequence, Espacement, HorCode, HorTxt, Secteur, Remarques)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (svc_pk, f.get("IndicLieu", ""), f.get("Frequence", ""),
                 f.get("Espacement", ""), f.get("HorCode", ""),
                 f.get("HorTxt", ""), f.get("Secteur", ""), f.get("Remarques", "")),
            )

        # Aerodromes
        for ad in data.aerodromes:
            cur = conn.execute(
                """INSERT INTO Ad
                   (AdCode, AdNomComplet, AdStatut, ArpLat, ArpLon, AdRefAltFt,
                    DecMag, TempRef, HorCode, Carburant, CarburantRem,
                    MetCentre, MetBriefing, CatSSLIA, Gestionnaire, Telephone, Remarques)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ad.get("AdCode", ""), ad.get("AdNomComplet", ""), ad.get("AdStatut", ""),
                 _float(ad.get("ArpLat")), _float(ad.get("ArpLon")),
                 _float(ad.get("AdRefAltFt")), _float(ad.get("DecMag")),
                 _float(ad.get("TempRef")), ad.get("HorCode", ""),
                 ad.get("Carburant", ""), ad.get("CarburantRem", ""),
                 ad.get("MetCentre", ""), ad.get("MetBriefing", ""),
                 ad.get("CatSSLIA", ""), ad.get("Gestionnaire", ""),
                 ad.get("Telephone", ""), ad.get("Remarques", "")),
            )
            ad_pk_map[ad.get("AdCode", "")] = cur.lastrowid

        # Runways
        for rwy in data.runways:
            a_pk = ad_pk_map.get(rwy.get("AdCode", ""), None)
            conn.execute(
                """INSERT INTO Rwy
                   (ad_pk, AdCode, Identifiant, Longueur, Largeur, Principal,
                    Revetement, PCN, OrientationGeo,
                    LatSeuil1, LonSeuil1, AltFtSeuil1, LDA1,
                    LatSeuil2, LonSeuil2, AltFtSeuil2, LDA2)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (a_pk, rwy.get("AdCode", ""), rwy.get("Identifiant", ""),
                 _float(rwy.get("Longueur")), _float(rwy.get("Largeur")),
                 _int(rwy.get("Principal")),
                 rwy.get("Revetement", ""), rwy.get("PCN", ""),
                 _float(rwy.get("OrientationGeo")),
                 _float(rwy.get("LatSeuil1")), _float(rwy.get("LonSeuil1")),
                 _float(rwy.get("AltFtSeuil1")), _float(rwy.get("LDA1")),
                 _float(rwy.get("LatSeuil2")), _float(rwy.get("LonSeuil2")),
                 _float(rwy.get("AltFtSeuil2")), _float(rwy.get("LDA2"))),
            )

        conn.commit()

    def _build_spatial_geometries(self, conn: sqlite3.Connection) -> None:
        """Convert WKT text geometries into SpatiaLite spatial column."""
        conn.execute(
            "SELECT AddGeometryColumn('Geometrie', 'geom', 4326, 'GEOMETRY', 'XY')"
        )
        conn.execute("""
            UPDATE Geometrie
            SET geom = GeomFromText(WKT, 4326)
            WHERE WKT IS NOT NULL AND WKT != ''
        """)
        conn.commit()

    def _create_materialized_view(self, conn: sqlite3.Connection) -> None:
        """Create the pre-joined view used by AirspaceQueryService."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS airspace_spatial_indexed AS
            SELECT
                p.pk AS partie_pk,
                e.pk AS espace_pk,
                e.Nom AS espace_nom,
                e.TypeEspace AS espace_type,
                p.Nom AS partie_nom,
                v.pk AS volume_pk,
                CAST(COALESCE(NULLIF(v.PlancherVal, ''), '0') AS REAL) AS altitude_floor_ft_amsl,
                CAST(COALESCE(NULLIF(v.PlafondVal, ''), '99999') AS REAL) AS altitude_ceiling_ft_amsl,
                e.Classe AS Classe,
                v.HorCode AS HorCode,
                'ok' AS conversion_status,
                g.geom AS geom_spatial
            FROM Partie p
            JOIN Espace e ON p.espace_pk = e.pk
            JOIN Volume v ON v.partie_pk = p.pk
            JOIN Geometrie g ON g.partie_pk = p.pk
            WHERE g.geom IS NOT NULL
        """)
        conn.commit()

    def _create_spatial_index(self, conn: sqlite3.Connection) -> None:
        """Create R-tree spatial index on the materialized view."""
        try:
            conn.execute(
                "SELECT CreateSpatialIndex('airspace_spatial_indexed', 'geom_spatial')"
            )
            conn.commit()
        except Exception:
            logger.warning("Could not create spatial index (may already exist)")


def _float(val) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _int(val) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
