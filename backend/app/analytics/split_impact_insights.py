"""
Split Impact Insights Module.

Provides advanced analytics for split impact analysis:
- Fragmentation Index
- Child Divergence Score
- Convergence Trend Analysis
- Effect Size (Cohen's d)
- Counterfactual Projection
"""

import math
from dataclasses import dataclass

from app.analytics.statistics import get_analyzer


@dataclass
class FragmentationResult:
    """Result of fragmentation analysis."""
    index: float  # 1/child_count
    child_count: int
    interpretation: str


@dataclass
class DivergenceResult:
    """Result of child divergence analysis."""
    score: float  # CV across children
    interpretation: str
    best_performer: str | None
    best_yield: float
    worst_performer: str | None
    worst_yield: float
    spread: float  # max - min


@dataclass
class ConvergenceResult:
    """Result of convergence trend analysis."""
    trend: str  # 'converging', 'diverging', 'stable', 'insufficient_data'
    rate: float  # Rate of change in divergence score over time
    interpretation: str


@dataclass
class EffectSizeResult:
    """Result of effect size calculation."""
    cohens_d: float
    interpretation: str  # 'small', 'medium', 'large', 'very_large'
    confidence: float  # 0-1


@dataclass
class CounterfactualResult:
    """Result of counterfactual analysis."""
    projected_yield: float
    method: str
    actual_yield: float
    attribution_pct: float  # % of change attributable to split
    interpretation: str


@dataclass
class ChildPerformance:
    """Performance metrics for a single child district."""
    cdk: str
    name: str | None
    mean_yield: float
    cv: float
    cagr: float
    observations: int
    rank: int


@dataclass
class SplitInsights:
    """Complete split impact insights."""
    fragmentation: FragmentationResult
    divergence: DivergenceResult
    convergence: ConvergenceResult
    effect_size: EffectSizeResult
    counterfactual: CounterfactualResult
    children_performance: list[ChildPerformance]
    warnings: list[str]


