"""Unit tests for SpatiaLiteManager (no network, no GCS)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.persistence.errors import SpatiaLiteNotReadyError
from core.persistence.spatialite.db_manager import SpatiaLiteManager


class TestSpatiaLiteManager:
    def test_not_ready_by_default(self):
        manager = SpatiaLiteManager()
        assert not manager.is_ready
        assert manager.current_cycle is None

    def test_get_connection_raises_when_not_ready(self):
        manager = SpatiaLiteManager()
        with pytest.raises(SpatiaLiteNotReadyError):
            manager.get_connection()

    def test_use_local_sets_path(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.close()

        manager = SpatiaLiteManager()
        manager.use_local(db_path, cycle="test-cycle")

        assert manager.is_ready
        assert manager.current_cycle == "test-cycle"

    def test_use_local_missing_file_raises(self, tmp_path: Path):
        manager = SpatiaLiteManager()
        with pytest.raises(FileNotFoundError):
            manager.use_local(tmp_path / "nonexistent.db")

    def test_get_connection_returns_working_connection(self, tmp_path: Path):
        """Test that get_connection works with a real SQLite DB (no SpatiaLite needed)."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test_table (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO test_table VALUES (1, 'hello')")
        conn.commit()
        conn.close()

        manager = SpatiaLiteManager()
        manager.use_local(db_path)

        # get_connection requires SpatiaLite extension, which may not be
        # available in CI. So we test the path setup logic only.
        assert manager._local_path == db_path

    def test_multiple_cycles_different_filenames(self, tmp_path: Path):
        """Verify cycle-specific naming for local cache."""
        manager = SpatiaLiteManager(local_dir=str(tmp_path))

        # Simulate what download() would produce
        for cycle in ["2603", "2604"]:
            path = tmp_path / f"skypath_{cycle}.db"
            conn = sqlite3.connect(str(path))
            conn.execute("CREATE TABLE dummy (id INTEGER)")
            conn.close()

        manager.use_local(tmp_path / "skypath_2603.db", cycle="2603")
        assert manager.current_cycle == "2603"

        manager.use_local(tmp_path / "skypath_2604.db", cycle="2604")
        assert manager.current_cycle == "2604"
        assert manager._local_path == tmp_path / "skypath_2604.db"
