"""
Climate Service: Orchestrates rainfall and climate analysis responses.
"""

import asyncpg

from app.analytics import get_analyzer
from app.exceptions import NotFoundError, ValidationError
from app.repositories.climate_repo import ClimateRepository
from app.schemas.climate import (
    ClimateValidity,
    CorrelationMetric,
    MonthlyRainfall,
    RainfallCorrelationSet,
    RainfallMapItem,
    RainfallResponse,
    RainfallStatsResponse,
    RainfallYieldCorrelationResponse,
    RainfallYieldDataPoint,
    SeasonalRainfall,
    StateRainfallStatsResponse,
    WaterStressDistrict,
    WaterStressResponse,
)
from app.services.rainfall_service import (
    get_all_rainfall,
    get_rainfall_by_district,
    get_rainfall_count,
    get_state_rainfall_stats,
    get_water_stress_index,
)

SEASONAL_YIELD_FALLBACKS: dict[str, str] = {
    "rice": "kharif",
    "wheat": "rabi",
    "maize": "kharif",
    "soyabean": "kharif",
    "groundnut": "kharif",
    "cotton": "kharif",
}

CLIMATE_VALIDITY = ClimateValidity(
    climate_assumption="stationary",
    baseline_period="1951-2000",
    warning="Correlation based on historic climate normals. Not valid for real-time weather impact.",
)

WATER_STRESS_VALIDITY = ClimateValidity(
    climate_assumption="stationary",
    baseline_period="1951-2000",
    warning="Water stress mismatch index is based on historic annual rainfall normals. Not valid for current real-time drought assessment.",
)


