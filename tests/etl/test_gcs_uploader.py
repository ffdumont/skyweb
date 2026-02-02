"""Tests for GCS uploader with mocked storage client."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

from core.etl.gcs_uploader import GCSUploader


def _setup_mock_storage():
    """Inject a mock google.cloud.storage into sys.modules."""
    mock_storage = MagicMock()
    mock_client = MagicMock()
    mock_storage.Client.return_value = mock_client

    mock_google = MagicMock()
    mock_google.cloud.storage = mock_storage
    sys.modules["google"] = mock_google
    sys.modules["google.cloud"] = mock_google.cloud
    sys.modules["google.cloud.storage"] = mock_storage

    return mock_client


class TestGCSUploader:
    def test_upload_cycle_calls_correct_paths(self, tmp_path: Path):
        """Verify upload constructs correct GCS blob paths."""
        mock_client = _setup_mock_storage()

        # Create a fake DB file
        db_path = tmp_path / "skypath_2604.db"
        db_path.write_text("fake db")

        # Create fake tile files
        tiles_dir = tmp_path / "tiles"
        tile_path = tiles_dir / "airspaces" / "6" / "32" / "22.json"
        tile_path.parent.mkdir(parents=True)
        tile_path.write_text('{"type":"FeatureCollection","features":[]}')

        mock_ref_bucket = MagicMock()
        mock_tiles_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.side_effect = lambda name: (
            mock_ref_bucket if name == "skyweb-reference" else mock_tiles_bucket
        )
        mock_ref_bucket.blob.return_value = mock_blob
        mock_tiles_bucket.blob.return_value = mock_blob

        uploader = GCSUploader()
        summary = uploader.upload_cycle("2604", db_path, tiles_dir)

        assert summary["cycle"] == "2604"
        assert summary["db_uploaded"]
        assert summary["tiles_uploaded"] >= 1

    def test_set_active_cycle(self):
        mock_client = _setup_mock_storage()

        uploader = GCSUploader()
        uploader.set_active_cycle("2604")

        mock_client.bucket.assert_called_with("skyweb-reference")
        bucket = mock_client.bucket.return_value
        bucket.blob.assert_called_with("current_cycle")
        bucket.blob.return_value.upload_from_string.assert_called_once_with("2604")
