"""FastAPI application factory."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.api.routes import (
    aerodromes,
    aircraft,
    airspaces,
    community,
    flights,
    routes,
    waypoints,
    weather,
)
from core.persistence.spatialite.db_manager import SpatiaLiteManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize SpatiaLite manager on startup."""
    import logging
    logger = logging.getLogger(__name__)

    manager = SpatiaLiteManager()
    local_db = os.environ.get("SPATIALITE_DB_PATH")
    if local_db:
        try:
            manager.use_local(Path(local_db))
            logger.info("Loaded SpatiaLite DB: %s", local_db)
        except FileNotFoundError:
            logger.warning("SPATIALITE_DB_PATH file not found: %s", local_db)
    else:
        logger.info("No SPATIALITE_DB_PATH — airspace/aerodrome endpoints return empty results")

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
app.include_router(flights.router, prefix="/api")
app.include_router(routes.router, prefix="/api")
app.include_router(aerodromes.router, prefix="/api")
app.include_router(airspaces.router, prefix="/api")
app.include_router(weather.router, prefix="/api")
app.include_router(community.router, prefix="/api")


@app.get("/api/health")
async def health():
    cycle = app.state.spatialite_manager.current_cycle
    return {"status": "ok", "airac_cycle": cycle}
