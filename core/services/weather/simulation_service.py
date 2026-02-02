"""Weather simulation orchestrator."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from core.contracts.enums import ForecastModel
from core.contracts.weather import (
    ModelPoint,
    ModelResult,
    WaypointContext,
    WeatherSimulation,
)
from core.persistence.repositories.route_repo import RouteRepository
from core.persistence.repositories.waypoint_repo import WaypointRepository
from core.services.weather.metar_client import MetarClient
from core.services.weather.model_selector import select_models
from core.services.weather.openmeteo_client import OpenMeteoClient
from core.services.weather.vfr_index import compute_vfr_index

logger = logging.getLogger(__name__)


class SimulationService:
    """Builds a multi-model WeatherSimulation for a route."""

    def __init__(
        self,
        openmeteo: OpenMeteoClient,
        metar: MetarClient,
        route_repo: RouteRepository,
        waypoint_repo: WaypointRepository,
    ):
        self._openmeteo = openmeteo
        self._metar = metar
        self._route_repo = route_repo
        self._wp_repo = waypoint_repo

    async def simulate(
        self,
        user_id: str,
        route_id: str,
        navigation_datetime: datetime,
    ) -> WeatherSimulation:
        """Full simulation pipeline.

        1. Load route + resolve waypoint coordinates
        2. Build WaypointContext list with estimated times
        3. Select models based on horizon
        4. Fetch forecasts in parallel (per model, per waypoint)
        5. Compute VFR index for each point
        6. Persist and return WeatherSimulation
        """
        now = datetime.now(tz=timezone.utc)

        # 1. Load route and resolve waypoints
        route = await self._route_repo.get(user_id, route_id)
        if route is None:
            raise ValueError(f"Route {route_id} not found")

        wp_ids = [ref.waypoint_id for ref in route.waypoints]
        wp_map = await self._wp_repo.get_by_ids(user_id, wp_ids)

        # 2. Build WaypointContext list
        sorted_refs = sorted(route.waypoints, key=lambda r: r.sequence_order)
        contexts: list[WaypointContext] = []
        for ref in sorted_refs:
            wp = wp_map.get(ref.waypoint_id)
            if wp is None:
                continue
            contexts.append(WaypointContext(
                waypoint_name=wp.name,
                waypoint_index=ref.sequence_order - 1,  # 0-based
                latitude=wp.latitude,
                longitude=wp.longitude,
                icao=wp.icao_code,
                estimated_time_utc=navigation_datetime,  # simplified
            ))

        # 3. Select models
        models = select_models(now, navigation_datetime)

        # 4. Fetch forecasts in parallel per model
        model_results = await asyncio.gather(
            *[self._build_model_result(model, contexts, navigation_datetime)
              for model in models]
        )

        # 5. Assemble simulation
        simulation = WeatherSimulation(
            route_id=route_id,
            simulated_at=now,
            navigation_datetime=navigation_datetime,
            waypoints=contexts,
            model_results=list(model_results),
        )

        # 6. Persist
        sim_id = await self._route_repo.add_simulation(user_id, route_id, simulation)
        simulation.id = sim_id

        return simulation

    async def _build_model_result(
        self,
        model: ForecastModel,
        contexts: list[WaypointContext],
        target_time: datetime,
    ) -> ModelResult:
        """Fetch forecasts for all waypoints from one model."""
        # Get model run time
        try:
            run_time = await self._openmeteo.get_model_run_time(model)
        except Exception:
            run_time = datetime.now(tz=timezone.utc)
            logger.warning("Could not fetch run time for %s, using now", model)

        # Fetch forecasts in parallel
        forecast_tasks = [
            self._openmeteo.get_forecast(
                model, ctx.latitude, ctx.longitude, target_time
            )
            for ctx in contexts
        ]
        forecasts = await asyncio.gather(*forecast_tasks, return_exceptions=True)

        # Build ModelPoints
        points: list[ModelPoint] = []
        for ctx, forecast in zip(contexts, forecasts):
            if isinstance(forecast, Exception):
                logger.warning("Forecast fetch failed for %s: %s", ctx.waypoint_name, forecast)
                continue
            vfr = compute_vfr_index(forecast, altitude_ft=3000)
            points.append(ModelPoint(
                waypoint_index=ctx.waypoint_index,
                forecast=forecast,
                vfr_index=vfr,
            ))

        return ModelResult(
            model=model,
            model_run_time=run_time,
            points=points,
        )

    async def collect_observations(
        self,
        user_id: str,
        route_id: str,
        simulation_id: str,
        actual_times: dict[int, datetime],
    ) -> WeatherSimulation:
        """Enrich a simulation with post-flight METAR observations.

        Args:
            actual_times: ``{waypoint_index: actual_passage_time_utc}``.
        """
        sim = await self._route_repo.get_simulation(user_id, route_id, simulation_id)
        if sim is None:
            raise ValueError(f"Simulation {simulation_id} not found")

        for wp_ctx in sim.waypoints:
            idx = wp_ctx.waypoint_index
            if idx in actual_times and wp_ctx.icao:
                wp_ctx.actual_time_utc = actual_times[idx]
                obs = await self._metar.get_metar_at_time(
                    wp_ctx.icao, actual_times[idx]
                )
                if obs is not None:
                    wp_ctx.observation = obs

        # TODO: persist updated simulation
        return sim
