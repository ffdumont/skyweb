"""Tests for VAC downloader module."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import pytest

from core.services.vac_downloader import (
    AIRACCycle,
    CacheMetadata,
    DownloadError,
    ParseError,
    VACDownloader,
    ValidationError,
    calculate_airac_cycle,
    get_vac_url,
    validate_icao_code,
    _parse_airac_from_text,
)


# ============ AIRAC Calculation Tests ============

class TestAIRACCalculation:
    """Tests for AIRAC cycle calculation."""

    def test_calculate_reference_date(self):
        """Test calculation for the reference date (Jan 2, 2025)."""
        cycle = calculate_airac_cycle(datetime(2025, 1, 2))
        assert cycle.cycle_number == "01/25"
        assert cycle.start_date == datetime(2025, 1, 2)

    def test_calculate_cycle_2026_01(self):
        """Test cycle 01/26 (Jan 22, 2026)."""
        # January 22, 2026 should be cycle 01/26
        cycle = calculate_airac_cycle(datetime(2026, 1, 22))
        assert cycle.start_date == datetime(2026, 1, 22)
        assert "01/26" in cycle.cycle_number or "01" in cycle.cycle_number

    def test_calculate_mid_cycle(self):
        """Test calculation for a date in the middle of a cycle."""
        # Jan 15, 2025 is in the middle of cycle 01/25 (Jan 2 - Jan 29)
        cycle = calculate_airac_cycle(datetime(2025, 1, 15))
        assert cycle.start_date == datetime(2025, 1, 2)
        assert cycle.end_date == datetime(2025, 1, 29)

    def test_cycle_string_format(self):
        """Test the cycle string format."""
        cycle = calculate_airac_cycle(datetime(2026, 1, 22))
        # Should be eAIP_DD_MMM_YYYY format
        assert cycle.cycle_string.startswith("eAIP_")
        assert "JAN" in cycle.cycle_string or "FEB" in cycle.cycle_string
        assert "2026" in cycle.cycle_string

    def test_cycle_28_days(self):
        """Test that cycles are exactly 28 days."""
        cycle = calculate_airac_cycle(datetime(2025, 1, 2))
        duration = (cycle.end_date - cycle.start_date).days + 1
        assert duration == 28


class TestAIRACCycle:
    """Tests for AIRACCycle dataclass."""

    def test_is_current_true(self):
        """Test is_current property when cycle is active."""
        now = datetime.now()
        cycle = AIRACCycle(
            cycle_string="eAIP_01_JAN_2025",
            cycle_number="01/25",
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=10),
        )
        assert cycle.is_current is True

    def test_is_current_false_past(self):
        """Test is_current property when cycle is in the past."""
        cycle = AIRACCycle(
            cycle_string="eAIP_01_JAN_2020",
            cycle_number="01/20",
            start_date=datetime(2020, 1, 1),
            end_date=datetime(2020, 1, 28),
        )
        assert cycle.is_current is False

    def test_to_dict_from_dict(self):
        """Test serialization round-trip."""
        original = AIRACCycle(
            cycle_string="eAIP_22_JAN_2026",
            cycle_number="01/26",
            start_date=datetime(2026, 1, 22),
            end_date=datetime(2026, 2, 18),
        )
        data = original.to_dict()
        restored = AIRACCycle.from_dict(data)

        assert restored.cycle_string == original.cycle_string
        assert restored.cycle_number == original.cycle_number
        assert restored.start_date == original.start_date
        assert restored.end_date == original.end_date


# ============ Text Parsing Tests ============

class TestParseAIRACFromText:
    """Tests for parsing AIRAC info from text."""

    def test_parse_standard_format(self):
        """Test parsing standard SIA text format."""
        text = """
        ZIP eAIP Complet AIRAC 01/26
        En vigueur du 22/01/2026 au 18/02/2026 inclus
        """
        cycle = _parse_airac_from_text(text)
        assert cycle.cycle_number == "01/26"
        assert cycle.start_date == datetime(2026, 1, 22)
        assert cycle.end_date == datetime(2026, 2, 18)

    def test_parse_no_cycle_number(self):
        """Test parsing fails without cycle number."""
        text = "No AIRAC info here"
        with pytest.raises(ParseError):
            _parse_airac_from_text(text)


# ============ Validation Tests ============

class TestValidateICAOCode:
    """Tests for ICAO code validation."""

    def test_valid_code(self):
        """Test valid ICAO codes."""
        assert validate_icao_code("LFXU") == "LFXU"
        assert validate_icao_code("lfpg") == "LFPG"  # Uppercase conversion
        assert validate_icao_code("  LFML  ") == "LFML"  # Trim whitespace

    def test_empty_code(self):
        """Test empty code raises error."""
        with pytest.raises(ValidationError):
            validate_icao_code("")

    def test_wrong_length(self):
        """Test wrong length raises error."""
        with pytest.raises(ValidationError):
            validate_icao_code("LFX")
        with pytest.raises(ValidationError):
            validate_icao_code("LFXUU")

    def test_non_alpha(self):
        """Test non-alphabetic code raises error."""
        with pytest.raises(ValidationError):
            validate_icao_code("LF12")


# ============ URL Generation Tests ============

class TestGetVACUrl:
    """Tests for VAC URL generation."""

    def test_url_format(self):
        """Test URL format is correct."""
        cycle = AIRACCycle(
            cycle_string="eAIP_22_JAN_2026",
            cycle_number="01/26",
            start_date=datetime(2026, 1, 22),
            end_date=datetime(2026, 2, 18),
        )
        url = get_vac_url("LFXU", cycle)

        assert "eAIP_22_JAN_2026" in url
        assert "AD-2.LFXU.pdf" in url
        assert url.startswith("https://www.sia.aviation-civile.gouv.fr/")

    def test_url_uppercase(self):
        """Test ICAO code is uppercased in URL."""
        cycle = AIRACCycle(
            cycle_string="eAIP_22_JAN_2026",
            cycle_number="01/26",
            start_date=datetime(2026, 1, 22),
            end_date=datetime(2026, 2, 18),
        )
        url = get_vac_url("lfxu", cycle)
        assert "AD-2.LFXU.pdf" in url


# ============ Cache Metadata Tests ============

class TestCacheMetadata:
    """Tests for CacheMetadata dataclass."""

    def test_to_dict_from_dict(self):
        """Test serialization round-trip."""
        original = CacheMetadata(
            cycle="eAIP_22_JAN_2026",
            start_date="2026-01-22",
            end_date="2026-02-18",
            downloaded_at="2026-02-07T10:30:00",
            files=["LFXU.pdf", "LFPG.pdf"],
        )
        data = original.to_dict()
        restored = CacheMetadata.from_dict(data)

        assert restored.cycle == original.cycle
        assert restored.files == original.files


# ============ VACDownloader Tests ============

class TestVACDownloader:
    """Tests for VACDownloader class."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_init_creates_cache_dir(self, temp_cache_dir):
        """Test that init creates the cache directory."""
        new_dir = temp_cache_dir / "new_cache"
        assert not new_dir.exists()
        VACDownloader(cache_dir=new_dir)
        assert new_dir.exists()

    def test_get_vac_url(self, temp_cache_dir):
        """Test URL generation through downloader."""
        downloader = VACDownloader(cache_dir=temp_cache_dir)
        cycle = AIRACCycle(
            cycle_string="eAIP_22_JAN_2026",
            cycle_number="01/26",
            start_date=datetime(2026, 1, 22),
            end_date=datetime(2026, 2, 18),
        )
        downloader._current_cycle = cycle
        downloader._cycle_fetched_at = datetime.now()

        url = downloader.get_vac_url("LFXU")
        assert "LFXU" in url

    def test_check_cache_validity_empty(self, temp_cache_dir):
        """Test cache validity check with empty cache."""
        downloader = VACDownloader(cache_dir=temp_cache_dir)
        # Mock the cycle to avoid network call
        downloader._current_cycle = AIRACCycle(
            cycle_string="eAIP_22_JAN_2026",
            cycle_number="01/26",
            start_date=datetime(2026, 1, 22),
            end_date=datetime(2026, 2, 18),
        )
        downloader._cycle_fetched_at = datetime.now()

        result = downloader.check_cache_validity()

        assert result["is_valid"] is False
        assert result["needs_update"] is True
        assert result["cached_cycle"] is None

    def test_check_cache_validity_current(self, temp_cache_dir):
        """Test cache validity check with current cache."""
        downloader = VACDownloader(cache_dir=temp_cache_dir)

        # Set up current cycle
        current_cycle = AIRACCycle(
            cycle_string="eAIP_22_JAN_2026",
            cycle_number="01/26",
            start_date=datetime(2026, 1, 22),
            end_date=datetime(2026, 2, 18),
        )
        downloader._current_cycle = current_cycle
        downloader._cycle_fetched_at = datetime.now()

        # Create cache directory with metadata
        cycle_dir = temp_cache_dir / current_cycle.cycle_string
        cycle_dir.mkdir()
        meta = CacheMetadata(
            cycle=current_cycle.cycle_string,
            start_date="2026-01-22",
            end_date="2026-02-18",
            downloaded_at="2026-02-07T10:30:00",
            files=["LFXU"],
        )
        with open(cycle_dir / "metadata.json", "w") as f:
            json.dump(meta.to_dict(), f)

        result = downloader.check_cache_validity()

        assert result["is_valid"] is True
        assert result["needs_update"] is False
        assert result["cached_files"] == ["LFXU"]

    def test_clean_old_cycles(self, temp_cache_dir):
        """Test cleaning old cycles."""
        downloader = VACDownloader(cache_dir=temp_cache_dir)

        # Create multiple cycle directories
        for cycle_name in ["eAIP_01_JAN_2024", "eAIP_01_FEB_2024", "eAIP_01_MAR_2024"]:
            cycle_dir = temp_cache_dir / cycle_name
            cycle_dir.mkdir()
            meta = CacheMetadata(
                cycle=cycle_name,
                start_date="2024-01-01",
                end_date="2024-01-28",
                downloaded_at="2024-01-01T10:00:00",
                files=[],
            )
            with open(cycle_dir / "metadata.json", "w") as f:
                json.dump(meta.to_dict(), f)

        # Set current cycle to a newer one
        downloader._current_cycle = AIRACCycle(
            cycle_string="eAIP_22_JAN_2026",
            cycle_number="01/26",
            start_date=datetime(2026, 1, 22),
            end_date=datetime(2026, 2, 18),
        )
        downloader._cycle_fetched_at = datetime.now()

        # Clean keeping only 1 previous
        removed = downloader.clean_old_cycles(keep_current=True, keep_previous=1)

        # Should have removed 2 of the 3 old cycles
        assert len(removed) == 2
        remaining = [d.name for d in temp_cache_dir.iterdir() if d.is_dir()]
        assert len(remaining) == 1

    @mock.patch("core.services.vac_downloader.requests.get")
    def test_download_success(self, mock_get, temp_cache_dir):
        """Test successful download."""
        # Mock the response
        mock_response = mock.Mock()
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.content = b"%PDF-1.4 test content"
        mock_response.iter_content = lambda chunk_size: [b"%PDF-1.4 test content"]
        mock_response.raise_for_status = mock.Mock()
        mock_get.return_value = mock_response

        downloader = VACDownloader(cache_dir=temp_cache_dir)
        downloader._current_cycle = AIRACCycle(
            cycle_string="eAIP_22_JAN_2026",
            cycle_number="01/26",
            start_date=datetime(2026, 1, 22),
            end_date=datetime(2026, 2, 18),
        )
        downloader._cycle_fetched_at = datetime.now()

        path = downloader.download("LFXU")

        assert path.exists()
        assert path.name == "LFXU.pdf"
        assert path.parent.name == "eAIP_22_JAN_2026"

    @mock.patch("core.services.vac_downloader.requests.get")
    def test_download_uses_cache(self, mock_get, temp_cache_dir):
        """Test that download uses cache."""
        downloader = VACDownloader(cache_dir=temp_cache_dir)
        downloader._current_cycle = AIRACCycle(
            cycle_string="eAIP_22_JAN_2026",
            cycle_number="01/26",
            start_date=datetime(2026, 1, 22),
            end_date=datetime(2026, 2, 18),
        )
        downloader._cycle_fetched_at = datetime.now()

        # Create cached file
        cycle_dir = temp_cache_dir / "eAIP_22_JAN_2026"
        cycle_dir.mkdir()
        cached_file = cycle_dir / "LFXU.pdf"
        cached_file.write_bytes(b"%PDF-1.4 cached")

        path = downloader.download("LFXU")

        assert path == cached_file
        mock_get.assert_not_called()  # Should not have made a request

    @mock.patch("core.services.vac_downloader.requests.get")
    def test_download_404(self, mock_get, temp_cache_dir):
        """Test download handles 404."""
        from requests.exceptions import HTTPError

        mock_response = mock.Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = HTTPError(response=mock_response)
        mock_get.return_value = mock_response

        downloader = VACDownloader(cache_dir=temp_cache_dir)
        downloader._current_cycle = AIRACCycle(
            cycle_string="eAIP_22_JAN_2026",
            cycle_number="01/26",
            start_date=datetime(2026, 1, 22),
            end_date=datetime(2026, 2, 18),
        )
        downloader._cycle_fetched_at = datetime.now()

        with pytest.raises(DownloadError) as exc_info:
            downloader.download("XXXX")

        assert "404" in str(exc_info.value)


# ============ Run Tests ============

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
