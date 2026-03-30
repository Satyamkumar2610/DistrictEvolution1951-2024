"""
Crop Diversity Analytics Service.
"""
import contextlib
import math
from dataclasses import dataclass
from typing import Any, TypedDict

from app.cache import CacheTTL, cached  # type: ignore[import]

from .base import BaseAnalyticsService


@dataclass
class CropDiversification:
    """Crop diversification index for a district."""
    cdk: str
    year: int
    herfindahl_index: float
    simpson_index: float
    num_crops: int
    dominant_crop: str
    dominant_share: float
    breakdown: dict[str, float]


class SplitChildMix(TypedDict):
    cdk: str
    mix: dict[str, float]


class CropDiversityService(BaseAnalyticsService):
    """Analytics for crop diversity indices and structural shifts over time."""

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
        rows = await self._fetch("""
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

        total_area = sum(r['area'] for r in rows)
        if total_area == 0:
            return None

        shares = [(r['crop'], r['area'] / total_area) for r in rows]
        hhi = sum(s ** 2 for _, s in shares)
        simpson = 1 - hhi

        dominant_crop, dominant_share = shares[0]
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
        """
        rows = await self._fetch("""
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

        yearly_data: dict[int, dict[str, float]] = {}
        for r in rows:
            yr, crp, area = r['year'], r['crop'], r['area']
            if yr not in yearly_data:
                yearly_data[yr] = {}
            yearly_data[yr][crp] = yearly_data[yr].get(crp, 0) + area

        results = []
        for yr, crops in sorted(yearly_data.items()):
            total_area = sum(crops.values())
            if total_area == 0:
                continue

            sorted_crops = sorted(crops.items(), key=lambda x: x[1], reverse=True)
            top_crops = sorted_crops[:5]
            other_area = sum(area for crp, area in sorted_crops[5:])

            shannon_index: float = 0.0
            shares: dict[str, float] = {}

            for crp, area in top_crops:
                share = area / total_area
                shares[crp] = round(share, 4)
                if share > 0:
                    shannon_index -= share * math.log(share)

            if other_area > 0:
                other_share = other_area / total_area
                shares['other'] = round(other_share, 4)
                if other_share > 0:
                    shannon_index -= other_share * math.log(other_share)

            hhi = sum(s ** 2 for s in shares.values())
            simpson = 1 - hhi

            results.append({
                "year": yr,
                "total_area": round(total_area, 2),
                "shannon_index": round(shannon_index, 4),
                "simpson_index": round(simpson, 4),
                "dominant_crop": top_crops[0][0] if top_crops else "none",
                "dominant_share": round(shares.get(top_crops[0][0], 0) * 100, 1) if top_crops else 0,
                "crop_mix": shares
            })

        return results

    @cached(ttl=CacheTTL.ANALYSIS, prefix="split_spec")
    async def get_post_split_specialization(
        self,
        parent_cdk: str,
        child_cdks: list[str],
        split_year: int
    ) -> dict[str, Any]:
        """
        Compare the crop mix of the parent vs the child to measure economic specialization.
        """
        target_crops = ['wheat', 'rice', 'cotton', 'sugarcane', 'maize', 'groundnut', 'sorghum', 'pearl_millet']
        pre_start, pre_end = split_year - 4, split_year - 1
        post_start, post_end = split_year + 3, split_year + 6

        async def get_crop_mix(cdks: list[str], start_yr: int, end_yr: int) -> dict[str, float]:
            if not cdks:
                return {c: 0.0 for c in target_crops}

            cdk_ints = []
            for c in cdks:
                with contextlib.suppress(ValueError):
                    cdk_ints.append(float(c))

            if not cdk_ints:
                return {c: 0.0 for c in target_crops}

            case_statements = [f"SUM(CASE WHEN variable_name = '{c}_area' THEN value ELSE 0 END) as {c}" for c in target_crops]
            query = f"""
                SELECT {', '.join(case_statements)},
                       SUM(CASE WHEN variable_name LIKE '%_area' AND variable_name NOT LIKE '%_kharif%' AND variable_name NOT LIKE '%_rabi%' THEN value ELSE 0 END) as total_area
                FROM agri_metrics
                WHERE district_lgd = ANY($1::float[])
                  AND year BETWEEN $2 AND $3
            """
            row = await self._fetchrow(query, cdk_ints, start_yr, end_yr)

            res = {}
            if row and row['total_area']:
                total = float(row['total_area'])
                for c in target_crops:
                    val = float(row[c] or 0)
                    res[c] = round((val / total) * 100, 1) if total > 0 else 0.0
            else:
                for c in target_crops:
                    res[c] = 0.0
            return res

        parent_pre_mix = await get_crop_mix([parent_cdk], pre_start, pre_end)

        children_post_mix: dict[str, SplitChildMix] = {}
        for cdk in child_cdks:
            if not cdk:
                continue
            mix = await get_crop_mix([cdk], post_start, post_end)
            name_row = await self._fetchrow("SELECT district_name FROM districts WHERE lgd_code::text = $1", str(cdk))
            name = name_row['district_name'] if name_row else str(cdk)
            children_post_mix[name] = {"cdk": str(cdk), "mix": mix}

        p_name_row = await self._fetchrow("SELECT district_name FROM districts WHERE lgd_code::text = $1", str(parent_cdk))
        parent_name = p_name_row['district_name'] if p_name_row else str(parent_cdk)

        divergence_scores = {}
        for c_name, c_data in children_post_mix.items():
            dist = sum((parent_pre_mix[crop] - c_data["mix"][crop]) ** 2 for crop in target_crops)
            divergence_scores[c_name] = round(math.sqrt(dist), 1)

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