class SplitImpactInsightsAnalyzer:
    """
    Analyzer for advanced split impact insights.

    Computes:
    - Fragmentation index (1 / number of children)
    - Child divergence score (CV of children's yields)
    - Convergence trend (are children becoming more similar over time?)
    - Effect size (Cohen's d for pre vs post)
    - Counterfactual projection (what would have happened without split?)
    """

    def __init__(self):
        self.stats = get_analyzer()

    def calculate_fragmentation(
        self,
        child_count: int
    ) -> FragmentationResult:
        """
        Calculate fragmentation index.

        Higher index = less fragmented (1.0 = single successor)
        Lower index = more fragmented (0.33 = 3 successors)
        """
        if child_count <= 0:
            return FragmentationResult(
                index=0,
                child_count=0,
                interpretation="No children districts"
            )

        index = 1.0 / child_count

        if child_count == 1:
            interpretation = "No fragmentation - single successor"
        elif child_count == 2:
            interpretation = "Minor fragmentation - binary split"
        elif child_count <= 4:
            interpretation = "Moderate fragmentation"
        else:
            interpretation = f"High fragmentation - {child_count} successors"

        return FragmentationResult(
            index=round(index, 4),
            child_count=child_count,
            interpretation=interpretation
        )

    def calculate_divergence(
        self,
        children_yields: dict[str, float],
        children_names: dict[str, str] | None = None
    ) -> DivergenceResult:
        """
        Calculate divergence score across children.

        Uses coefficient of variation across children's mean yields.
        Higher CV = more inequality between successor districts.
        """
        if not children_yields or len(children_yields) < 2:
            return DivergenceResult(
                score=0,
                interpretation="Insufficient data for divergence analysis",
                best_performer=None,
                best_yield=0,
                worst_performer=None,
                worst_yield=0,
                spread=0
            )

        yields = list(children_yields.values())

        # Calculate CV
        cv = self.stats.coefficient_of_variation(yields)

        # Find best and worst
        sorted_children = sorted(
            children_yields.items(),
            key=lambda x: x[1],
            reverse=True)
        best_cdk, best_yield = sorted_children[0]
        worst_cdk, worst_yield = sorted_children[-1]

        spread = best_yield - worst_yield

        # Interpretation
        if cv < 10:
            interpretation = "Low inequality - children performing similarly"
        elif cv < 25:
            interpretation = "Moderate inequality between successors"
        elif cv < 40:
            interpretation = "High inequality - significant performance gaps"
        else:
            interpretation = "Very high inequality - extreme divergence"

        return DivergenceResult(
            score=round(cv, 2),
            interpretation=interpretation,
            best_performer=best_cdk,
            best_yield=round(best_yield, 2),
            worst_performer=worst_cdk,
            worst_yield=round(worst_yield, 2),
            spread=round(spread, 2)
        )

    def calculate_convergence_trend(
        self,
        yearly_children_data: dict[int, dict[str, float]],
        split_year: int
    ) -> ConvergenceResult:
        """
        Analyze if children are converging or diverging over time.

        Computes CV of children's yields for each year post-split,
        then calculates the trend of that CV.
        """
        if not yearly_children_data or len(yearly_children_data) < 3:
            return ConvergenceResult(
                trend="insufficient_data",
                rate=0,
                interpretation="Need at least 3 post-split years for trend analysis")

        # Calculate CV for each year
        yearly_cvs = {}
        for year, children_data in sorted(yearly_children_data.items()):
            if year < split_year:
                continue
            values = [v for v in children_data.values() if v >= 0]
            if len(values) >= 2:
                yearly_cvs[year] = self.stats.coefficient_of_variation(values)

        if len(yearly_cvs) < 3:
            return ConvergenceResult(
                trend="insufficient_data",
                rate=0,
                interpretation="Insufficient post-split data with multiple children")

        # Calculate trend of CVs
        years = sorted(yearly_cvs.keys())
        cvs = [yearly_cvs[y] for y in years]

        trend_result = self.stats.linear_trend(cvs)

        # Determine trend direction
        if trend_result.significant:
            if trend_result.slope < -0.5:
                trend = "converging"
                interpretation = f"Children are converging (CV decreasing {abs(trend_result.slope):.1f}/year)"
            elif trend_result.slope > 0.5:
                trend = "diverging"
                interpretation = f"Children are diverging (CV increasing {trend_result.slope:.1f}/year)"
            else:
                trend = "stable"
                interpretation = "Children inequality is stable over time"
        else:
            trend = "stable"
            interpretation = "No significant convergence or divergence trend"

        return ConvergenceResult(
            trend=trend,
            rate=round(trend_result.slope, 4),
            interpretation=interpretation
        )

    def calculate_effect_size(
        self,
        pre_values: list[float],
        post_values: list[float]
    ) -> EffectSizeResult:
        """
        Calculate Cohen's d effect size.

        Cohen's d = (mean_post - mean_pre) / pooled_std_dev

        Interpretation:
        - 0.2: Small effect
        - 0.5: Medium effect
        - 0.8: Large effect
        - 1.2+: Very large effect
        """
        if not pre_values or not post_values or len(
                pre_values) < 2 or len(post_values) < 2:
            return EffectSizeResult(
                cohens_d=0,
                interpretation="Insufficient data",
                confidence=0
            )

        mean_pre = self.stats.mean(pre_values)
        mean_post = self.stats.mean(post_values)

        var_pre = self.stats.variance(pre_values)
        var_post = self.stats.variance(post_values)

        n_pre = len(pre_values)
        n_post = len(post_values)

        # Pooled standard deviation
        pooled_var = ((n_pre - 1) * var_pre + (n_post - 1)
                      * var_post) / (n_pre + n_post - 2)
        pooled_std = math.sqrt(pooled_var) if pooled_var > 1e-4 else 1e-2

        cohens_d = (mean_post - mean_pre) / pooled_std

        # Interpretation
        abs_d = abs(cohens_d)
        if abs_d < 0.2:
            interpretation = "Negligible effect"
        elif abs_d < 0.5:
            interpretation = "Small effect"
        elif abs_d < 0.8:
            interpretation = "Medium effect"
        elif abs_d < 1.2:
            interpretation = "Large effect"
        else:
            interpretation = "Very large effect"

        # Simple confidence based on sample size
        total_n = n_pre + n_post
        confidence = min(0.95, 0.5 + (total_n / 50) * 0.45)

        return EffectSizeResult(
            cohens_d=round(cohens_d, 4),
            interpretation=interpretation,
            confidence=round(confidence, 2)
        )

    def calculate_counterfactual(
        self,
        pre_values: list[float],
        pre_years: list[int],
        post_mean: float,
        projection_year: int
    ) -> CounterfactualResult:
        """
        Calculate counterfactual projection - what would have happened without split?

        Uses linear trend extrapolation from pre-split period.
        """
        if not pre_values or len(pre_values) < 3:
            return CounterfactualResult(
                projected_yield=0,
                method="insufficient_data",
                actual_yield=post_mean,
                attribution_pct=0,
                interpretation="Insufficient pre-split data for projection"
            )

        # Fit linear trend to pre-split data
        trend = self.stats.linear_trend(pre_values)

        if not trend.significant:
            # Use mean as projection if no clear trend
            projected = self.stats.mean(pre_values)
            method = "mean_projection"
        else:
            # Extrapolate trend
            last_pre_year = max(pre_years)
            years_ahead = projection_year - last_pre_year
            projected = pre_values[-1] + (trend.slope * years_ahead)
            method = "trend_extrapolation"

        # Calculate attribution
        # What % of the actual change is explained by factors other than trend?
        pre_mean = self.stats.mean(pre_values)

        if pre_mean > 1e-2:
            trend_expected_change = projected - pre_mean
            actual_change = post_mean - pre_mean

            if abs(trend_expected_change) > 0:
                # Attribution = what % change is NOT explained by trend
                unexplained_change = actual_change - trend_expected_change
                attribution_pct = (unexplained_change / pre_mean) * 100
            else:
                attribution_pct = (actual_change / pre_mean) * 100

            # Cap attribution at +/- 999.9% to avoid UI breakage on extreme
            # outliers
            attribution_pct = max(-999.9, min(999.9, attribution_pct))
        else:
            attribution_pct = 0

        # Interpretation
        if abs(attribution_pct) < 5:
            interpretation = "Split had minimal impact - outcome matches trend"
        elif attribution_pct > 10:
            interpretation = f"Split associated with {attribution_pct:.1f}% improvement above trend"
        elif attribution_pct < -10:
            interpretation = f"Split associated with {abs(attribution_pct):.1f}% decline below trend"
        else:
            interpretation = "Split had modest impact on performance trajectory"

        return CounterfactualResult(
            projected_yield=round(projected, 2),
            method=method,
            actual_yield=round(post_mean, 2),
            attribution_pct=round(attribution_pct, 2),
            interpretation=interpretation
        )

    def analyze_child_performance(
        self,
        yearly_data: dict[int, dict[str, dict[str, float]]],
        child_cdks: list[str],
        child_names: dict[str, str] | None = None,
        split_year: int = 0
    ) -> list[ChildPerformance]:
        """
        Analyze individual child district performance post-split.
        """
        children_stats = []

        for cdk in child_cdks:
            # Collect yearly values for this child
            yearly_values = {}
            for year, year_data in yearly_data.items():
                if year >= split_year and cdk in year_data:
                    yld = year_data[cdk].get("yld", 0)
                    if yld > 0:
                        yearly_values[year] = yld

            if not yearly_values:
                continue

            values = list(yearly_values.values())

            mean_yield = self.stats.mean(values)
            cv = self.stats.coefficient_of_variation(
                values) if len(values) >= 2 else 0

            # Calculate CAGR
            if len(values) >= 2:
                cagr = self.stats.cagr(values[0], values[-1], len(values) - 1)
            else:
                cagr = 0

            children_stats.append(ChildPerformance(
                cdk=cdk,
                name=child_names.get(cdk) if child_names else None,
                mean_yield=round(mean_yield, 2),
                cv=round(cv, 2),
                cagr=round(cagr, 2),
                observations=len(values),
                rank=0  # Will be filled after sorting
            ))

        # Assign ranks
        children_stats.sort(key=lambda x: x.mean_yield, reverse=True)
        for i, child in enumerate(children_stats):
            child.rank = i + 1

        return children_stats

    def compute_full_insights(
        self,
        pre_values: list[float],
        pre_years: list[int],
        post_values: list[float],
        split_year: int,
        child_cdks: list[str],
        yearly_children_data: dict[int, dict[str, float]],
        children_mean_yields: dict[str, float],
        child_names: dict[str, str] | None = None,
        yearly_data: dict[int, dict[str, dict[str, float]]] | None = None
    ) -> SplitInsights:
        """
        Compute complete split impact insights.
        """
        warnings = []

        # Fragmentation
        fragmentation = self.calculate_fragmentation(len(child_cdks))

        # Divergence
        divergence = self.calculate_divergence(
            children_mean_yields, child_names)

        # Convergence trend
        convergence = self.calculate_convergence_trend(
            yearly_children_data, split_year)

        # Effect size
        effect_size = self.calculate_effect_size(pre_values, post_values)

        # Counterfactual
        post_mean = self.stats.mean(post_values) if post_values else 0
        projection_year = split_year + 5  # Project 5 years ahead
        counterfactual = self.calculate_counterfactual(
            pre_values, pre_years, post_mean, projection_year)

        # Child performance
        if yearly_data:
            children_performance = self.analyze_child_performance(
                yearly_data, child_cdks, child_names, split_year
            )
        else:
            children_performance = []

        # Add warnings
        if len(pre_values) < 5:
            warnings.append(
                f"Limited pre-split data ({len(pre_values)} years)")
        if len(post_values) < 5:
            warnings.append(
                f"Limited post-split data ({len(post_values)} years)")
        if len(child_cdks) < 2:
            warnings.append(
                "Single successor - divergence analysis not applicable")

        return SplitInsights(
            fragmentation=fragmentation,
            divergence=divergence,
            convergence=convergence,
            effect_size=effect_size,
            counterfactual=counterfactual,
            children_performance=children_performance,
            warnings=warnings
        )


def get_insights_analyzer() -> SplitImpactInsightsAnalyzer:
    """Get a split impact insights analyzer instance."""
    return SplitImpactInsightsAnalyzer()
