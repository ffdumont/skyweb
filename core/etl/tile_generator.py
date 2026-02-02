"""Generate GeoJSON tiles from SpatiaLite database by zoom level."""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# Zoom level configuration: (min_z, max_z) → (type_filter, tolerance_degrees)
ZOOM_CONFIG: list[tuple[tuple[int, int], list[str] | None, float]] = [
    ((0, 5), ["FIR", "TMA"], 0.01),
    ((6, 8), ["TMA", "CTR", "SIV", "D", "R", "P"], 0.001),
    ((9, 12), None, 0.0001),  # None = all types
]


class TileGenerator:
    """Generates GeoJSON tiles from a SpatiaLite database."""

    def __init__(self, db_path: Path, output_dir: Path):
        self._db_path = db_path
        self._output_dir = output_dir

    def generate_all(self) -> int:
        """Generate all tiles across all zoom levels. Returns total tile count."""
        total = 0
        for (z_min, z_max), type_filter, tolerance in ZOOM_CONFIG:
            for z in range(z_min, z_max + 1):
                total += self._generate_zoom_level(z, type_filter, tolerance)
        self._write_tileset_json()
        logger.info("Generated %d total tiles in %s", total, self._output_dir)
        return total

    def _generate_zoom_level(
        self,
        z: int,
        type_filter: list[str] | None,
        tolerance: float,
    ) -> int:
        """Generate all tiles at a zoom level. Returns tile count."""
        conn = sqlite3.connect(str(self._db_path))
        conn.enable_load_extension(True)
        try:
            from core.persistence.spatialite.db_manager import _load_spatialite
            _load_spatialite(conn)
        except Exception:
            logger.warning("SpatiaLite not available — tiles will have unsimplified geometries")

        count = 0
        n_tiles = 2 ** z
        for x in range(n_tiles):
            for y in range(n_tiles):
                bbox = tile_bbox(z, x, y)
                features = self._query_tile(conn, bbox, type_filter, tolerance)
                if features:
                    self._write_tile(z, x, y, features)
                    count += 1

        conn.close()
        return count

    def _query_tile(
        self,
        conn: sqlite3.Connection,
        bbox: tuple[float, float, float, float],
        type_filter: list[str] | None,
        tolerance: float,
    ) -> list[dict]:
        """Query airspaces intersecting a tile bbox."""
        lon_min, lat_min, lon_max, lat_max = bbox

        sql = """
            SELECT
                espace_pk, espace_nom, espace_type, Classe,
                altitude_floor_ft_amsl, altitude_ceiling_ft_amsl,
                AsGeoJSON(SimplifyPreserveTopology(geom_spatial, ?)) AS geojson
            FROM airspace_spatial_indexed
            WHERE geom_spatial IS NOT NULL
              AND MbrIntersects(
                  geom_spatial,
                  BuildMbr(?, ?, ?, ?, 4326)
              )
        """
        params: list = [tolerance, lon_min, lat_min, lon_max, lat_max]

        if type_filter:
            placeholders = ",".join("?" for _ in type_filter)
            sql += f" AND espace_type IN ({placeholders})"
            params.extend(type_filter)

        features: list[dict] = []
        for row in conn.execute(sql, params):
            geojson_str = row[6]
            if not geojson_str:
                continue
            features.append({
                "type": "Feature",
                "properties": {
                    "id": row[0],
                    "name": row[1],
                    "type": row[2],
                    "class": row[3],
                    "floor_ft": row[4],
                    "ceiling_ft": row[5],
                },
                "geometry": json.loads(geojson_str),
            })

        return features

    def _write_tile(self, z: int, x: int, y: int, features: list[dict]) -> None:
        tile_dir = self._output_dir / "airspaces" / str(z) / str(x)
        tile_dir.mkdir(parents=True, exist_ok=True)
        tile_path = tile_dir / f"{y}.json"
        geojson = {
            "type": "FeatureCollection",
            "features": features,
        }
        tile_path.write_text(json.dumps(geojson), encoding="utf-8")

    def _write_tileset_json(self) -> None:
        """Write a tileset metadata file."""
        meta = {
            "format": "geojson",
            "tile_url": "airspaces/{z}/{x}/{y}.json",
            "zoom_levels": {
                "0-5": {"types": ["FIR", "TMA"], "tolerance": 0.01},
                "6-8": {"types": ["TMA", "CTR", "SIV", "D", "R", "P"], "tolerance": 0.001},
                "9-12": {"types": "all", "tolerance": 0.0001},
            },
        }
        meta_path = self._output_dir / "tileset.json"
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def tile_bbox(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """Convert tile coordinates to (lon_min, lat_min, lon_max, lat_max).

    Uses the standard Slippy Map tile scheme (Web Mercator).
    """
    n = 2.0 ** z
    lon_min = x / n * 360.0 - 180.0
    lon_max = (x + 1) / n * 360.0 - 180.0
    lat_max = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    lat_min = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return (lon_min, lat_min, lon_max, lat_max)
