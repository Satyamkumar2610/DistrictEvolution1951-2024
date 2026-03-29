"""
Advanced Analytics Service for I-ASCAP.

Provides data science-driven insights:
- Crop Diversification Index (CDI)
- Yield Trend Analysis (CAGR, volatility)
- Rainfall-Yield Correlation
- Split Impact Comparison
- Crop Correlation Matrix
- District Performance Rankings

Updated to use lgd_code/district_lgd schema.
"""

import contextlib
import math
from dataclasses import dataclass
from typing import Any

import asyncpg  # type: ignore[import]

from app.cache import CacheTTL, cached  # type: ignore[import]


@dataclass
class YieldTrend:
    """Yield trend analysis results."""
    crop: str
    start_year: int
    end_year: int
    start_yield: float
    end_yield: float
    cagr: float  # Compound Annual Growth Rate
    volatility: float  # Standard deviation of YoY changes
    trend: str  # "increasing", "decreasing", "stable"


@dataclass
class CropDiversification:
    """Crop diversification index for a district."""
    cdk: str
    year: int
    herfindahl_index: float  # Market concentration (0-1, lower = more diverse)
    simpson_index: float  # Diversity index (0-1, higher = more diverse)
    num_crops: int
    dominant_crop: str
    dominant_share: float
    breakdown: dict[str, float]  # crop_name -> share (0-1)


