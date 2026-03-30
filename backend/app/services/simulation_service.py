"""
Simulation application service for API-facing simulation and prediction flows.
"""

from collections import defaultdict
from typing import Any

import asyncpg

from app.analytics.advanced import get_advanced_analyzer
from app.cache import CacheTTL, get_cache
from app.exceptions import NotFoundError, ValidationError
from app.ml.prediction_engine import PredictionEngine
from app.repositories.simulation_repo import SimulationRepository
from app.schemas.simulation import PredictionV2Response, SimulationResponse


class SimulationService:
    """Service layer for rainfall simulation and v2 prediction APIs."""

    SEASON_MAP = {
        "rice": "kharif",
        "wheat": "rabi",
        "maize": "kharif",
        "soyabean": "kharif",
        "groundnut": "kharif",
    }

    def __init__(self, conn: asyncpg.Connection):
        self.repo = SimulationRepository(conn)

    async def get_simulation_response(
        self,
        district: str,
        crop: str,
        year: int,
        state: str,
    ) -> SimulationResponse | dict[str, Any]:
        """Build the spatial-regression simulation response."""
        cache_key = f"sim:{state}:{district}:{crop}:{year}"
        cache = get_cache()
        cached_result = await cache.get(cache_key)
        if cached_result:
            return cached_result

        variable_name, yield_rows = await self._resolve_yield_rows(state, crop, year)
        if len(yield_rows) < 5:
            raise NotFoundError(detail="Insufficient state data for spatial regression")

        rain_rows = await self.repo.get_state_rainfall_rows(state, include_jjas=False)
        rain_map = {str(row["district"]).upper(): float(row["annual"] or 0) for row in rain_rows}

        rainfall_x: list[float] = []
        yields_y: list[float] = []
        years: list[int] = []

        idx = 0
        for row in yield_rows:
            district_name = str(row["district_name"])
            district_yield = float(row["yield"])
            rainfall_value = rain_map.get(district_name.upper())

            if rainfall_value and rainfall_value > 0:
                rainfall_x.append(rainfall_value)
                yields_y.append(district_yield)
                years.append(idx)
                idx += 1

        if len(rainfall_x) < 5:
            raise NotFoundError(detail="Insufficient matching rainfall/yield data")

        analyzer = get_advanced_analyzer()
        sim_result = analyzer.calculate_impact_simulation(rainfall_x, yields_y, years)

        response = SimulationResponse(
            district=district,
            state=state,
            crop=crop,
            result=sim_result,
            note="Spatial Regression Proxy: Sensitivity derived from cross-district comparison within state.",
            validity={
                "climate_assumption": "stationary",
                "baseline_period": "1951-2000",
                "warning": "Simulation based on historic climate normals. Not valid for real-time weather impact.",
            },
        )

        await cache.set(cache_key, response, CacheTTL.ANALYSIS)
        return response

    async def get_prediction_v2_response(
        self,
        district: str,
        crop: str,
        year: int,
        state: str,
    ) -> PredictionV2Response | dict[str, Any]:
        """Build the multi-factor v2 prediction response."""
        cache_key = f"pred_v2:{state}:{district}:{crop}:{year}"
        cache = get_cache()
        cached_result = await cache.get(cache_key)
        if cached_result:
            return cached_result

        variable_name, yield_rows = await self._resolve_yield_rows(state, crop, year)
        if len(yield_rows) < 5:
            raise NotFoundError(detail="Insufficient yield data for prediction")

        rain_rows = await self.repo.get_state_rainfall_rows(state, include_jjas=True)
        rain_map = {
            str(row["district"]).upper(): {
                "annual": float(row["annual"] or 0),
                "monsoon_jjas": float(row["jjas"] or 0),
            }
            for row in rain_rows
        }

        hist_rows = await self.repo.get_state_historical_yields(state, variable_name)
        hist_map: dict[str, list[tuple[int, float]]] = defaultdict(list)
        for row in hist_rows:
            hist_map[str(row["district_name"])].append((int(row["year"]), float(row["value"])))

        area_rows = await self.repo.get_state_area_rows(state, f"{crop.lower()}_area", year)
        area_map = {str(row["district_name"]).upper(): float(row["area"]) for row in area_rows}

        district_data = self._build_prediction_district_data(yield_rows, rain_map, hist_map, area_map)
        if len(district_data) < 5:
            raise NotFoundError(detail="Insufficient matched data for prediction")

        engine = PredictionEngine()
        result = engine.predict(district_data, district)
        if result is None:
            raise ValidationError(detail="Prediction engine returned no result")

        response = PredictionV2Response.model_validate(
            {
                "district": district,
                "state": state,
                "crop": crop,
                "year": year,
                "prediction": result.to_dict(),
                "validity": {
                    "climate_assumption": "stationary",
                    "baseline_period": "1951-2000",
                    "warning": "Prediction based on historic climate normals and cross-sectional spatial regression. Not valid for real-time weather impact.",
                },
            }
        )

        await cache.set(cache_key, response, CacheTTL.ANALYSIS)
        return response

    async def _resolve_yield_rows(
        self,
        state: str,
        crop: str,
        year: int,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Resolve the best available yield variable, with seasonal fallback."""
        variable_name = f"{crop.lower()}_yield"
        yield_rows = await self.repo.get_state_yield_rows(state, variable_name, year)

        if len(yield_rows) < 5:
            season = self.SEASON_MAP.get(crop.lower())
            if season:
                variable_name = f"{crop.lower()}_yield_{season}"
                yield_rows = await self.repo.get_state_yield_rows(state, variable_name, year)

        return variable_name, yield_rows

    def _build_prediction_district_data(
        self,
        yield_rows: list[dict[str, Any]],
        rain_map: dict[str, dict[str, float]],
        hist_map: dict[str, list[tuple[int, float]]],
        area_map: dict[str, float],
    ) -> list[dict[str, Any]]:
        """Assemble district feature rows for the prediction engine."""
        district_data: list[dict[str, Any]] = []

        for row in yield_rows:
            district_name = str(row["district_name"])
            district_yield = float(row["yield"])
            rain_info = rain_map.get(district_name.upper())

            if not rain_info or rain_info["annual"] <= 0:
                continue

            yield_trend = 0.0
            yield_cv = 0.0
            history = hist_map.get(district_name, [])
            if len(history) >= 5:
                years_arr = [point[0] for point in history]
                values_arr = [point[1] for point in history]
                import numpy as np
                from scipy import stats as sp_stats

                slope, _, _, _, _ = sp_stats.linregress(years_arr, values_arr)
                yield_trend = float(slope)
                mean_value = np.mean(values_arr)  # type: ignore
                std_value = np.std(values_arr, ddof=1)  # type: ignore
                yield_cv = float((std_value / mean_value) * 100) if mean_value > 0 else 0.0

            district_data.append(
                {
                    "district": district_name,
                    "yield_value": district_yield,
                    "rainfall": rain_info["annual"],
                    "monsoon_jjas": rain_info["monsoon_jjas"],
                    "yield_trend": yield_trend,
                    "yield_cv": yield_cv,
                    "crop_area": area_map.get(district_name.upper(), 0.0),
                }
            )

        return district_data
