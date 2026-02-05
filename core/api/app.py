"""FastAPI application factory."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

# Load .env file from project root (must be before other imports)
load_dotenv()
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from core.api.routes import (  # noqa: E402
    aerodromes,
    aircraft,
    airspaces,
    community,
    dossiers,
    routes,
    waypoints,
    weather,
)
from core.persistence.spatialite.db_manager import SpatiaLiteManager  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Firebase Admin and SpatiaLite manager on startup."""
    import logging
    logger = logging.getLogger(__name__)

    # Initialize Firebase Admin SDK (uses ADC on Cloud Run)
    try:
        import firebase_admin
        firebase_admin.initialize_app()
        logger.info("Firebase Admin SDK initialized")
    except ValueError:
        # Already initialized
        logger.info("Firebase Admin SDK already initialized")
    except Exception as exc:
        logger.warning("Firebase Admin SDK init failed: %s", exc)

    manager = SpatiaLiteManager()
    local_db = os.environ.get("SPATIALITE_DB_PATH")
    if local_db:
        try:
            manager.use_local(Path(local_db))
            logger.info("Loaded SpatiaLite DB from local path: %s", local_db)
        except FileNotFoundError:
            logger.warning("SPATIALITE_DB_PATH file not found: %s", local_db)
    else:
        # Try to download from GCS (Cloud Run environment)
        try:
            db_path = manager.download()
            logger.info("Downloaded SpatiaLite DB from GCS: %s (cycle %s)", db_path, manager.current_cycle)
        except Exception as exc:
            logger.warning("Failed to download SpatiaLite DB from GCS: %s", exc)

    app.state.spatialite_manager = manager
    yield


app = FastAPI(
    title="SkyWeb API",
    description="VFR flight preparation automation",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(waypoints.router, prefix="/api")
app.include_router(aircraft.router, prefix="/api")
app.include_router(dossiers.router, prefix="/api")
app.include_router(routes.router, prefix="/api")
app.include_router(aerodromes.router, prefix="/api")
app.include_router(airspaces.router, prefix="/api")
app.include_router(weather.router, prefix="/api")
app.include_router(community.router, prefix="/api")


@app.get("/api/health")
async def health():
    manager = app.state.spatialite_manager
    result = {
        "status": "ok",
        "airac_cycle": manager.current_cycle,
        "spatialite_ready": manager.is_ready,
    }

    # Verify SpatiaLite is functional
    if manager.is_ready:
        try:
            conn = manager.get_connection()
            try:
                # Check SpatiaLite version
                row = conn.execute("SELECT spatialite_version()").fetchone()
                result["spatialite_version"] = row[0] if row else None

                # Check if the main view exists and has data
                row = conn.execute(
                    "SELECT COUNT(*) FROM airspace_spatial_indexed"
                ).fetchone()
                result["airspace_count"] = row[0] if row else 0
            finally:
                conn.close()
        except Exception as exc:
            result["spatialite_error"] = str(exc)

    return result
