"""Cross-platform SpatiaLite extension loader.

Provides automatic detection and loading of SpatiaLite extension across
Windows, Linux, and macOS platforms with support for various installation
methods (Conda, OSGeo4W, Homebrew, system packages).

Copied from SkyPath project for reuse in SkyWeb.

Usage:
    from core.persistence.spatialite.spatialite_loader import enable_spatialite

    conn = sqlite3.connect(db_path)
    if enable_spatialite(conn):
        # SpatiaLite is ready to use
        conn.execute("SELECT spatialite_version()")

Environment Variables:
    SPATIALITE_LIBRARY_PATH: Override auto-detection with explicit path
                            to SpatiaLite library file
"""

import os
import sys
import sqlite3
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class SpatiaLiteLoader:
    """Cross-platform SpatiaLite extension loader with auto-detection."""

    def __init__(self):
        """Initialize the loader."""
        self._platform = sys.platform
        self._search_paths: List[Path] = []

    def enable_spatialite(self, conn: sqlite3.Connection) -> bool:
        """
        Enable SpatiaLite extension for the given database connection.

        Tries loading in the following order:
        1. SPATIALITE_LIBRARY_PATH environment variable (if set)
        2. Platform-specific paths based on common installation locations
        3. Generic library names as fallback

        Args:
            conn: SQLite database connection

        Returns:
            True if SpatiaLite was successfully loaded and initialized

        Raises:
            RuntimeError: If SpatiaLite cannot be loaded
        """
        try:
            conn.enable_load_extension(True)
        except Exception as e:
            raise RuntimeError(f"Cannot enable SQLite extensions: {e}")

        # Try loading with different strategies
        loaded = False

        # Strategy 1: Environment variable override
        env_path = os.environ.get("SPATIALITE_LIBRARY_PATH")
        if env_path:
            if self._try_load_from_path(conn, Path(env_path)):
                logger.info(f"Loaded SpatiaLite from SPATIALITE_LIBRARY_PATH: {env_path}")
                loaded = True

        # Strategy 2: Platform-specific paths
        if not loaded:
            search_paths = self._get_platform_search_paths()
            for path in search_paths:
                if path.exists():
                    if self._try_load_from_path(conn, path):
                        logger.info(f"Loaded SpatiaLite from: {path}")
                        loaded = True
                        break
                else:
                    logger.debug(f"Path does not exist: {path}")

        # Strategy 3: Generic library names (system-managed paths)
        if not loaded:
            generic_names = self._get_generic_library_names()
            for name in generic_names:
                if self._try_load_by_name(conn, name):
                    logger.info(f"Loaded SpatiaLite using library name: {name}")
                    loaded = True
                    break

        if not loaded:
            error_msg = self._generate_error_message()
            raise RuntimeError(error_msg)

        # Verify SpatiaLite is functional
        try:
            cursor = conn.execute("SELECT spatialite_version()")
            version = cursor.fetchone()
            if version:
                logger.info(f"SpatiaLite version: {version[0]}")
            return True
        except Exception as e:
            raise RuntimeError(f"SpatiaLite loaded but not functional: {e}")

    def _get_platform_search_paths(self) -> List[Path]:
        """Get platform-specific search paths for SpatiaLite library."""
        if self._platform == "win32":
            return self._get_windows_paths()
        elif self._platform == "linux":
            return self._get_linux_paths()
        elif self._platform == "darwin":
            return self._get_macos_paths()
        else:
            logger.warning(f"Unsupported platform: {self._platform}")
            return []

    def _get_windows_paths(self) -> List[Path]:
        """Get Windows-specific search paths."""
        paths = []

        # 1. Conda environment (highest priority for conda users)
        conda_prefix = os.environ.get("CONDA_PREFIX")
        if conda_prefix:
            conda_paths = [
                Path(conda_prefix) / "Library" / "bin" / "mod_spatialite.dll",
                Path(conda_prefix) / "Library" / "lib" / "mod_spatialite.dll",
                Path(conda_prefix) / "DLLs" / "mod_spatialite.dll",
            ]
            paths.extend(conda_paths)

            # Also add conda bin to PATH if not already there
            conda_bin = Path(conda_prefix) / "Library" / "bin"
            if conda_bin.exists():
                current_path = os.environ.get("PATH", "")
                conda_bin_str = str(conda_bin)
                if conda_bin_str not in current_path:
                    os.environ["PATH"] = conda_bin_str + ";" + current_path
                    logger.debug(f"Added to PATH: {conda_bin_str}")

        # 2. OSGeo4W installation
        osgeo_roots = [
            Path("C:/OSGeo4W64"),
            Path("C:/OSGeo4W"),
        ]
        for root in osgeo_roots:
            if root.exists():
                paths.extend([
                    root / "bin" / "mod_spatialite.dll",
                    root / "lib" / "mod_spatialite.dll",
                ])

        # 3. QGIS installation (often includes SpatiaLite)
        program_files = [
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")),
            Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")),
        ]
        for pf in program_files:
            qgis_paths = list(pf.glob("QGIS*/bin/mod_spatialite.dll"))
            paths.extend(qgis_paths)

        return paths

    def _get_linux_paths(self) -> List[Path]:
        """Get Linux-specific search paths."""
        paths = []

        # Common library paths across distributions
        lib_dirs = [
            "/usr/lib",
            "/usr/local/lib",
            "/usr/lib/x86_64-linux-gnu",  # Debian/Ubuntu
            "/usr/lib64",                  # RedHat/Fedora/CentOS
            "/usr/lib/aarch64-linux-gnu",  # ARM64
        ]

        lib_names = [
            "mod_spatialite.so",
            "libspatialite.so",
            "mod_spatialite.so.7",
            "libspatialite.so.7",
        ]

        for lib_dir in lib_dirs:
            for lib_name in lib_names:
                path = Path(lib_dir) / lib_name
                paths.append(path)

        # Conda environment on Linux
        conda_prefix = os.environ.get("CONDA_PREFIX")
        if conda_prefix:
            conda_paths = [
                Path(conda_prefix) / "lib" / "mod_spatialite.so",
                Path(conda_prefix) / "lib" / "libspatialite.so",
            ]
            # Prioritize conda paths for conda users
            paths = conda_paths + paths

        return paths

    def _get_macos_paths(self) -> List[Path]:
        """Get macOS-specific search paths."""
        paths = []

        # Homebrew paths (Intel and Apple Silicon)
        homebrew_prefixes = [
            "/opt/homebrew",      # Apple Silicon
            "/usr/local",         # Intel
        ]

        lib_names = [
            "mod_spatialite.dylib",
            "libspatialite.dylib",
        ]

        for prefix in homebrew_prefixes:
            for lib_name in lib_names:
                paths.append(Path(prefix) / "lib" / lib_name)

        # Conda environment on macOS
        conda_prefix = os.environ.get("CONDA_PREFIX")
        if conda_prefix:
            conda_paths = [
                Path(conda_prefix) / "lib" / "mod_spatialite.dylib",
                Path(conda_prefix) / "lib" / "libspatialite.dylib",
            ]
            # Prioritize conda paths
            paths = conda_paths + paths

        # MacPorts (less common but still used)
        paths.append(Path("/opt/local/lib/mod_spatialite.dylib"))

        return paths

    def _get_generic_library_names(self) -> List[str]:
        """Get generic library names to try (relies on system library paths)."""
        if self._platform == "win32":
            return ["mod_spatialite", "spatialite"]
        elif self._platform == "darwin":
            return ["mod_spatialite", "spatialite", "libspatialite"]
        else:  # Linux and others
            return ["mod_spatialite", "spatialite", "libspatialite"]

    def _try_load_from_path(self, conn: sqlite3.Connection, path: Path) -> bool:
        """Try to load SpatiaLite from a specific path."""
        try:
            conn.load_extension(str(path))
            return True
        except Exception as e:
            logger.debug(f"Failed to load from {path}: {e}")
            return False

    def _try_load_by_name(self, conn: sqlite3.Connection, name: str) -> bool:
        """Try to load SpatiaLite by library name."""
        try:
            conn.load_extension(name)
            return True
        except Exception as e:
            logger.debug(f"Failed to load by name '{name}': {e}")
            return False

    def _generate_error_message(self) -> str:
        """Generate helpful error message with installation instructions."""
        msg = "Failed to load SpatiaLite extension.\n\n"

        if self._platform == "win32":
            msg += "Windows Installation Options:\n"
            msg += "  1. Conda: conda install -c conda-forge libspatialite\n"
            msg += "  2. OSGeo4W: Download from https://trac.osgeo.org/osgeo4w/\n"
            msg += "  3. Set SPATIALITE_LIBRARY_PATH to mod_spatialite.dll location\n"
        elif self._platform == "linux":
            msg += "Linux Installation Options:\n"
            msg += "  Ubuntu/Debian: sudo apt-get install libspatialite7\n"
            msg += "  Fedora/RHEL: sudo dnf install libspatialite\n"
            msg += "  Conda: conda install -c conda-forge libspatialite\n"
            msg += "  Set SPATIALITE_LIBRARY_PATH to library location\n"
        elif self._platform == "darwin":
            msg += "macOS Installation Options:\n"
            msg += "  Homebrew: brew install libspatialite\n"
            msg += "  Conda: conda install -c conda-forge libspatialite\n"
            msg += "  Set SPATIALITE_LIBRARY_PATH to library location\n"

        return msg


def enable_spatialite(conn: sqlite3.Connection) -> bool:
    """
    Convenience function to enable SpatiaLite on a connection.

    Args:
        conn: SQLite database connection

    Returns:
        True if SpatiaLite was successfully enabled

    Raises:
        RuntimeError: If SpatiaLite cannot be loaded
    """
    loader = SpatiaLiteLoader()
    return loader.enable_spatialite(conn)
