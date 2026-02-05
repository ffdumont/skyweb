"""SpatiaLite database manager — download from GCS, cache, serve read-only connections."""

from __future__ import annotations

import logging
import sqlite3
import tempfile
from pathlib import Path

from core.persistence.errors import SpatiaLiteNotReadyError
from core.persistence.spatialite.spatialite_loader import enable_spatialite

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
        enable_spatialite(conn)
        return conn
