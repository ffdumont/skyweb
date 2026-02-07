"""VAC (Visual Approach Chart) downloader from French SIA.

Automatically fetches the current AIRAC cycle and downloads VAC PDFs
for French aerodromes from the SIA eAIP portal.

Usage:
    from core.services.vac_downloader import VACDownloader

    downloader = VACDownloader()
    vac_path = downloader.download("LFXU")
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Constants
SIA_EAIP_PAGE = "https://www.sia.aviation-civile.gouv.fr/produits-numeriques-en-libre-disposition/eaip.html"
VAC_URL_TEMPLATE = "https://www.sia.aviation-civile.gouv.fr/media/dvd/{cycle}/Atlas-VAC/PDF_AIPparSSection/VAC/AD/AD-2.{icao}.pdf"
REQUEST_TIMEOUT = 15
DEFAULT_USER_AGENT = "SkyWeb-VACDownloader/1.0"

# AIRAC reference point: December 26, 2024 aligns with cycle 01/26 starting Jan 22, 2026
AIRAC_REFERENCE_DATE = datetime(2024, 12, 26)
AIRAC_CYCLE_DAYS = 28

# Month abbreviations in French (as used by SIA)
MONTH_ABBR = {
    1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
    7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC"
}

MONTH_ABBR_REVERSE = {v: k for k, v in MONTH_ABBR.items()}


# ============ Exceptions ============

class VACDownloaderError(Exception):
    """Base exception for VAC downloader errors."""
    pass


class NetworkError(VACDownloaderError):
    """Network-related errors (timeout, connection refused, etc.)."""
    pass


class ParseError(VACDownloaderError):
    """Failed to parse SIA website HTML."""
    pass


class DownloadError(VACDownloaderError):
    """Failed to download VAC PDF (404, 403, etc.)."""
    pass


class ValidationError(VACDownloaderError):
    """Invalid ICAO code or parameter."""
    pass


# ============ Data Classes ============

@dataclass
class AIRACCycle:
    """Represents an AIRAC cycle with its validity dates."""

    cycle_string: str      # "eAIP_22_JAN_2026"
    cycle_number: str      # "01/26"
    start_date: datetime
    end_date: datetime

    @property
    def is_current(self) -> bool:
        """Check if this cycle is currently in effect."""
        now = datetime.now()
        return self.start_date <= now <= self.end_date

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "cycle_string": self.cycle_string,
            "cycle_number": self.cycle_number,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AIRACCycle:
        """Create from dictionary."""
        return cls(
            cycle_string=data["cycle_string"],
            cycle_number=data["cycle_number"],
            start_date=datetime.fromisoformat(data["start_date"]),
            end_date=datetime.fromisoformat(data["end_date"]),
        )

    def __str__(self) -> str:
        return f"AIRAC {self.cycle_number} ({self.start_date.strftime('%d/%m/%Y')} - {self.end_date.strftime('%d/%m/%Y')})"


@dataclass
class CacheMetadata:
    """Metadata for a cached AIRAC cycle."""

    cycle: str
    start_date: str
    end_date: str
    downloaded_at: str
    files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "downloaded_at": self.downloaded_at,
            "files": self.files,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CacheMetadata:
        return cls(
            cycle=data["cycle"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            downloaded_at=data["downloaded_at"],
            files=data.get("files", []),
        )


# ============ AIRAC Calculation ============

def calculate_airac_cycle(reference_date: datetime | None = None) -> AIRACCycle:
    """Calculate the AIRAC cycle for a given date using the 28-day pattern.

    Args:
        reference_date: Date to calculate cycle for (default: now)

    Returns:
        AIRACCycle object for the cycle in effect on that date
    """
    if reference_date is None:
        reference_date = datetime.now()

    # Calculate days since reference point
    days_since_ref = (reference_date - AIRAC_REFERENCE_DATE).days

    # Find which cycle we're in
    cycles_since_ref = days_since_ref // AIRAC_CYCLE_DAYS

    # Calculate cycle start date
    cycle_start = AIRAC_REFERENCE_DATE + timedelta(days=cycles_since_ref * AIRAC_CYCLE_DAYS)
    cycle_end = cycle_start + timedelta(days=AIRAC_CYCLE_DAYS - 1)

    # Calculate cycle number (1-13 per year)
    # Find which year this cycle belongs to
    year = cycle_start.year

    # Find the first cycle of this year
    year_start = datetime(year, 1, 1)
    if year_start < AIRAC_REFERENCE_DATE:
        first_cycle_of_year = AIRAC_REFERENCE_DATE
    else:
        # Find the first cycle that starts in this year
        days_from_ref = (year_start - AIRAC_REFERENCE_DATE).days
        cycles_before = days_from_ref // AIRAC_CYCLE_DAYS
        first_cycle_of_year = AIRAC_REFERENCE_DATE + timedelta(days=cycles_before * AIRAC_CYCLE_DAYS)
        if first_cycle_of_year < year_start:
            first_cycle_of_year += timedelta(days=AIRAC_CYCLE_DAYS)

    # Calculate cycle number within the year
    cycles_from_year_start = (cycle_start - first_cycle_of_year).days // AIRAC_CYCLE_DAYS + 1

    # Handle edge case where cycle started in previous year
    if cycles_from_year_start <= 0:
        # This cycle started in the previous year
        year = cycle_start.year
        # Recalculate from that year
        prev_year_start = datetime(year, 1, 1)
        days_from_ref = (prev_year_start - AIRAC_REFERENCE_DATE).days
        cycles_before = days_from_ref // AIRAC_CYCLE_DAYS
        first_cycle_of_year = AIRAC_REFERENCE_DATE + timedelta(days=cycles_before * AIRAC_CYCLE_DAYS)
        if first_cycle_of_year < prev_year_start:
            first_cycle_of_year += timedelta(days=AIRAC_CYCLE_DAYS)
        cycles_from_year_start = (cycle_start - first_cycle_of_year).days // AIRAC_CYCLE_DAYS + 1

    cycle_number = f"{cycles_from_year_start:02d}/{str(year)[2:]}"

    # Build cycle string: eAIP_DD_MMM_YYYY
    day = cycle_start.day
    month = MONTH_ABBR[cycle_start.month]
    cycle_string = f"eAIP_{day:02d}_{month}_{cycle_start.year}"

    return AIRACCycle(
        cycle_string=cycle_string,
        cycle_number=cycle_number,
        start_date=cycle_start,
        end_date=cycle_end,
    )


def get_current_airac_cycle() -> AIRACCycle:
    """Fetch the current AIRAC cycle from the SIA website.

    Falls back to calculation if scraping fails.

    Returns:
        AIRACCycle object for the current cycle
    """
    try:
        return _scrape_airac_cycle()
    except (NetworkError, ParseError) as e:
        logger.warning(f"Failed to scrape AIRAC cycle from SIA: {e}. Using calculated fallback.")
        return calculate_airac_cycle()


def _scrape_airac_cycle() -> AIRACCycle:
    """Scrape the current AIRAC cycle from the SIA eAIP page.

    Raises:
        NetworkError: If request fails
        ParseError: If HTML cannot be parsed
    """
    try:
        response = requests.get(
            SIA_EAIP_PAGE,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": DEFAULT_USER_AGENT},
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise NetworkError(f"Timeout fetching {SIA_EAIP_PAGE}")
    except requests.exceptions.RequestException as e:
        raise NetworkError(f"Failed to fetch SIA page: {e}")

    try:
        soup = BeautifulSoup(response.text, "html.parser")

        # Look for the current cycle information
        # Pattern: "ZIP eAIP Complet AIRAC 01/26" with "En vigueur du 22/01/2026 au 18/02/2026 inclus"

        # Find all product cards/sections
        products = soup.find_all(["div", "article", "section"], class_=re.compile(r"product|card|item", re.I))

        if not products:
            # Try to find by text content
            text = soup.get_text()
            return _parse_airac_from_text(text)

        for product in products:
            text = product.get_text()
            if "En vigueur" in text and "AIRAC" in text:
                return _parse_airac_from_text(text)

        # If no products found, try the whole page text
        return _parse_airac_from_text(soup.get_text())

    except Exception as e:
        if isinstance(e, (NetworkError, ParseError)):
            raise
        raise ParseError(f"Failed to parse SIA page: {e}")


def _parse_airac_from_text(text: str) -> AIRACCycle:
    """Parse AIRAC cycle information from text content.

    Looks for patterns like:
    - "AIRAC 01/26"
    - "En vigueur du 22/01/2026 au 18/02/2026"
    """
    # Find cycle number
    cycle_match = re.search(r"AIRAC\s+(\d{2})/(\d{2})", text)
    if not cycle_match:
        raise ParseError("Could not find AIRAC cycle number in text")

    cycle_num = int(cycle_match.group(1))
    cycle_year = int(cycle_match.group(2))
    full_year = 2000 + cycle_year
    cycle_number = f"{cycle_num:02d}/{cycle_year:02d}"

    # Find validity dates
    validity_match = re.search(
        r"En vigueur du\s+(\d{1,2})/(\d{1,2})/(\d{4})\s+au\s+(\d{1,2})/(\d{1,2})/(\d{4})",
        text
    )

    if validity_match:
        start_day, start_month, start_year = int(validity_match.group(1)), int(validity_match.group(2)), int(validity_match.group(3))
        end_day, end_month, end_year = int(validity_match.group(4)), int(validity_match.group(5)), int(validity_match.group(6))
        start_date = datetime(start_year, start_month, start_day)
        end_date = datetime(end_year, end_month, end_day)
    else:
        # Fall back to calculation for this cycle
        logger.warning("Could not parse validity dates, calculating from cycle number")
        # Calculate start date from cycle number
        calculated = calculate_airac_cycle()
        start_date = calculated.start_date
        end_date = calculated.end_date

    # Build cycle string
    month = MONTH_ABBR[start_date.month]
    cycle_string = f"eAIP_{start_date.day:02d}_{month}_{start_date.year}"

    return AIRACCycle(
        cycle_string=cycle_string,
        cycle_number=cycle_number,
        start_date=start_date,
        end_date=end_date,
    )


# ============ URL Generation ============

def validate_icao_code(icao_code: str) -> str:
    """Validate and normalize an ICAO code.

    Args:
        icao_code: ICAO code to validate

    Returns:
        Normalized (uppercase) ICAO code

    Raises:
        ValidationError: If code is invalid
    """
    if not icao_code:
        raise ValidationError("ICAO code cannot be empty")

    icao = icao_code.strip().upper()

    if len(icao) != 4:
        raise ValidationError(f"ICAO code must be 4 characters, got '{icao}' ({len(icao)} chars)")

    if not icao.isalpha():
        raise ValidationError(f"ICAO code must contain only letters, got '{icao}'")

    return icao


def get_vac_url(icao_code: str, airac_cycle: AIRACCycle | None = None) -> str:
    """Generate the URL for a VAC PDF.

    Args:
        icao_code: ICAO code (4 letters)
        airac_cycle: AIRAC cycle to use (default: current)

    Returns:
        Full URL to the VAC PDF
    """
    icao = validate_icao_code(icao_code)

    if airac_cycle is None:
        airac_cycle = get_current_airac_cycle()

    return VAC_URL_TEMPLATE.format(
        cycle=airac_cycle.cycle_string,
        icao=icao,
    )


# ============ Main Downloader Class ============

class VACDownloader:
    """Downloads and caches VAC PDFs from the French SIA."""

    def __init__(
        self,
        cache_dir: str | Path = "./vac_cache",
        user_agent: str | None = None,
    ):
        """Initialize the VAC downloader.

        Args:
            cache_dir: Directory to store cached VAC PDFs
            user_agent: User-Agent header for HTTP requests
        """
        self.cache_dir = Path(cache_dir)
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self._current_cycle: AIRACCycle | None = None
        self._cycle_fetched_at: datetime | None = None

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_current_cycle(self, force_refresh: bool = False) -> AIRACCycle:
        """Get the current AIRAC cycle with in-memory caching.

        Args:
            force_refresh: Force fetching from SIA website

        Returns:
            Current AIRACCycle
        """
        # Refresh if forced, no cache, or cache is old (> 1 hour)
        should_refresh = (
            force_refresh
            or self._current_cycle is None
            or self._cycle_fetched_at is None
            or (datetime.now() - self._cycle_fetched_at) > timedelta(hours=1)
        )

        if should_refresh:
            self._current_cycle = get_current_airac_cycle()
            self._cycle_fetched_at = datetime.now()
            logger.info(f"Fetched current AIRAC cycle: {self._current_cycle}")

        return self._current_cycle

    def get_vac_url(self, icao_code: str, cycle: AIRACCycle | None = None) -> str:
        """Generate URL for a VAC PDF.

        Args:
            icao_code: ICAO code (4 letters)
            cycle: AIRAC cycle (default: current)

        Returns:
            Full URL to the VAC PDF
        """
        if cycle is None:
            cycle = self.get_current_cycle()
        return get_vac_url(icao_code, cycle)

    def _get_cycle_cache_dir(self, cycle: AIRACCycle) -> Path:
        """Get the cache directory for a specific cycle."""
        return self.cache_dir / cycle.cycle_string

    def _get_metadata_path(self, cycle: AIRACCycle) -> Path:
        """Get the metadata file path for a cycle."""
        return self._get_cycle_cache_dir(cycle) / "metadata.json"

    def _load_metadata(self, cycle: AIRACCycle) -> CacheMetadata | None:
        """Load metadata for a cycle if it exists."""
        meta_path = self._get_metadata_path(cycle)
        if not meta_path.exists():
            return None
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return CacheMetadata.from_dict(json.load(f))
        except Exception as e:
            logger.warning(f"Failed to load metadata: {e}")
            return None

    def _save_metadata(self, cycle: AIRACCycle, metadata: CacheMetadata):
        """Save metadata for a cycle."""
        meta_path = self._get_metadata_path(cycle)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)

    def download(
        self,
        icao_code: str,
        force_download: bool = False,
    ) -> Path:
        """Download a VAC PDF.

        Args:
            icao_code: ICAO code (4 letters)
            force_download: Force re-download even if cached

        Returns:
            Path to the downloaded PDF

        Raises:
            ValidationError: Invalid ICAO code
            DownloadError: Failed to download
        """
        icao = validate_icao_code(icao_code)
        cycle = self.get_current_cycle()

        cycle_dir = self._get_cycle_cache_dir(cycle)
        pdf_path = cycle_dir / f"{icao}.pdf"

        # Check cache
        if not force_download and pdf_path.exists():
            logger.debug(f"Using cached VAC for {icao}")
            return pdf_path

        # Download
        url = self.get_vac_url(icao, cycle)
        logger.info(f"Downloading VAC for {icao} from {url}")

        try:
            response = requests.get(
                url,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": self.user_agent},
                stream=True,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise DownloadError(f"Timeout downloading VAC for {icao}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise DownloadError(f"VAC not found for {icao} (404)")
            raise DownloadError(f"HTTP error downloading VAC for {icao}: {e}")
        except requests.exceptions.RequestException as e:
            raise DownloadError(f"Failed to download VAC for {icao}: {e}")

        # Verify it's a PDF
        content_type = response.headers.get("content-type", "")
        if "pdf" not in content_type.lower() and not response.content[:4] == b"%PDF":
            raise DownloadError(f"Response for {icao} is not a PDF (content-type: {content_type})")

        # Save to cache
        cycle_dir.mkdir(parents=True, exist_ok=True)
        with open(pdf_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Update metadata
        metadata = self._load_metadata(cycle)
        if metadata is None:
            metadata = CacheMetadata(
                cycle=cycle.cycle_string,
                start_date=cycle.start_date.strftime("%Y-%m-%d"),
                end_date=cycle.end_date.strftime("%Y-%m-%d"),
                downloaded_at=datetime.now().isoformat(),
                files=[],
            )
        if icao not in metadata.files:
            metadata.files.append(icao)
        metadata.downloaded_at = datetime.now().isoformat()
        self._save_metadata(cycle, metadata)

        logger.info(f"Downloaded VAC for {icao} to {pdf_path}")
        return pdf_path

    def download_multiple(
        self,
        icao_codes: list[str],
        max_workers: int = 5,
        delay_between: float = 0.5,
    ) -> dict[str, Path | str]:
        """Download multiple VAC PDFs in parallel.

        Args:
            icao_codes: List of ICAO codes
            max_workers: Number of parallel downloads
            delay_between: Delay between starting downloads (rate limiting)

        Returns:
            Dictionary mapping ICAO code to Path (success) or error string (failure)
        """
        results: dict[str, Path | str] = {}

        # Pre-validate all codes
        valid_codes = []
        for code in icao_codes:
            try:
                valid_codes.append(validate_icao_code(code))
            except ValidationError as e:
                results[code] = str(e)

        if not valid_codes:
            return results

        # Ensure cycle is cached before parallel downloads
        self.get_current_cycle()

        def download_one(icao: str) -> tuple[str, Path | str]:
            try:
                path = self.download(icao)
                return (icao, path)
            except Exception as e:
                return (icao, str(e))

        try:
            from tqdm import tqdm
            progress = tqdm(total=len(valid_codes), desc="Downloading VACs")
        except ImportError:
            progress = None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(download_one, code): code for code in valid_codes}

            for future in as_completed(futures):
                icao, result = future.result()
                results[icao] = result
                if progress:
                    progress.update(1)

        if progress:
            progress.close()

        return results

    def check_cache_validity(self) -> dict[str, Any]:
        """Check if the cache is still valid for the current cycle.

        Returns:
            Dictionary with validity information
        """
        current_cycle = self.get_current_cycle()

        # Find most recent cached cycle
        cached_cycles = []
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir() and subdir.name.startswith("eAIP_"):
                meta = self._load_metadata_from_dir(subdir)
                if meta:
                    cached_cycles.append((subdir.name, meta))

        if not cached_cycles:
            return {
                "is_valid": False,
                "cached_cycle": None,
                "current_cycle": current_cycle.cycle_string,
                "needs_update": True,
                "cached_files": [],
            }

        # Sort by cycle string (most recent first)
        cached_cycles.sort(key=lambda x: x[0], reverse=True)
        latest_cycle, latest_meta = cached_cycles[0]

        is_valid = latest_cycle == current_cycle.cycle_string

        return {
            "is_valid": is_valid,
            "cached_cycle": latest_cycle,
            "current_cycle": current_cycle.cycle_string,
            "needs_update": not is_valid,
            "cached_files": latest_meta.files if latest_meta else [],
        }

    def _load_metadata_from_dir(self, cycle_dir: Path) -> CacheMetadata | None:
        """Load metadata from a cycle directory."""
        meta_path = cycle_dir / "metadata.json"
        if not meta_path.exists():
            return None
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return CacheMetadata.from_dict(json.load(f))
        except Exception:
            return None

    def clean_old_cycles(
        self,
        keep_current: bool = True,
        keep_previous: int = 1,
    ) -> list[str]:
        """Remove old AIRAC cycles from the cache.

        Args:
            keep_current: Keep the current cycle
            keep_previous: Number of previous cycles to keep

        Returns:
            List of removed cycle names
        """
        current_cycle = self.get_current_cycle() if keep_current else None

        # List all cycle directories
        cycle_dirs = []
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir() and subdir.name.startswith("eAIP_"):
                cycle_dirs.append(subdir)

        # Sort by name (chronological order)
        cycle_dirs.sort(key=lambda x: x.name, reverse=True)

        # Determine which to keep
        to_keep = set()
        if current_cycle:
            to_keep.add(current_cycle.cycle_string)

        # Keep N most recent (excluding current if already kept)
        kept_count = 0
        for cycle_dir in cycle_dirs:
            if cycle_dir.name in to_keep:
                continue
            if kept_count < keep_previous:
                to_keep.add(cycle_dir.name)
                kept_count += 1

        # Remove the rest
        removed = []
        for cycle_dir in cycle_dirs:
            if cycle_dir.name not in to_keep:
                logger.info(f"Removing old cycle cache: {cycle_dir.name}")
                shutil.rmtree(cycle_dir)
                removed.append(cycle_dir.name)

        return removed


# ============ Convenience Functions ============

def download_vac(
    icao_code: str,
    cache_dir: str | Path = "./vac_cache",
    force_download: bool = False,
) -> Path:
    """Download a VAC PDF (convenience function).

    Args:
        icao_code: ICAO code (4 letters)
        cache_dir: Cache directory
        force_download: Force re-download

    Returns:
        Path to the downloaded PDF
    """
    downloader = VACDownloader(cache_dir=cache_dir)
    return downloader.download(icao_code, force_download=force_download)


def download_multiple_vac(
    icao_codes: list[str],
    cache_dir: str | Path = "./vac_cache",
    max_workers: int = 5,
) -> dict[str, Path | str]:
    """Download multiple VAC PDFs (convenience function).

    Args:
        icao_codes: List of ICAO codes
        cache_dir: Cache directory
        max_workers: Number of parallel downloads

    Returns:
        Dictionary mapping ICAO code to Path or error string
    """
    downloader = VACDownloader(cache_dir=cache_dir)
    return downloader.download_multiple(icao_codes, max_workers=max_workers)


def check_vac_validity(cache_dir: str | Path = "./vac_cache") -> dict[str, Any]:
    """Check VAC cache validity (convenience function).

    Args:
        cache_dir: Cache directory

    Returns:
        Validity information dictionary
    """
    downloader = VACDownloader(cache_dir=cache_dir)
    return downloader.check_cache_validity()


def clean_old_cycles(
    cache_dir: str | Path = "./vac_cache",
    keep_current: bool = True,
    keep_previous: int = 1,
) -> list[str]:
    """Clean old AIRAC cycles from cache (convenience function).

    Args:
        cache_dir: Cache directory
        keep_current: Keep the current cycle
        keep_previous: Number of previous cycles to keep

    Returns:
        List of removed cycle names
    """
    downloader = VACDownloader(cache_dir=cache_dir)
    return downloader.clean_old_cycles(keep_current=keep_current, keep_previous=keep_previous)
