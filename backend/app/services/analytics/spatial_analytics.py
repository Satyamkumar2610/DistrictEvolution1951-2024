"""
Spatial and State-wide Analytics Service.
"""
import math
from typing import Any

from app.cache import CacheTTL, cached  # type: ignore[import]
from .base import BaseAnalyticsService


class SpatialAnalyticsService(BaseAnalyticsService):
    """Analytics for state-wide comparisons, rankings, and correlations."""

    @cached(ttl=CacheTTL.ANALYSIS, prefix="crop_corr")
    async def get_crop_correlations(
        self,
        state: str,
        year: int,
        crops: list[str] | None = None
    ) -> dict[str, Any]:
        """Calculate correlation between crop areas/yields across districts."""
        if crops is None:
            crops = ['rice', 'wheat', 'maize', 'groundnut', 'cotton', 'sugarcane']

        crop_data = {}
        for crop in crops:
            query = """
                SELECT m.district_lgd::text as cdk, m.value
                FROM agri_metrics m
                JOIN districts d ON m.district_lgd = d.lgd_code
                WHERE UPPER(d.state_name) = UPPER($1)
                  AND m.year = $2
                  AND m.value > 0
                  AND m.variable_name = $3
            """
            rows = await self._fetch_with_fallback(query, crop, "yield", state, year)
            crop_data[crop] = {r['cdk']: r['value'] for r in rows}

        correlations: dict[str, dict[str, float | None]] = {}
        for _i, crop1 in enumerate(crops):
            correlations[crop1] = {}
            for crop2 in crops:
                if crop1 == crop2:
                    correlations[crop1][crop2] = 1.0
                else:
                    common = set(crop_data[crop1].keys()) & set(crop_data[crop2].keys())
                    if len(common) < 3:
                        correlations[crop1][crop2] = None
                        continue

                    vals1 = [crop_data[crop1][cdk] for cdk in common]
                    vals2 = [crop_data[crop2][cdk] for cdk in common]

                    mean1, mean2 = sum(vals1) / len(vals1), sum(vals2) / len(vals2)
                    cov = sum((v1 - mean1) * (v2 - mean2) for v1, v2 in zip(vals1, vals2))
                    std1 = math.sqrt(sum((v - mean1) ** 2 for v in vals1))
                    std2 = math.sqrt(sum((v - mean2) ** 2 for v in vals2))

                    if std1 > 0 and std2 > 0:
                        corr = cov / (std1 * std2)
                        correlations[crop1][crop2] = round(corr, 3)
                    else:
                        correlations[crop1][crop2] = None

        return {
            'state': state,
            'year': year,
            'crops': crops,
            'correlations': correlations
        }

    @cached(ttl=CacheTTL.ANALYSIS, prefix="dist_rank")
    async def get_district_rankings(
        self,
        state: str,
        crop: str,
        year: int,
        metric: str = 'yield'
    ) -> list[dict[str, Any]]:
        """Rank districts by crop performance."""
        query = """
            SELECT m.district_lgd::text as cdk, d.district_name, m.value
            FROM agri_metrics m
            JOIN districts d ON m.district_lgd = d.lgd_code
            WHERE UPPER(d.state_name) = UPPER($1)
              AND m.year = $2
              AND m.value > 0
              AND m.variable_name = $3
            ORDER BY m.value DESC
        """
        rows = await self._fetch_with_fallback(query, crop, metric, state, year)

        return [
            {'rank': i, 'cdk': r['cdk'], 'district': r['district_name'], 'value': round(r['value'], 2)}
            for i, r in enumerate(rows, 1)
        ]

    @cached(ttl=CacheTTL.ANALYSIS, prefix="season_comp")
    async def get_seasonal_comparison(
        self,
        cdk: str,
        crop: str,
        year: int
    ) -> dict[str, Any]:
        """Compare Kharif vs Rabi season performance."""
        kharif = await self.db.fetchrow("""
            SELECT value FROM agri_metrics
            WHERE district_lgd::text = $1 AND year = $2 AND variable_name LIKE $3
        """, cdk, year, f"{crop}_yield_kharif")

        rabi = await self.db.fetchrow("""
            SELECT value FROM agri_metrics
            WHERE district_lgd::text = $1 AND year = $2 AND variable_name LIKE $3
        """, cdk, year, f"{crop}_yield_rabi")

        kharif_val = kharif['value'] if kharif else None
        rabi_val = rabi['value'] if rabi else None

        return {
            'cdk': cdk, 
            'crop': crop, 
            'year': year, 
            'kharif_yield': round(kharif_val, 2) if kharif_val else None, 
            'rabi_yield': round(rabi_val, 2) if rabi_val else None, 
            'dominant_season': 'kharif' if (kharif_val or 0) > (rabi_val or 0) else 'rabi'
        }

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
        if year_range is None: year_range = [1990, 2020]
        query = """
            SELECT d.district_name, m.district_lgd::text as cdk, m.year, m.value
            FROM agri_metrics m
            JOIN districts d ON m.district_lgd = d.lgd_code
            WHERE UPPER(d.state_name) = UPPER($1)
              AND m.value > 0
              AND m.year BETWEEN $2 AND $3
              AND m.variable_name = $4
            ORDER BY m.district_lgd, m.year
        """
        rows = await self._fetch_with_fallback(query, crop, "yield", state, year_range[0], year_range[1])

        district_data = {}
        for r in rows:
            cdk = r['cdk']
            if cdk not in district_data:
                district_data[cdk] = {"name": r['district_name'], "years": {}}
            district_data[cdk]["years"][r['year']] = r['value']

        shock_years = [2002, 2004, 2009, 2014, 2015]
        results = []

        for cdk, data in district_data.items():
            year_dict = data["years"]
            if len(year_dict) < 10: continue

            mean_y = sum(year_dict.values()) / len(year_dict)
            shock_drops, recovery_times = [], []

            for shock_yr in shock_years:
                if shock_yr in year_dict:
                    pre_vals = [year_dict[y] for y in [shock_yr - 3, shock_yr - 2, shock_yr - 1] if y in year_dict]
                    if not pre_vals: continue

                    pre_avg = sum(pre_vals) / len(pre_vals)
                    shock_val = year_dict[shock_yr]

                    if shock_val < pre_avg * 0.9:
                        shock_drops.append((pre_avg - shock_val) / pre_avg)
                        recovery_time = 5
                        for i in range(1, 6):
                            check_yr = shock_yr + i
                            if check_yr in year_dict and year_dict[check_yr] >= pre_avg * 0.95:
                                recovery_time = i
                                break
                        recovery_times.append(recovery_time)

            if not shock_drops:
                resilience, avg_drop, avg_recovery = 100.0, 0.0, 0.0
            else:
                avg_drop = sum(shock_drops) / len(shock_drops)
                avg_recovery = sum(recovery_times) / len(recovery_times)
                resilience = max(0.0, min(100.0, 100 - (avg_drop * 100) - ((avg_recovery - 1) * 12.5)))

            results.append({
                "cdk": cdk,
                "district_name": data["name"],
                "data_points": len(year_dict),
                "avg_yield": round(mean_y, 2),
                "avg_shock_drop_pct": round(avg_drop * 100, 1),
                "avg_recovery_years": round(avg_recovery, 1),
                "resilience_score": round(resilience, 1)
            })

        results.sort(key=lambda x: x["resilience_score"], reverse=True)
        for i, r in enumerate(results, 1): r["rank"] = i
        return results
