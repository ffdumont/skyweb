"""SpatiaLite database manager — download from GCS, cache, serve read-only connections."""

from __future__ import annotations

import logging
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from core.persistence.errors import SpatiaLiteNotReadyError

logger = logging.getLogger(__name__)


class SpatiaLiteManager:
    """Manages the read-only SpatiaLite reference database lifecycle.

    - Downloads the current AIRAC database from GCS (or uses a local path).
    - Opens read-only connections with SpatiaLite loaded.
    - Thread-safe: each caller gets its own connection (read-only = no locks).
    """

    def __init__(
        self,
        bucket_name: str = "skyweb-reference",
        db_prefix: str = "airac",
        db_filename: str = "skypath.db",
        local_dir: str | None = None,
    ):
        self._bucket_name = bucket_name
        self._db_prefix = db_prefix
        self._db_filename = db_filename
        self._local_dir = Path(local_dir or tempfile.gettempdir())
        self._current_cycle: str | None = None
        self._local_path: Path | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_cycle(self) -> str | None:
        return self._current_cycle

    @property
    def is_ready(self) -> bool:
        return self._local_path is not None and self._local_path.exists()

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download(self, cycle: str | None = None) -> Path:
        """Download the SpatiaLite DB from GCS.

        If *cycle* is ``None``, reads the current cycle pointer from
        ``gs://{bucket}/current_cycle``.

        Returns the local path to the database file.
        """
        from google.cloud import storage

        client = storage.Client()
        bucket = client.bucket(self._bucket_name)

        if cycle is None:
            blob = bucket.blob("current_cycle")
            cycle = blob.download_as_text().strip()

        local_path = self._local_dir / f"skypath_{cycle}.db"

        if local_path.exists():
            logger.info("SpatiaLite DB already cached: %s", local_path)
            self._current_cycle = cycle
            self._local_path = local_path
            return local_path

        gcs_path = f"{self._db_prefix}/{cycle}/{self._db_filename}"
        logger.info("Downloading %s from gs://%s/%s", gcs_path, self._bucket_name, gcs_path)

        blob = bucket.blob(gcs_path)
        blob.download_to_filename(str(local_path))

        self._current_cycle = cycle
        self._local_path = local_path
        logger.info("Downloaded SpatiaLite DB: %s (%d bytes)", local_path, local_path.stat().st_size)
        return local_path

    def use_local(self, path: Path, cycle: str = "local") -> None:
        """Use a local database file directly (for dev/testing)."""
        if not path.exists():
            raise FileNotFoundError(f"SpatiaLite DB not found: {path}")
        self._local_path = path
        self._current_cycle = cycle

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def get_connection(self) -> sqlite3.Connection:
        """Open a new read-only SQLite connection with SpatiaLite loaded.

        Each call returns a fresh connection. The caller is responsible
        for closing it (use ``with`` or ``try/finally``).
        """
        if not self.is_ready:
            raise SpatiaLiteNotReadyError(
                "SpatiaLite database not available. Call download() or use_local() first."
            )

        uri = f"file:{self._local_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        _load_spatialite(conn)
        return conn


# ------------------------------------------------------------------
# SpatiaLite extension loading (cross-platform)
# ------------------------------------------------------------------

def _load_spatialite(conn: sqlite3.Connection) -> None:
    """Load the SpatiaLite extension into a connection.

    Tries, in order:
    1. SPATIALITE_LIBRARY_PATH env var
    2. Platform-specific known paths
    3. Generic library name (relies on system library path)
    """
    conn.enable_load_extension(True)

    # Strategy 1: environment variable
    env_path = os.environ.get("SPATIALITE_LIBRARY_PATH")
    if env_path and _try_load(conn, env_path):
        return

    # Strategy 2: platform-specific paths
    for path in _platform_search_paths():
        if path.exists() and _try_load(conn, str(path)):
            return

    # Strategy 3: generic names
    for name in _generic_names():
        if _try_load(conn, name):
            return

    raise RuntimeError(
        "Failed to load SpatiaLite extension. "
        "Install it (apt-get install libsqlite3-mod-spatialite, "
        "conda install -c conda-forge libspatialite, "
        "or set SPATIALITE_LIBRARY_PATH)."
    )


def _try_load(conn: sqlite3.Connection, lib: str) -> bool:
    try:
        conn.load_extension(lib)
        return True
    except Exception:
        return False


def _platform_search_paths() -> list[Path]:
    if sys.platform == "win32":
        paths: list[Path] = []
        conda = os.environ.get("CONDA_PREFIX")
        if conda:
            paths.append(Path(conda) / "Library" / "bin" / "mod_spatialite.dll")
        for root in [Path("C:/OSGeo4W64"), Path("C:/OSGeo4W")]:
            paths.append(root / "bin" / "mod_spatialite.dll")
        return paths

    if sys.platform == "darwin":
        return [
            Path("/opt/homebrew/lib/mod_spatialite.dylib"),
            Path("/usr/local/lib/mod_spatialite.dylib"),
        ]

    # Linux
    return [
        Path("/usr/lib/x86_64-linux-gnu/mod_spatialite.so"),
        Path("/usr/lib/aarch64-linux-gnu/mod_spatialite.so"),
        Path("/usr/lib64/mod_spatialite.so"),
        Path("/usr/local/lib/mod_spatialite.so"),
    ]


def _generic_names() -> list[str]:
    return ["mod_spatialite", "spatialite", "libspatialite"]
