"""
Yield Analysis Service.
"""

import logging
import math
import warnings
from dataclasses import dataclass
from typing import Any, TypedDict

from app.cache import CacheTTL, cached  # type: ignore[import]

from .base import BaseAnalyticsService


@dataclass
class YieldTrend:
    """Yield trend analysis results."""

    crop: str
    start_year: int
    end_year: int
    start_yield: float
    end_yield: float
    cagr: float
    volatility: float
    trend: str


class DistrictGapEntry(TypedDict):
    name: str
    gaps: list[float]
    yields: list[float]


class YieldGapRankingEntry(TypedDict):
    cdk: str
    district_name: str
    avg_gap: float
    latest_gap: float
    avg_yield: float
    gap_trend: float
    status: str
    rank: int


class YieldAnalysisService(BaseAnalyticsService):
    """Analytics for yield trends, growth rates, forecasting, and gaps."""

    @cached(ttl=CacheTTL.ANALYSIS, prefix="yield_trend")
    async def get_yield_trend(
        self, cdk: str, crop: str, start_year: int = 1990, end_year: int = 2020
    ) -> YieldTrend | None:
        """Calculate yield trend with CAGR and volatility."""
        query = """
            SELECT year, value
            FROM agri_metrics
            WHERE district_lgd::text = $1
              AND year BETWEEN $2 AND $3
              AND value > 0
              AND variable_name = $4
            ORDER BY year
        """
        rows = await self._fetch_with_fallback(query, crop, "yield", cdk, start_year, end_year)

        if len(rows) < 3:
            return None

        years = [r["year"] for r in rows]
        yields = [r["value"] for r in rows]

        n_years = years[-1] - years[0]
        cagr = (yields[-1] / yields[0]) ** (1 / n_years) - 1 if n_years > 0 and yields[0] > 0 else 0

        yoy_changes = []
        for i in range(1, len(yields)):
            if yields[i - 1] > 0:
                yoy_changes.append((yields[i] - yields[i - 1]) / yields[i - 1])

        volatility = 0.0
        if yoy_changes:
            mean_change = sum(yoy_changes) / len(yoy_changes)
            variance = sum((c - mean_change) ** 2 for c in yoy_changes) / len(yoy_changes)
            volatility = math.sqrt(variance)

        if cagr > 0.02:
            trend = "increasing"
        elif cagr < -0.02:
            trend = "decreasing"
        else:
            trend = "stable"

        return YieldTrend(
            crop=crop,
            start_year=years[0],
            end_year=years[-1],
            start_yield=round(yields[0], 2),
            end_yield=round(yields[-1], 2),
            cagr=round(cagr * 100, 2),
            volatility=round(volatility * 100, 2),
            trend=trend,
        )

    @cached(ttl=CacheTTL.ANALYSIS, prefix="yoy_growth")
    async def get_yoy_growth(
        self, cdk: str, crop: str, start_year: int = 2010, end_year: int = 2020
    ) -> list[dict[str, Any]]:
        """Calculate year-over-year growth rates."""
        query = """
            SELECT year, value
            FROM agri_metrics
            WHERE district_lgd::text = $1
              AND year BETWEEN $2 AND $3
              AND value > 0
              AND variable_name = $4
            ORDER BY year
        """
        rows = await self._fetch_with_fallback(query, crop, "yield", cdk, start_year, end_year)

        growth_data = []
        prev_value = None

        for r in rows:
            yoy = None
            if prev_value and prev_value > 0:
                yoy = round((r["value"] - prev_value) / prev_value * 100, 2)

            growth_data.append({"year": r["year"], "yield": round(r["value"], 2), "yoy_growth": yoy})
            prev_value = r["value"]

        return growth_data

    @cached(ttl=CacheTTL.ANALYSIS, prefix="yield_forecast")
    async def get_yield_forecast(self, cdk: str, crop: str, forecast_years: int = 5) -> dict[str, Any]:
        """Produce a yield forecast using SARIMA or Simple Linear fallback."""
        query = """
            SELECT year, value FROM agri_metrics
            WHERE district_lgd::text = $1
              AND year >= 2000
              AND value > 0
              AND variable_name = $2
            ORDER BY year
        """
        rows = await self._fetch_with_fallback(query, crop, "yield", cdk)

        if len(rows) < 5:
            return {"error": "Insufficient data to forecast. Need at least 5 years."}

        years = [r["year"] for r in rows]
        yields = [r["value"] for r in rows]
        last_year = years[-1]
        forecast = []
        slope = 0.0

        try:
            from statsmodels.tools.sm_exceptions import ConvergenceWarning
            from statsmodels.tsa.statespace.sarimax import SARIMAX

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", ConvergenceWarning)
                warnings.simplefilter("ignore", UserWarning)
                model = SARIMAX(yields, order=(1, 1, 1), enforce_stationarity=False, enforce_invertibility=False)
                results = model.fit(disp=False)
                forecast_result = results.get_forecast(steps=forecast_years)
                pred_mean = forecast_result.predicted_mean
                pred_ci = forecast_result.conf_int(alpha=0.20)

                if hasattr(pred_mean, "tolist"):
                    pred_mean = pred_mean.tolist()
                if hasattr(pred_ci, "tolist"):
                    pred_ci = pred_ci.tolist()
                elif hasattr(pred_ci, "values"):
                    pred_ci = pred_ci.values.tolist()

                for i in range(forecast_years):
                    forecast.append(
                        {
                            "year": last_year + i + 1,
                            "projected_yield": round(max(0, float(pred_mean[i])), 2),
                            "confidence_interval_lower": round(max(0, float(pred_ci[i][0])), 2),
                            "confidence_interval_upper": round(max(0, float(pred_ci[i][1])), 2),
                        }
                    )
        except Exception as e:
            logging.getLogger("analytics").warning(f"SARIMA failed for {cdk} {crop}: {e}")

        # Linear trend calculation
        n = len(years)
        sum_x, sum_y = sum(years), sum(yields)
        sum_xy = sum(x * y for x, y in zip(years, yields, strict=True))
        sum_xx = sum(x * x for x in years)
        denom = n * sum_xx - sum_x * sum_x
        slope = (n * sum_xy - sum_x * sum_y) / denom if denom != 0 else 0
        c = (sum_y - slope * sum_x) / n if denom != 0 else sum_y / n

        if not forecast:
            for i in range(1, forecast_years + 1):
                f_yield = max(0, float(slope * (last_year + i) + c))
                forecast.append(
                    {
                        "year": last_year + i,
                        "projected_yield": round(f_yield, 2),
                        "confidence_interval_lower": round(f_yield * 0.9, 2),
                        "confidence_interval_upper": round(f_yield * 1.1, 2),
                    }
                )

        return {
            "cdk": cdk,
            "crop": crop,
            "historical_trend": "increasing" if slope > 0.0 else "decreasing",
            "slope": round(slope, 4),
            "forecast": forecast,
        }

    @cached(ttl=CacheTTL.ANALYSIS, prefix="yield_gap")
    async def get_yield_gap(
        self, state: str, crop: str, start_year: int = 2000, end_year: int = 2020
    ) -> dict[str, Any]:
        """Quantifies the yield gap for each district against the state's 90th percentile 'frontier'."""
        query = """
             SELECT d.district_name, m.district_lgd::text as cdk, m.year, m.value
             FROM agri_metrics m
             JOIN districts d ON m.district_lgd = d.lgd_code
             WHERE UPPER(d.state_name) = UPPER($1)
               AND m.value > 0
               AND m.year BETWEEN $2 AND $3
               AND m.variable_name = $4
             ORDER BY m.year, m.value DESC
        """
        rows = await self._fetch_with_fallback(query, crop, "yield", state, start_year, end_year)

        if not rows:
            return {"error": "No data found for the given parameters"}

        yearly_data: dict[int, list[tuple[str, str, float]]] = {}
        for r in rows:
            yearly_data.setdefault(r["year"], []).append((r["cdk"], r["district_name"], r["value"]))

        convergence_timeline = []
        district_gaps: dict[str, DistrictGapEntry] = {}

        for yr, dist_vals in sorted(yearly_data.items()):
            yields = sorted([v[2] for v in dist_vals])
            if not yields:
                continue

            idx_90 = min(int(0.9 * len(yields)), len(yields) - 1)
            frontier_yield = yields[idx_90]

            total_gap = 0.0
            for cdk, name, yld in dist_vals:
                gap = max(0, frontier_yield - yld)
                total_gap += gap
                dic_entry = district_gaps.setdefault(cdk, {"name": name, "gaps": [], "yields": []})
                dic_entry["gaps"].append(gap)
                dic_entry["yields"].append(yld)

            convergence_timeline.append(
                {
                    "year": yr,
                    "frontier_yield": round(frontier_yield, 2),
                    "state_avg_yield": round(sum(yields) / len(yields), 2),
                    "avg_gap": round(total_gap / len(dist_vals), 2),
                }
            )

        rankings: list[YieldGapRankingEntry] = []
        for cdk, data in district_gaps.items():
            gaps, yields = data["gaps"], data["yields"]
            if not gaps:
                continue

            gap_trend, n_years = 0.0, len(gaps)
            if n_years > 5:
                x = list(range(n_years))
                denom = n_years * sum(x_i * x_i for x_i in x) - sum(x) * sum(x)
                if denom != 0:
                    gap_trend = (
                        n_years * sum(x_i * y_i for x_i, y_i in zip(x, gaps, strict=True)) - sum(x) * sum(gaps)
                    ) / denom

            rankings.append(
                {
                    "cdk": cdk,
                    "district_name": data["name"],
                    "avg_gap": round(sum(gaps) / len(gaps), 2),
                    "latest_gap": round(gaps[-1], 2),
                    "avg_yield": round(sum(yields) / len(yields), 2),
                    "gap_trend": round(gap_trend, 2),
                    "status": "Closing" if gap_trend < -1 else "Widening" if gap_trend > 1 else "Stagnant",
                    "rank": 0,
                }
            )

        rankings.sort(key=lambda x: x["avg_gap"], reverse=True)
        for i, r in enumerate(rankings, 1):
            r["rank"] = i

        return {
            "state": state,
            "crop": crop,
            "period": f"{start_year}-{end_year}",
            "convergence_timeline": convergence_timeline,
            "district_rankings": rankings,
        }
