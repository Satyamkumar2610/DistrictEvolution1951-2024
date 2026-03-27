"""
Impact Analyzer: Compare pre/post split periods with statistical rigor.
"""
from dataclasses import dataclass

from app.analytics.harmonizer import HarmonizedPoint
from app.analytics.statistics import get_analyzer
from app.schemas.common import ImpactStats, PeriodStats, UncertaintyBounds


@dataclass
class ImpactResult:
    """Complete impact analysis result."""
    pre_stats: PeriodStats
    post_stats: PeriodStats
    impact: ImpactStats
    split_year: int
    warnings: list[str]


class ImpactAnalyzer:
    """
    Analyzes the impact of administrative boundary changes on metrics.

    Compares pre-split and post-split periods to quantify:
    - Changes in mean performance
    - Changes in stability (CV)
    - Growth dynamics (CAGR)
    - Divergence with uncertainty bounds
    """

    def __init__(self, min_observations: int = 3):
        """
        Args:
            min_observations: Minimum data points required per period
        """
        self.min_observations = min_observations
        self.stats = get_analyzer()

    def analyze(
        self,
        timeline: list[HarmonizedPoint],
        split_year: int,
        uncertainty: UncertaintyBounds | None = None,
    ) -> ImpactResult:
        """
        Perform impact analysis on a harmonized timeline.

        Args:
            timeline: Merged pre/post timeline with values
            split_year: Year of administrative change
            uncertainty: Optional pre-computed uncertainty bounds

        Returns:
            ImpactResult with statistics and warnings
        """
        warnings = []

        # Split into pre and post periods
        pre_values = [p.value for p in timeline if p.year < split_year]
        post_values = [p.value for p in timeline if p.year >= split_year]

        # Check data sufficiency
        if len(pre_values) < self.min_observations:
            warnings.append(
                f"Pre-split period has only {len(pre_values)} observations "
                f"(minimum recommended: {self.min_observations})"
            )

        if len(post_values) < self.min_observations:
            warnings.append(
                f"Post-split period has only {len(post_values)} observations "
                f"(minimum recommended: {self.min_observations})"
            )

        # Calculate period statistics
        pre_stats = self._calculate_period_stats(pre_values)
        post_stats = self._calculate_period_stats(post_values)

        # Calculate impact
        impact = self._calculate_impact(pre_stats, post_stats, uncertainty)

        return ImpactResult(
            pre_stats=pre_stats,
            post_stats=post_stats,
            impact=impact,
            split_year=split_year,
            warnings=warnings,
        )

    def _calculate_period_stats(self, values: list[float]) -> PeriodStats:
        """Calculate statistics for a single period."""
        if not values:
            return PeriodStats(
                mean=0,
                variance=0,
                cv=0,
                cagr=0,
                n_observations=0,
            )

        # Calculate CAGR
        cagr = 0
        if len(values) >= 2 and values[0] > 0 and values[-1] > 0:
            cagr = self.stats.cagr(values[0], values[-1], len(values) - 1)

        return PeriodStats(
            mean=self.stats.mean(values),
            variance=self.stats.variance(values),
            cv=self.stats.coefficient_of_variation(values),
            cagr=cagr,
            n_observations=len(values),
        )

    def _calculate_impact(
        self,
        pre: PeriodStats,
        post: PeriodStats,
        uncertainty: UncertaintyBounds | None = None,
    ) -> ImpactStats:
        """Calculate comparative impact between periods."""
        absolute_change = post.mean - pre.mean

        pct_change = absolute_change / pre.mean * 100 if pre.mean != 0 else 0 if post.mean == 0 else 100

        return ImpactStats(
            absolute_change=absolute_change,
            pct_change=pct_change,
            uncertainty=uncertainty,
        )

    def analyze_from_values(
        self,
        pre_values: list[float],
        post_values: list[float],
        split_year: int,
    ) -> ImpactResult:
        """
        Convenience method to analyze from raw value lists.

        Args:
            pre_values: Pre-split period values
            post_values: Post-split period values
            split_year: Year of split

        Returns:
            ImpactResult
        """
        warnings = []

        if len(pre_values) < self.min_observations:
            warnings.append(
                f"Pre-split period has only {len(pre_values)} observations"
            )

        if len(post_values) < self.min_observations:
            warnings.append(
                f"Post-split period has only {len(post_values)} observations"
            )

        pre_stats = self._calculate_period_stats(pre_values)
        post_stats = self._calculate_period_stats(post_values)
        impact = self._calculate_impact(pre_stats, post_stats)

        return ImpactResult(
            pre_stats=pre_stats,
            post_stats=post_stats,
            impact=impact,
            split_year=split_year,
            warnings=warnings,
        )
