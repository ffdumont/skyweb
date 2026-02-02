"""Tests for tile generator utilities."""

from __future__ import annotations

import math

from core.etl.tile_generator import tile_bbox


class TestTileBbox:
    def test_zoom_0_single_tile(self):
        """Zoom 0 has a single tile covering the world."""
        lon_min, lat_min, lon_max, lat_max = tile_bbox(0, 0, 0)
        assert lon_min == -180.0
        assert lon_max == 180.0
        assert lat_max > 80  # Mercator limit
        assert lat_min < -80

    def test_zoom_1_four_tiles(self):
        """Zoom 1 splits the world into 4 tiles."""
        # Top-left tile
        lon_min, lat_min, lon_max, lat_max = tile_bbox(1, 0, 0)
        assert lon_min == -180.0
        assert lon_max == 0.0
        assert lat_max > 0

        # Bottom-right tile
        lon_min, lat_min, lon_max, lat_max = tile_bbox(1, 1, 1)
        assert lon_min == 0.0
        assert lon_max == 180.0
        assert lat_max <= 0

    def test_tile_bbox_has_positive_area(self):
        for z in range(5):
            for x in range(2**z):
                for y in range(2**z):
                    lon_min, lat_min, lon_max, lat_max = tile_bbox(z, x, y)
                    assert lon_max > lon_min
                    assert lat_max > lat_min

    def test_france_tile_at_zoom_6(self):
        """France (~47°N, 2°E) should be covered by specific tiles at Z6."""
        # At Z6, n=64, France is roughly at x=32, y=22
        lon_min, lat_min, lon_max, lat_max = tile_bbox(6, 32, 22)
        # This tile should be in the vicinity of western Europe
        assert lon_min >= 0
        assert lon_max <= 10
        assert lat_min > 40
        assert lat_max < 55