class ClimateService:
    """Service for climate endpoints."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn
        self.repo = ClimateRepository(conn)

    async def get_rainfall_stats(self) -> RainfallStatsResponse:
        """Return rainfall table load stats."""
        count = await get_rainfall_count(self.conn)
        return RainfallStatsResponse(
            source="IMD 1951-2000 Normals (database)",
            record_count=count,
            status="loaded" if count > 0 else "empty",
        )

    async def get_rainfall(self, state: str, district: str) -> RainfallResponse:
        """Return rainfall normals for a single district."""
        rainfall = await get_rainfall_by_district(self.conn, state, district)
        if not rainfall:
            raise NotFoundError("Rainfall data", f"{district}, {state}")

        return RainfallResponse(
            state=rainfall.state,
            district=rainfall.district,
            monthly=MonthlyRainfall(
                jan=rainfall.jan,
                feb=rainfall.feb,
                mar=rainfall.mar,
                apr=rainfall.apr,
                may=rainfall.may,
                jun=rainfall.jun,
                jul=rainfall.jul,
                aug=rainfall.aug,
                sep=rainfall.sep,
                oct=rainfall.oct,
                nov=rainfall.nov,
                dec=rainfall.dec,
            ),
            seasonal=SeasonalRainfall(
                winter_jf=rainfall.winter_jf,
                pre_monsoon_mam=rainfall.pre_monsoon_mam,
                monsoon_jjas=rainfall.monsoon_jjas,
                post_monsoon_ond=rainfall.post_monsoon_ond,
            ),
            annual=rainfall.annual,
            source="IMD 1951-2000 Normals",
        )

    async def get_all_rainfall_data(self, state: str | None = None) -> list[RainfallMapItem]:
        """Return rainfall data for map views."""
        data = await get_all_rainfall(self.conn, state)
        return [RainfallMapItem(**item) for item in data]

    async def get_state_stats(self, state: str) -> StateRainfallStatsResponse:
        """Return aggregate rainfall stats for a state."""
        stats = await get_state_rainfall_stats(self.conn, state)
        if "error" in stats:
            raise NotFoundError("Rainfall data", state)
        return StateRainfallStatsResponse(**stats)

    async def get_water_stress(self, state: str, year: int) -> WaterStressResponse:
        """Return water-stress mismatch analysis for a state."""
        results = await get_water_stress_index(self.conn, state, year)
        if not results:
            raise NotFoundError(detail=f"Insufficient data to compute water stress for {state} in {year}")

        return WaterStressResponse(
            state=state,
            year=year,
            districts=[WaterStressDistrict(**item) for item in results],
            validity=WATER_STRESS_VALIDITY,
        )

    async def get_rainfall_yield_correlation(
        self,
        state: str,
        crop: str,
        year: int,
    ) -> RainfallYieldCorrelationResponse:
        """Return rainfall/yield correlations for districts in a state."""
        yield_rows = await self._get_yield_rows_with_fallback(state, crop, year)
        if len(yield_rows) < 5:
            raise ValidationError(detail="Insufficient yield data (need at least 5 districts)")

        matched_data: list[dict[str, float | str]] = []
        for row in yield_rows:
            district_name = str(row["district_name"])
            rainfall = await get_rainfall_by_district(self.conn, state, district_name)
            if rainfall:
                matched_data.append(
                    {
                        "district": district_name,
                        "yield": float(row["yield_val"]),
                        "annual_rainfall": rainfall.annual,
                        "monsoon_rainfall": rainfall.monsoon_jjas,
                    }
                )

        if len(matched_data) < 5:
            raise ValidationError(
                detail=f"Could not match sufficient districts with rainfall data ({len(matched_data)} found)"
            )

        analyzer = get_analyzer()
        yields = [float(item["yield"]) for item in matched_data]
        annual_rain = [float(item["annual_rainfall"]) for item in matched_data]
        monsoon_rain = [float(item["monsoon_rainfall"]) for item in matched_data]

        annual_corr = analyzer.pearson_correlation(annual_rain, yields)
        monsoon_corr = analyzer.pearson_correlation(monsoon_rain, yields)

        return RainfallYieldCorrelationResponse(
            state=state,
            crop=crop,
            year=year,
            sample_size=len(matched_data),
            correlations=RainfallCorrelationSet(
                annual_rainfall=self._build_correlation_metric(float(annual_corr.value)),
                monsoon_rainfall=self._build_correlation_metric(float(monsoon_corr.value)),
            ),
            data_points=[
                RainfallYieldDataPoint.model_validate(
                    {
                        "district": str(item["district"]),
                        "yield": float(item["yield"]),
                        "annual_rainfall": float(item["annual_rainfall"]),
                        "monsoon_rainfall": float(item["monsoon_rainfall"]),
                    }
                )
                for item in matched_data
            ],
            note="Correlation uses IMD 1951-2000 rainfall normals vs actual yields",
            validity=CLIMATE_VALIDITY,
        )

    async def _get_yield_rows_with_fallback(
        self,
        state: str,
        crop: str,
        year: int,
    ) -> list[dict[str, str | float]]:
        """Return district yield rows, using seasonal fallback when needed."""
        variable = f"{crop.lower()}_yield"
        rows = await self.repo.get_state_yield_rows(state, variable, year)
        if len(rows) >= 5:
            return rows

        season = SEASONAL_YIELD_FALLBACKS.get(crop.lower())
        if not season:
            return rows

        seasonal_variable = f"{crop.lower()}_yield_{season}"
        return await self.repo.get_state_yield_rows(state, seasonal_variable, year)

    def _build_correlation_metric(self, value: float) -> CorrelationMetric:
        """Build interpretation metadata for a correlation coefficient."""
        return CorrelationMetric(
            r=round(value, 4),
            interpretation=self._interpret_correlation(value),
            direction="positive" if value > 0 else "negative",
        )

    @staticmethod
    def _interpret_correlation(value: float) -> str:
        """Interpret a Pearson correlation coefficient."""
        magnitude = abs(value)
        if magnitude < 0.2:
            return "negligible"
        if magnitude < 0.4:
            return "weak"
        if magnitude < 0.6:
            return "moderate"
        if magnitude < 0.8:
            return "strong"
        return "very strong"