class AdvancedAnalyticsService:
    """Advanced analytics engine for agricultural data."""

    def __init__(self, db: asyncpg.Connection):
        self.db = db

    # ============================================================
    # HELPER METHODS
    # ============================================================

    async def _fetch_with_fallback(
        self,
        query_template: str,
        crop: str,
        metric: str,
        *args
    ) -> list[asyncpg.Record]:
        """
        Executes a query by substituting the variable_name parameter (always the last arg).
        If the primary crop_metric (e.g. 'wheat_yield') returns no data, it falls back
        to 'wheat_yield_rabi', etc.
        """
        # 1. Try standard aggregated metric
        primary_var = f"{crop}_{metric}"
        all_args = list(args) + [primary_var]
        rows = await self.db.fetch(query_template, *all_args)

        # 2. Try seasonal fallback if no data
        if not rows or len(rows) == 0:
            season_map = {
                "rice": "kharif",
                "wheat": "rabi",
                "maize": "kharif",
                "soyabean": "kharif",
                "groundnut": "kharif",
                "cotton": "kharif",
                "pearl_millet": "kharif",
                "sorghum": "kharif",
                "chickpea": "rabi"}
            season = season_map.get(crop.lower())
            if season:
                fallback_var = f"{crop}_{metric}_{season}"
                all_args[-1] = fallback_var
                rows = await self.db.fetch(query_template, *all_args)

        return rows  # type: ignore[return-value]

    # ============================================================
    # CROP DIVERSIFICATION INDEX
    # ============================================================

    @cached(ttl=CacheTTL.ANALYSIS, prefix="cdi")
    async def get_crop_diversification(
        self,
        cdk: str,
        year: int
    ) -> CropDiversification | None:
        """
        Calculate Crop Diversification Index for a district-year.

        Uses Herfindahl-Hirschman Index (HHI) and Simpson's Diversity Index.
        """
        # Get area by crop for this district-year
        rows = await self.db.fetch("""
            SELECT
                SPLIT_PART(variable_name, '_', 1) as crop,
                value as area
            FROM agri_metrics
            WHERE district_lgd::text = $1
              AND year = $2
              AND variable_name LIKE '%_area%'
              AND variable_name NOT LIKE '%_kharif%'
              AND variable_name NOT LIKE '%_rabi%'
              AND value > 0
            ORDER BY value DESC
        """, cdk, year)

        if not rows:
            return None

        # Calculate total area and shares
        total_area = sum(r['area'] for r in rows)
        if total_area == 0:
            return None

        shares = [(r['crop'], r['area'] / total_area) for r in rows]

        # Herfindahl-Hirschman Index (sum of squared shares)
        hhi = sum(s ** 2 for _, s in shares)

        # Simpson's Diversity Index (1 - HHI)
        simpson = 1 - hhi

        dominant_crop, dominant_share = shares[0]

        # Build breakdown dict (crop -> share as decimal 0-1)
        breakdown = {crop: round(share, 4) for crop, share in shares}

        return CropDiversification(
            cdk=cdk,
            year=year,
            herfindahl_index=round(hhi, 4),
            simpson_index=round(simpson, 4),
            num_crops=len(rows),
            dominant_crop=dominant_crop,
            dominant_share=round(dominant_share * 100, 1),
            breakdown=breakdown
        )

    @cached(ttl=CacheTTL.ANALYSIS, prefix="crop_shift")
    async def get_crop_shift(
        self,
        cdk: str,
    ) -> list[dict[str, Any]]:
        """
        Calculates the shifting mix of crops over a district's entire history.
        Groups minor crops into an 'Other' category and computes diversity indices per year.
        """
        # Fetch all area metrics across all years
        rows = await self.db.fetch("""
            SELECT
                year,
                SPLIT_PART(variable_name, '_', 1) as crop,
                value as area
            FROM agri_metrics
            WHERE district_lgd::text = $1
              AND variable_name LIKE '%_area%'
              AND variable_name NOT LIKE '%_kharif%'
              AND variable_name NOT LIKE '%_rabi%'
              AND value > 0
            ORDER BY year, value DESC
        """, cdk)

        if not rows:
            return []

        # Group by year
        yearly_data: dict[int, dict[str, float]] = {}
        for r in rows:
            yr = r['year']
            crp = r['crop']
            area = r['area']

            if yr not in yearly_data:
                yearly_data[yr] = {}

            yearly_data[yr][crp] = yearly_data[yr].get(crp, 0) + area

        results = []
        for yr, crops in sorted(yearly_data.items()):
            total_area = sum(crops.values())
            if total_area == 0:
                continue

            # Filter to top 5 crops, everything else goes to 'Other'
            sorted_crops = sorted(
                crops.items(),
                key=lambda x: x[1],
                reverse=True)
            top_crops = sorted_crops[:5]  # type: ignore[index]
            other_area = sum(area for crp, area in sorted_crops[5:])  # type: ignore[index]

            # Compute Shannon Diversity Index (H = -sum(p * ln(p)))
            shannon_index: float = 0.0
            shares: dict[str, float] = {}
            for crp, area in top_crops:
                share = area / total_area
                shares[crp] = round(share, 4)  # type: ignore[call-overload]
                if share > 0:
                    shannon_index -= share * math.log(share)  # type: ignore[operator]

            if other_area > 0:
                other_share = other_area / total_area
                shares['other'] = round(other_share, 4)  # type: ignore[call-overload]
                if other_share > 0:
                    shannon_index -= other_share * math.log(other_share)  # type: ignore[operator, assignment]

            hhi = sum(s ** 2 for s in shares.values())
            simpson = 1 - hhi

            results.append({
                "year": yr,
                "total_area": round(total_area, 2),  # type: ignore[call-overload]
                "shannon_index": round(shannon_index, 4),  # type: ignore[call-overload]
                "simpson_index": round(simpson, 4),
                "dominant_crop": top_crops[0][0] if top_crops else "none",
                "dominant_share": round(shares.get(top_crops[0][0], 0) * 100, 1) if top_crops else 0,
                "crop_mix": shares
            })

        return results

    # ============================================================
    # YIELD TREND ANALYSIS
    # ============================================================

    @cached(ttl=CacheTTL.ANALYSIS, prefix="yield_trend")
    async def get_yield_trend(
        self,
        cdk: str,
        crop: str,
        start_year: int = 1990,
        end_year: int = 2020
    ) -> YieldTrend | None:
        """
        Calculate yield trend with CAGR and volatility.
        """
        query_template = """
            SELECT year, value
            FROM agri_metrics
            WHERE district_lgd::text = $1
              AND year BETWEEN $2 AND $3
              AND value > 0
              AND variable_name = $4
            ORDER BY year
        """
        rows = await self._fetch_with_fallback(query_template, crop, "yield", cdk, start_year, end_year)

        if len(rows) < 3:
            return None

        years = [r['year'] for r in rows]
        yields = [r['value'] for r in rows]

        # CAGR = (end/start)^(1/n) - 1
        n_years = years[-1] - years[0]
        cagr = (yields[-1] / yields[0]) ** (1 / n_years) - 1 if n_years > 0 and yields[0] > 0 else 0

        # Volatility (std dev of year-over-year percentage changes)
        yoy_changes = []
        for i in range(1, len(yields)):
            if yields[i - 1] > 0:
                yoy_changes.append((yields[i] - yields[i - 1]) / yields[i - 1])

        if yoy_changes:
            mean_change = sum(yoy_changes) / len(yoy_changes)
            variance = sum(
                (c - mean_change) ** 2 for c in yoy_changes) / len(yoy_changes)  # type: ignore[operator]
            volatility = math.sqrt(variance)
        else:
            volatility = 0

        # Determine trend
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
            start_yield=round(yields[0], 2),  # type: ignore[call-overload]
            end_yield=round(yields[-1], 2),  # type: ignore[call-overload]
            cagr=round(cagr * 100, 2),  # type: ignore[call-overload]
            volatility=round(volatility * 100, 2),  # type: ignore[call-overload]
            trend=trend
        )

    # ============================================================
    # SPLIT IMPACT ANALYSIS (Before/After Comparison)
    # ============================================================

    @cached(ttl=CacheTTL.SPLIT_EVENTS, prefix="split_impact")
    async def get_split_impact(
        self,
        parent_cdk: str,
        child_cdks: list[str],
        split_year: int,
        crop: str,
        years_before: int = 5,
        years_after: int = 5
    ) -> dict[str, Any]:
        """
        Compare agricultural performance before/after district split.
        """
        # Before split: parent district performance
        query_template = """
            SELECT year, value
            FROM agri_metrics
            WHERE district_lgd::text = $1
              AND year BETWEEN $2 AND $3
              AND value > 0
              AND variable_name = $4
            ORDER BY year
        """
        before_data = await self._fetch_with_fallback(
            query_template, crop, "yield", parent_cdk, split_year - years_before, split_year - 1
        )

        before_yields = [r['value'] for r in before_data]
        before_avg = sum(before_yields) / \
            len(before_yields) if before_yields else 0

        # After split: weighted average of children
        after_results: dict[str, dict[str, Any]] = {}
        for child_cdk in child_cdks:
            after_data = await self._fetch_with_fallback(
                query_template, crop, "yield", child_cdk, split_year, split_year + years_after
            )

            after_yields = [r['value'] for r in after_data]
            after_results[child_cdk] = {'yields': after_yields, 'avg': sum(
                after_yields) / len(after_yields) if after_yields else 0}

        # Calculate aggregate after-split performance
        all_after_avgs: list[float] = [float(v['avg'])
                          for v in after_results.values() if v['avg'] > 0]
        after_avg = sum(all_after_avgs) / \
            len(all_after_avgs) if all_after_avgs else 0  # type: ignore[operator]

        # Impact metrics
        absolute_change = after_avg - before_avg  # type: ignore[operator]
        percent_change = (
            absolute_change
            / before_avg  # type: ignore[operator]
            * 100) if before_avg > 0 else 0  # type: ignore[operator]

        return {
            'parent_cdk': parent_cdk,
            'child_cdks': child_cdks,
            'split_year': split_year,
            'crop': crop,
            'before': {
                'years': [r['year'] for r in before_data],
                'yields': before_yields,
                'average': round(before_avg, 2)  # type: ignore[call-overload]
            },
            'after': {
                'by_child': after_results,
                'combined_average': round(after_avg, 2)  # type: ignore[call-overload]
            },
            'impact': {
                'absolute_change': round(absolute_change, 2),  # type: ignore[call-overload]
                'percent_change': round(percent_change, 2),  # type: ignore[call-overload]
                'assessment': 'positive' if percent_change > 5 else 'negative' if percent_change < -5 else 'neutral'
            }
        }

    # ============================================================
    # CROP CORRELATION MATRIX
    # ============================================================

    @cached(ttl=CacheTTL.ANALYSIS, prefix="crop_corr")
    async def get_crop_correlations(
        self,
        state: str,
        year: int,
        crops: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Calculate correlation between crop areas/yields across districts.
        Helps identify crop substitution patterns.
        """
        if crops is None:
            crops = [
                'rice',
                'wheat',
                'maize',
                'groundnut',
                'cotton',
                'sugarcane']

        # Get yield data for each crop across districts
        crop_data = {}
        for crop in crops:
            query_template = """
                SELECT m.district_lgd::text as cdk, m.value
                FROM agri_metrics m
                JOIN districts d ON m.district_lgd = d.lgd_code
                WHERE UPPER(d.state_name) = UPPER($1)
                  AND m.year = $2
                  AND m.value > 0
                  AND m.variable_name = $3
            """
            rows = await self._fetch_with_fallback(query_template, crop, "yield", state, year)

            crop_data[crop] = {r['cdk']: r['value'] for r in rows}

        # Calculate pairwise correlations
        correlations: dict[str, dict[str, float | None]] = {}
        for _i, crop1 in enumerate(crops):
            correlations[crop1] = {}
            for crop2 in crops:
                if crop1 == crop2:
                    correlations[crop1][crop2] = 1.0  # type: ignore[index]
                else:
                    # Find common districts
                    common = set(  # type: ignore[arg-type]
                        crop_data[crop1].keys()) & set(
                        crop_data[crop2].keys())  # type: ignore[arg-type]
                    if len(common) < 3:
                        correlations[crop1][crop2] = None  # type: ignore[index]
                        continue

                    vals1 = [crop_data[crop1][cdk] for cdk in common]  # type: ignore[index]
                    vals2 = [crop_data[crop2][cdk] for cdk in common]  # type: ignore[index]

                    # Pearson correlation
                    mean1 = sum(vals1) / len(vals1)
                    mean2 = sum(vals2) / len(vals2)

                    cov = sum((v1 - mean1) * (v2 - mean2)
                              for v1, v2 in zip(vals1, vals2, strict=False))
                    std1 = math.sqrt(sum((v - mean1) ** 2 for v in vals1))
                    std2 = math.sqrt(sum((v - mean2) ** 2 for v in vals2))

                    if std1 > 0 and std2 > 0:
                        corr = cov / (std1 * std2)
                        correlations[crop1][crop2] = round(corr, 3)  # type: ignore[call-overload, index]
                    else:
                        correlations[crop1][crop2] = None  # type: ignore[index]

        return {
            'state': state,
            'year': year,
            'crops': crops,
            'correlations': correlations
        }

    # ============================================================
    # DISTRICT PERFORMANCE RANKINGS
    # ============================================================

    @cached(ttl=CacheTTL.ANALYSIS, prefix="dist_rank")
    async def get_district_rankings(
        self,
        state: str,
        crop: str,
        year: int,
        metric: str = 'yield'
    ) -> list[dict[str, Any]]:
        """
        Rank districts by crop performance.
        """
        query_template = """
            SELECT
                m.district_lgd::text as cdk,
                d.district_name,
                m.value
            FROM agri_metrics m
            JOIN districts d ON m.district_lgd = d.lgd_code
            WHERE UPPER(d.state_name) = UPPER($1)
              AND m.year = $2
              AND m.value > 0
              AND m.variable_name = $3
            ORDER BY m.value DESC
        """
        rows = await self._fetch_with_fallback(query_template, crop, metric, state, year)

        rankings = []
        for i, r in enumerate(rows, 1):
            rankings.append({
                'rank': i,
                'cdk': r['cdk'],
                'district': r['district_name'],
                'value': round(r['value'], 2),
            })

        return rankings

    # ============================================================
    # YEAR-OVER-YEAR GROWTH ANALYSIS
    # ============================================================

    @cached(ttl=CacheTTL.ANALYSIS, prefix="yoy_growth")
    async def get_yoy_growth(
        self,
        cdk: str,
        crop: str,
        start_year: int = 2010,
        end_year: int = 2020
    ) -> list[dict[str, Any]]:
        """
        Calculate year-over-year growth rates.
        """
        query_template = """
            SELECT year, value
            FROM agri_metrics
            WHERE district_lgd::text = $1
              AND year BETWEEN $2 AND $3
              AND value > 0
              AND variable_name = $4
            ORDER BY year
        """
        rows = await self._fetch_with_fallback(query_template, crop, "yield", cdk, start_year, end_year)

        growth_data = []
        prev_value = None

        for r in rows:
            yoy = None
            if prev_value and prev_value > 0:
                yoy = round((r['value'] - prev_value) / prev_value * 100, 2)

            growth_data.append({
                'year': r['year'],
                'yield': round(r['value'], 2),
                'yoy_growth': yoy
            })
            prev_value = r['value']

        return growth_data

    # ============================================================
    # SEASONAL COMPARISON (Kharif vs Rabi)
    # ============================================================

    @cached(ttl=CacheTTL.ANALYSIS, prefix="season_comp")
    async def get_seasonal_comparison(
        self,
        cdk: str,
        crop: str,
        year: int
    ) -> dict[str, Any]:
        """
        Compare Kharif vs Rabi season performance.
        Only works for DES data which has seasonal breakdown.
        """
        kharif = await self.db.fetchrow("""
            SELECT value FROM agri_metrics
            WHERE district_lgd::text = $1 AND year = $2
              AND variable_name LIKE $3
        """, cdk, year, f"{crop}_yield_kharif")

        rabi = await self.db.fetchrow("""
            SELECT value FROM agri_metrics
            WHERE district_lgd::text = $1 AND year = $2
              AND variable_name LIKE $3
        """, cdk, year, f"{crop}_yield_rabi")

        kharif_val = kharif['value'] if kharif else None
        rabi_val = rabi['value'] if rabi else None

        return {
            'cdk': cdk, 'crop': crop, 'year': year, 'kharif_yield': round(
                kharif_val, 2) if kharif_val else None, 'rabi_yield': round(
                rabi_val, 2) if rabi_val else None, 'dominant_season': 'kharif' if (
                kharif_val or 0) > (
                    rabi_val or 0) else 'rabi'}

    # ============================================================
    # YIELD FORECASTING
    # ============================================================

    @cached(ttl=CacheTTL.ANALYSIS, prefix="yield_forecast")
    async def get_yield_forecast(
        self,
        cdk: str,
        crop: str,
        forecast_years: int = 5
    ) -> dict[str, Any]:
        """
        Produce a yield forecast using SARIMA (statsmodels),
        with a fallback to simple linear regression.
        """
        # Fetch the last 20+ years of data
        query_template = """
            SELECT year, value FROM agri_metrics
            WHERE district_lgd::text = $1
              AND year >= 2000
              AND value > 0
              AND variable_name = $2
            ORDER BY year
        """
        rows = await self._fetch_with_fallback(query_template, crop, "yield", cdk)

        if len(rows) < 5:
            return {
                "error": "Insufficient data to forecast. Need at least 5 years."}

        years = [r['year'] for r in rows]
        yields = [r['value'] for r in rows]

        last_year = years[-1]
        forecast = []
        slope = 0.0

        # 1. Try SARIMA (Requires statsmodels)
        try:
            import warnings

            from statsmodels.tools.sm_exceptions import ConvergenceWarning  # type: ignore[import]
            from statsmodels.tsa.statespace.sarimax import SARIMAX  # type: ignore[import]

            with warnings.catch_warnings():
                warnings.simplefilter('ignore', ConvergenceWarning)
                warnings.simplefilter('ignore', UserWarning)
                # SARIMAX(1, 1, 1) is a good default for simple trended time
                # series
                model = SARIMAX(
                    yields,
                    order=(
                        1,
                        1,
                        1),
                    enforce_stationarity=False,
                    enforce_invertibility=False)
                results = model.fit(disp=False)

                forecast_result = results.get_forecast(steps=forecast_years)
                pred_mean = forecast_result.predicted_mean
                # 80% confidence interval
                pred_ci = forecast_result.conf_int(alpha=0.20)

                # Convert to normal python lists depending on statsmodels
                # output format
                if hasattr(pred_mean, "tolist"):
                    pred_mean = pred_mean.tolist()

                if hasattr(pred_ci, "tolist"):
                    pred_ci = [row for row in pred_ci.tolist()]
                elif hasattr(pred_ci, "values"):
                    pred_ci = pred_ci.values.tolist()

                for i in range(forecast_years):
                    f_year = last_year + i + 1
                    f_yield = max(0, float(pred_mean[i]))  # type: ignore[call-overload]
                    lower = max(0, float(pred_ci[i][0]))  # type: ignore[call-overload]
                    upper = max(0, float(pred_ci[i][1]))  # type: ignore[call-overload]

                    forecast.append({
                        "year": f_year,
                        "projected_yield": round(f_yield, 2),
                        "confidence_interval_lower": round(lower, 2),
                        "confidence_interval_upper": round(upper, 2)
                    })
        except Exception as e:
            import logging
            logging.getLogger("analytics").warning(
                f"SARIMA failed for {cdk} {crop}, falling back to linear: {e}")

        # 2. Calculate Linear Trend (used for historical_trend and as fallback)
        n = len(years)
        sum_x = sum(years)
        sum_y = sum(yields)
        sum_xy = sum(x * y for x, y in zip(years, yields, strict=False))
        sum_xx = sum(x * x for x in years)

        denominator = n * sum_xx - sum_x * sum_x
        if denominator == 0:
            m = 0
            c = sum_y / n
        else:
            m = (n * sum_xy - sum_x * sum_y) / denominator
            c = (sum_y - m * sum_x) / n
        slope = m

        # 3. Fallback: If SARIMA failed, use Linear Regression
        if not forecast:
            for i in range(1, forecast_years + 1):
                f_year = last_year + i
                f_yield = m * f_year + c
                f_yield = max(0, float(f_yield))  # type: ignore[call-overload]
                forecast.append({
                    "year": f_year,
                    "projected_yield": round(f_yield, 2),
                    "confidence_interval_lower": round(f_yield * 0.9, 2),
                    "confidence_interval_upper": round(f_yield * 1.1, 2)
                })

        return {
            "cdk": cdk,
            "crop": crop,
            "historical_trend": "increasing" if slope > 0.0 else "decreasing",
            "slope": round(slope, 4),  # type: ignore[call-overload]
            "forecast": forecast
        }

    # ============================================================
    # CLIMATE RESILIENCE / VOLATILITY INDEX
    # ============================================================

    @cached(ttl=CacheTTL.ANALYSIS, prefix="resilience_idx")
    async def get_resilience_index(
        self,
        state: str,
        crop: str,
        year_range: list[int] | None = None
    ) -> list[dict[str, Any]]:
        """
        Rank districts by true climate resilience, measured by the magnitude
        of yield drop and speed of recovery during known systemic drought/shock years.
        """
        if year_range is None:
            year_range = [1990, 2020]
        query_template = """
            SELECT
                d.district_name,
                m.district_lgd::text as cdk,
                m.year,
                m.value
            FROM agri_metrics m
            JOIN districts d ON m.district_lgd = d.lgd_code
            WHERE UPPER(d.state_name) = UPPER($1)
              AND m.value > 0
              AND m.year BETWEEN $2 AND $3
              AND m.variable_name = $4
            ORDER BY m.district_lgd, m.year
        """
        rows = await self._fetch_with_fallback(query_template, crop, "yield", state, year_range[0], year_range[1])

        # Group by district into {year: value} dicts
        district_data = {}
        for r in rows:
            cdk = r['cdk']
            if cdk not in district_data:
                district_data[cdk] = {"name": r['district_name'], "years": {}}
            district_data[cdk]["years"][r['year']] = r['value']  # type: ignore[index]

        # Major pan-India drought/shock years in this timeframe
        shock_years = [2002, 2004, 2009, 2014, 2015]

        results = []
        for cdk, data in district_data.items():
            year_dict = data["years"]
            if len(year_dict) < 10:
                continue  # Need a solid dataset

            mean_y = sum(year_dict.values()) / len(year_dict)

            shock_drops = []
            recovery_times = []

            for shock_yr in shock_years:
                if shock_yr in year_dict:  # type: ignore[operator]
                    # Pre-shock average (up to 3 years prior)
                    pre_vals = [
                        year_dict[y] for y in [  # type: ignore[index]
                            shock_yr - 3,
                            shock_yr - 2,
                            shock_yr - 1] if y in year_dict]  # type: ignore[operator]
                    if not pre_vals:
                        continue

                    pre_avg = sum(pre_vals) / len(pre_vals)
                    shock_val = year_dict[shock_yr]  # type: ignore[index]

                    # Identify if a localized or systemic shock actually hit
                    # this district (Drop > 10%)
                    if shock_val < pre_avg * 0.9:
                        drop_pct = (pre_avg - shock_val) / pre_avg
                        shock_drops.append(drop_pct)

                        # Calculate recovery time (years to reach 95% of
                        # pre-shock average, cap at 5)
                        recovery_time = 5
                        for i in range(1, 6):
                            check_yr = shock_yr + i
                            if check_yr in year_dict and year_dict[check_yr] >= pre_avg * 0.95:  # type: ignore[operator, index]
                                recovery_time = i
                                break
                        recovery_times.append(recovery_time)

            # Formulate the Resilience Score (0-100)
            if not shock_drops:
                # Survived systemic shocks with <10% drops = Extremely
                # Resilient
                avg_drop = 0.0
                avg_recovery = 0.0
                resilience = 100.0
            else:
                avg_drop = sum(shock_drops) / len(shock_drops)
                avg_recovery = sum(recovery_times) / len(recovery_times)  # type: ignore[operator]

                # Penalty math:
                # - 50% average drop removes 50 points
                # - 5 year average recovery removes 50 points (12.5 per year past 1)
                resilience = 100 - (avg_drop * 100) - \
                    ((avg_recovery - 1) * 12.5)
                resilience = max(0.0, min(100.0, resilience))

            results.append({
                "cdk": cdk,
                "district_name": data["name"],
                "data_points": len(year_dict),
                "avg_yield": round(mean_y, 2),  # type: ignore[call-overload]
                "avg_shock_drop_pct": round(avg_drop * 100, 1),  # type: ignore[call-overload]
                "avg_recovery_years": round(avg_recovery, 1),  # type: ignore[call-overload]
                "resilience_score": round(resilience, 1)  # type: ignore[call-overload]
            })

        # Sort by most resilient (highest score)
        results.sort(key=lambda x: x["resilience_score"], reverse=True)

        # Add ranks
        for i, r in enumerate(results, 1):
            r["rank"] = i

        return results

    # ============================================================
    # YIELD GAP ANALYSIS
    # ============================================================

    @cached(ttl=CacheTTL.ANALYSIS, prefix="yield_gap")
    async def get_yield_gap(
        self,
        state: str,
        crop: str,
        start_year: int = 2000,
        end_year: int = 2020
    ) -> dict[str, Any]:
        """
        Quantifies the yield gap for each district against the state's 90th percentile "frontier".
        Tracks convergence or divergence over the time period.
        """
        query_template = """
             SELECT
                d.district_name,
                m.district_lgd::text as cdk,
                m.year,
                m.value
            FROM agri_metrics m
            JOIN districts d ON m.district_lgd = d.lgd_code
            WHERE UPPER(d.state_name) = UPPER($1)
              AND m.value > 0
              AND m.year BETWEEN $2 AND $3
              AND m.variable_name = $4
            ORDER BY m.year, m.value DESC
        """
        rows = await self._fetch_with_fallback(query_template, crop, "yield", state, start_year, end_year)

        if not rows:
            return {"error": "No data found for the given parameters"}

        # Group by year to compute frontiers
        yearly_data: dict[int, list[tuple[str, str, float]]] = {}
        for r in rows:
            yr = r['year']
            if yr not in yearly_data:
                yearly_data[yr] = []
            yearly_data[yr].append((r['cdk'], r['district_name'], r['value']))

        # Compute frontier (90th percentile) and average yield gap for each
        # year to plot convergence
        convergence_timeline = []
        district_gaps: dict[str, dict[str, Any]] = {}  # Store lifetime gaps for ranking

        for yr, dist_vals in sorted(yearly_data.items()):
            yields = sorted([v[2] for v in dist_vals])
            if not yields:
                continue

            # 90th percentile index
            idx_90 = int(0.9 * len(yields))
            if idx_90 >= len(yields):
                idx_90 = len(yields) - 1

            frontier_yield = yields[idx_90]

            total_gap: float = 0.0
            for cdk, name, yld in dist_vals:
                gap = max(0, frontier_yield - yld)
                total_gap += gap

                if cdk not in district_gaps:
                    district_gaps[cdk] = {
                        "name": name, "gaps": [], "yields": []}
                district_gaps[cdk]["gaps"].append(gap)
                district_gaps[cdk]["yields"].append(yld)

            avg_state_gap = total_gap / len(dist_vals)

            convergence_timeline.append({
                "year": yr,
                "frontier_yield": round(frontier_yield, 2),  # type: ignore[call-overload]
                "state_avg_yield": round(sum(yields) / len(yields), 2),  # type: ignore[call-overload]
                "avg_gap": round(avg_state_gap, 2)  # type: ignore[call-overload]
            })

        # Aggregate district data
        rankings = []
        for cdk, data in district_gaps.items():
            gaps = list(data["gaps"])  # type: ignore[assignment]
            yields = list(data["yields"])  # type: ignore[assignment]
            if not gaps:
                continue
            avg_gap = sum(gaps) / len(gaps)
            avg_yld = sum(yields) / len(yields)

            # Latest gap to show current status
            latest_gap = gaps[-1]

            # Convergence rate (negative means gap is closing -> good)
            n_years = len(gaps)
            gap_trend = 0
            if n_years > 5:
                # Simple linear trend over the gaps
                x = list(range(n_years))
                y = gaps
                sum_x = sum(x)
                sum_y = sum(y)
                sum_xy = sum(x_i * y_i for x_i, y_i in zip(x, y, strict=False))
                sum_xx = sum(x_i * x_i for x_i in x)
                denom = n_years * sum_xx - sum_x * sum_x
                if denom != 0:
                    gap_trend = (n_years * sum_xy - sum_x * sum_y) / denom  # type: ignore[assignment]

            rankings.append({
                "cdk": cdk,
                "district_name": data["name"],
                "avg_gap": round(avg_gap, 2),  # type: ignore[call-overload]
                "latest_gap": round(latest_gap, 2),  # type: ignore[call-overload]
                "avg_yield": round(avg_yld, 2),  # type: ignore[call-overload]
                "gap_trend": round(gap_trend, 2),  # type: ignore[call-overload]
                "status": "Closing" if gap_trend < -1 else "Widening" if gap_trend > 1 else "Stagnant"
            })

        # Sort by largest average gap
        rankings.sort(key=lambda x: x["avg_gap"], reverse=True)

        # Add rank
        for i, r in enumerate(rankings, 1):
            r["rank"] = i

        return {
            "state": state,
            "crop": crop,
            "period": f"{start_year}-{end_year}",
            "convergence_timeline": convergence_timeline,
            "district_rankings": rankings
        }

    # ============================================================
    # POST-SPLIT ECONOMIC SPECIALIZATION
    # ============================================================
    @cached(ttl=CacheTTL.ANALYSIS, prefix="split_spec")
    async def get_post_split_specialization(
        self,
        parent_cdk: str,
        child_cdks: list[str],
        split_year: int
    ) -> dict[str, Any]:
        """
        Compare the crop mix of the parent (pre-split) vs the child (post-split)
        to measure economic specialization or divergence.
        Builds a multi-crop matrix for a radar chart.
        """
        # Focus on top ~8 crops to make the radar chart readable
        target_crops = [
            'wheat',
            'rice',
            'cotton',
            'sugarcane',
            'maize',
            'groundnut',
            'sorghum',
            'pearl_millet']

        # Pre-split period: average of 3 years before split
        pre_start = split_year - 4
        pre_end = split_year - 1

        # Post-split period: average of 3 years after split (give it a few
        # years to stabilize)
        post_start = split_year + 3
        post_end = split_year + 6

        async def get_crop_mix(cdks: list[str], start_yr: int, end_yr: int) -> dict[str, float]:
            if not cdks:
                return {c: 0.0 for c in target_crops}

            cdk_ints = []
            for c in cdks:
                with contextlib.suppress(ValueError):
                    cdk_ints.append(float(c))

            if not cdk_ints:
                return {c: 0.0 for c in target_crops}

            # Use SIMILAR TO or LIKE to match area metrics
            case_statements = []
            for c in target_crops:
                case_statements.append(
                    f"SUM(CASE WHEN variable_name = '{c}_area' THEN value ELSE 0 END) as {c}")

            query = f"""
                SELECT {
                ', '.join(case_statements)},
                       SUM(CASE WHEN variable_name LIKE '%_area' AND variable_name NOT LIKE '%_kharif%' AND variable_name NOT LIKE '%_rabi%' THEN value ELSE 0 END) as total_area
                FROM agri_metrics
                WHERE district_lgd = ANY($1::float[])
                  AND year BETWEEN $2 AND $3
            """

            row = await self.db.fetchrow(query, cdk_ints, start_yr, end_yr)

            res = {}
            if row and row['total_area']:
                total = float(row['total_area'])
                for c in target_crops:
                    val = float(row[c] or 0)
                    # Return share as percentage
                    res[c] = round(  # type: ignore[call-overload]
                        (val / total) * 100,
                        1) if total > 0 else 0.0  # type: ignore[call-overload]
            else:
                for c in target_crops:
                    res[c] = 0.0
            return res

        parent_pre_mix = await get_crop_mix([parent_cdk], pre_start, pre_end)

        children_post_mix = {}
        for cdk in child_cdks:
            if not cdk:
                continue
            mix = await get_crop_mix([cdk], post_start, post_end)

            # Fetch name
            name_row = await self.db.fetchrow("SELECT district_name FROM districts WHERE lgd_code::text = $1", str(cdk))
            name = name_row['district_name'] if name_row else str(cdk)
            children_post_mix[name] = {"cdk": str(cdk), "mix": mix}

        # Parent Name
        p_name_row = await self.db.fetchrow("SELECT district_name FROM districts WHERE lgd_code::text = $1", str(parent_cdk))
        parent_name = p_name_row['district_name'] if p_name_row else str(
            parent_cdk)

        # Calculate divergence score (Euclidean distance of crop vectors)
        import math
        divergence_scores = {}
        for c_name, c_data in children_post_mix.items():
            dist = 0
            for crop in target_crops:
                dist += (parent_pre_mix[crop] - c_data["mix"][crop]) ** 2  # type: ignore[index]
            divergence_scores[c_name] = round(math.sqrt(dist), 1)  # type: ignore[call-overload]

        return {
            "split_year": split_year,
            "crops": target_crops,
            "parent": {
                "name": parent_name,
                "cdk": parent_cdk,
                "pre_mix": parent_pre_mix
            },
            "children": children_post_mix,
            "divergence_scores": divergence_scores
        }
