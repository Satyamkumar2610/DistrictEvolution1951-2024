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
        years_after: int = 5
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

        before_yields = [r['value'] for r in before_data]
        before_avg = sum(before_yields) / len(before_yields) if before_yields else 0

        after_results: dict[str, dict[str, Any]] = {}
        for child_cdk in child_cdks:
            after_data = await self._fetch_with_fallback(
                query_template, crop, "yield", child_cdk, split_year, split_year + years_after
            )

            after_yields = [r['value'] for r in after_data]
            after_results[child_cdk] = {'yields': after_yields, 'avg': sum(after_yields) / len(after_yields) if after_yields else 0}

        all_after_avgs = [float(v['avg']) for v in after_results.values() if v['avg'] > 0]
        after_avg = sum(all_after_avgs) / len(all_after_avgs) if all_after_avgs else 0

        absolute_change = after_avg - before_avg
        percent_change = (absolute_change / before_avg * 100) if before_avg > 0 else 0

        return {
            'parent_cdk': parent_cdk,
            'child_cdks': child_cdks,
            'split_year': split_year,
            'crop': crop,
            'before': {
                'years': [r['year'] for r in before_data],
                'yields': before_yields,
                'average': round(before_avg, 2)
            },
            'after': {
                'by_child': after_results,
                'combined_average': round(after_avg, 2)
            },
            'impact': {
                'absolute_change': round(absolute_change, 2),
                'percent_change': round(percent_change, 2),
                'assessment': 'positive' if percent_change > 5 else 'negative' if percent_change < -5 else 'neutral'
            }
        }
