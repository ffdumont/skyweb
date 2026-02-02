"""Upload ETL outputs to Google Cloud Storage."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class GCSUploader:
    """Uploads SpatiaLite DB and tiles to GCS buckets."""

    def __init__(
        self,
        reference_bucket: str = "skyweb-reference",
        tiles_bucket: str = "skyweb-tiles",
    ):
        self._reference_bucket = reference_bucket
        self._tiles_bucket = tiles_bucket

    def upload_cycle(
        self,
        cycle: str,
        db_path: Path,
        tiles_dir: Path,
    ) -> dict:
        """Upload a complete AIRAC cycle to GCS.

        Returns a summary dict with upload counts.
        """
        from google.cloud import storage

        client = storage.Client()
        summary: dict = {"cycle": cycle, "db_uploaded": False, "tiles_uploaded": 0}

        # Upload SpatiaLite database
        ref_bucket = client.bucket(self._reference_bucket)
        blob = ref_bucket.blob(f"airac/{cycle}/skypath.db")
        blob.upload_from_filename(str(db_path))
        summary["db_uploaded"] = True
        logger.info("Uploaded %s to gs://%s/airac/%s/skypath.db", db_path, self._reference_bucket, cycle)

        # Upload metadata
        metadata = {
            "cycle": cycle,
            "db_size_bytes": db_path.stat().st_size,
        }
        meta_blob = ref_bucket.blob(f"airac/{cycle}/metadata.json")
        meta_blob.upload_from_string(json.dumps(metadata))

        # Upload tiles
        tiles_bkt = client.bucket(self._tiles_bucket)
        tile_count = 0
        for tile_path in tiles_dir.rglob("*.json"):
            rel = tile_path.relative_to(tiles_dir)
            blob = tiles_bkt.blob(f"{cycle}/{rel.as_posix()}")
            blob.upload_from_filename(str(tile_path))
            tile_count += 1

        summary["tiles_uploaded"] = tile_count
        logger.info("Uploaded %d tiles to gs://%s/%s/", tile_count, self._tiles_bucket, cycle)

        return summary

    def set_active_cycle(self, cycle: str) -> None:
        """Update the current_cycle pointer."""
        from google.cloud import storage

        client = storage.Client()
        bucket = client.bucket(self._reference_bucket)
        blob = bucket.blob("current_cycle")
        blob.upload_from_string(cycle)
        logger.info("Set active cycle to %s", cycle)
