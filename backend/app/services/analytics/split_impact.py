"""
Split Impact Analysis Service.
"""

from typing import Any

from app.cache import CacheTTL, cached  # type: ignore[import]

from .base import BaseAnalyticsService


class SplitImpactService(BaseAnalyticsService):
    """Analytics for before/after comparison on district splits."""

    @cached(ttl=CacheTTL.SPLIT_EVENTS, prefix="split_impact")
    async def get_split_impact(
        self,
        parent_cdk: str,
        child_cdks: list[str],
        split_year: int,
        crop: str,
        years_before: int = 5,
        years_after: int = 5,
    ) -> dict[str, Any]:
        """
        Compare agricultural performance before/after district split.
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
        before_data = await self._fetch_with_fallback(
            query_template, crop, "yield", parent_cdk, split_year - years_before, split_year - 1
        )

        before_yields = [r["value"] for r in before_data]
        before_avg = sum(before_yields) / len(before_yields) if before_yields else 0

        after_results: dict[str, dict[str, Any]] = {}
        for child_cdk in child_cdks:
            after_data = await self._fetch_with_fallback(
                query_template, crop, "yield", child_cdk, split_year, split_year + years_after
            )

            after_yields = [r["value"] for r in after_data]
            after_results[child_cdk] = {
                "yields": after_yields,
                "avg": sum(after_yields) / len(after_yields) if after_yields else 0,
            }

        all_after_avgs = [float(v["avg"]) for v in after_results.values() if v["avg"] > 0]
        after_avg = sum(all_after_avgs) / len(all_after_avgs) if all_after_avgs else 0

        absolute_change = after_avg - before_avg
        percent_change = (absolute_change / before_avg * 100) if before_avg > 0 else 0

        return {
            "parent_cdk": parent_cdk,
            "child_cdks": child_cdks,
            "split_year": split_year,
            "crop": crop,
            "before": {
                "years": [r["year"] for r in before_data],
                "yields": before_yields,
                "average": round(before_avg, 2),
            },
            "after": {"by_child": after_results, "combined_average": round(after_avg, 2)},
            "impact": {
                "absolute_change": round(absolute_change, 2),
                "percent_change": round(percent_change, 2),
                "assessment": "positive" if percent_change > 5 else "negative" if percent_change < -5 else "neutral",
            },
        }

    @cached(ttl=CacheTTL.SPLIT_EVENTS, prefix="split_specialization")
    async def get_split_specialization(
        self,
        parent_cdk: str,
        child_cdks: list[str],
        split_year: int,
    ) -> dict[str, Any]:
        """
        Analyze crop specialization divergence after a district split.

        Compares the parent's pre-split crop mix with each child's post-split
        crop mix to identify specialization patterns.
        """
        # Crops to check
        crops = ["rice", "wheat", "maize", "soyabean", "groundnut", "cotton", "pearl_millet", "sorghum", "chickpea"]

        # --- Parent pre-split crop area mix ---
        parent_mix: dict[str, float] = {}
        for crop in crops:
            rows = await self._fetch_with_fallback(
                """
                SELECT AVG(value) as avg_val
                FROM agri_metrics
                WHERE district_lgd::text = $1
                  AND year BETWEEN $2 AND $3
                  AND value > 0
                  AND variable_name = $4
                """,
                crop,
                "area",
                parent_cdk,
                split_year - 5,
                split_year - 1,
            )
            if rows and rows[0]["avg_val"] is not None:
                parent_mix[crop] = float(rows[0]["avg_val"])

        # Normalise parent mix to proportions
        parent_total = sum(parent_mix.values()) or 1.0
        parent_proportions = {c: v / parent_total for c, v in parent_mix.items()}

        # --- Children post-split crop area mixes ---
        children_mixes: dict[str, dict[str, float]] = {}
        for child_cdk in child_cdks:
            child_mix: dict[str, float] = {}
            for crop in crops:
                rows = await self._fetch_with_fallback(
                    """
                    SELECT AVG(value) as avg_val
                    FROM agri_metrics
                    WHERE district_lgd::text = $1
                      AND year BETWEEN $2 AND $3
                      AND value > 0
                      AND variable_name = $4
                    """,
                    crop,
                    "area",
                    child_cdk,
                    split_year,
                    split_year + 5,
                )
                if rows and rows[0]["avg_val"] is not None:
                    child_mix[crop] = float(rows[0]["avg_val"])
            children_mixes[child_cdk] = child_mix

        # Normalise children mixes
        children_proportions: dict[str, dict[str, float]] = {}
        for cdk, mix in children_mixes.items():
            total = sum(mix.values()) or 1.0
            children_proportions[cdk] = {c: v / total for c, v in mix.items()}

        # --- Divergence scores (cosine distance from parent) ---
        divergence_scores: dict[str, float] = {}
        for cdk, child_props in children_proportions.items():
            # Compute cosine similarity then convert to distance
            all_crops = set(parent_proportions.keys()) | set(child_props.keys())
            dot = sum(parent_proportions.get(c, 0) * child_props.get(c, 0) for c in all_crops)
            mag_p = sum(v**2 for v in parent_proportions.values()) ** 0.5
            mag_c = sum(v**2 for v in child_props.values()) ** 0.5
            if mag_p > 0 and mag_c > 0:
                cosine_sim = dot / (mag_p * mag_c)
                divergence_scores[cdk] = round(1.0 - cosine_sim, 4)
            else:
                divergence_scores[cdk] = 1.0

        # Get parent name
        name_row = await self._fetchrow(
            "SELECT name FROM districts WHERE district_lgd::text = $1 OR cdk = $1",
            parent_cdk,
        )
        parent_name = name_row["name"] if name_row else parent_cdk

        return {
            "split_year": split_year,
            "crops": crops,
            "parent": {
                "name": parent_name,
                "cdk": parent_cdk,
                "pre_mix": {k: round(v, 4) for k, v in parent_proportions.items()},
            },
            "children": {
                cdk: {"cdk": cdk, "mix": {k: round(v, 4) for k, v in props.items()}}
                for cdk, props in children_proportions.items()
            },
            "divergence_scores": divergence_scores,
        }
