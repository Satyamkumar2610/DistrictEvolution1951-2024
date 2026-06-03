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
    plain_english: str = ""


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
    plain_english: str = ""


@dataclass
class ConvergenceResult:
    """Result of convergence trend analysis."""

    trend: str  # 'converging', 'diverging', 'stable', 'insufficient_data'
    rate: float  # Rate of change in divergence score over time
    interpretation: str
    plain_english: str = ""


@dataclass
class EffectSizeResult:
    """Result of effect size calculation."""

    cohens_d: float
    interpretation: str  # 'small', 'medium', 'large', 'very_large'
    confidence: float  # 0-1
    plain_english: str = ""


@dataclass
class CounterfactualResult:
    """Result of counterfactual analysis."""

    projected_yield: float
    method: str
    actual_yield: float
    attribution_pct: float  # % of change attributable to split
    interpretation: str
    plain_english: str = ""


@dataclass
class MaupZoningResult:
    """Result of MAUP Zoning Sensitivity analysis."""

    divergence_score: float
    interpretation: str
    is_sensitive: bool
    plain_english: str = ""


@dataclass
class MaupScaleResult:
    """Result of MAUP Scale Effect analysis."""

    variance_difference: float
    interpretation: str
    is_smoothing: bool
    plain_english: str = ""


@dataclass
class MaupInsights:
    """Complete MAUP reliability insights."""

    zoning: MaupZoningResult
    scale: MaupScaleResult
    overall_reliability: str


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
    plain_english: str = ""


@dataclass
class SplitInsights:
    """Complete split impact insights."""

    fragmentation: FragmentationResult
    divergence: DivergenceResult
    convergence: ConvergenceResult
    effect_size: EffectSizeResult
    counterfactual: CounterfactualResult
    maup: MaupInsights
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

    def calculate_fragmentation(self, child_count: int) -> FragmentationResult:
        """
        Calculate fragmentation index.

        Higher index = less fragmented (1.0 = single successor)
        Lower index = more fragmented (0.33 = 3 successors)
        """
        if child_count <= 0:
            return FragmentationResult(index=0, child_count=0, interpretation="No children districts")

        index = 1.0 / child_count

        if child_count == 1:
            interpretation = "No fragmentation - single successor"
            plain = "The district was renamed or had a single successor — no splitting occurred."
        elif child_count == 2:
            interpretation = "Minor fragmentation - binary split"
            plain = "The district was split into 2 parts. This is the most common type of split."
        elif child_count <= 4:
            interpretation = "Moderate fragmentation"
            plain = f"The district was broken into {child_count} parts, which is moderately complex."
        else:
            interpretation = f"High fragmentation - {child_count} successors"
            plain = f"The district was heavily fragmented into {child_count} new districts. Reconstruction quality may suffer."

        return FragmentationResult(index=round(index, 4), child_count=child_count, interpretation=interpretation, plain_english=plain)

    def calculate_divergence(
        self, children_yields: dict[str, float], children_names: dict[str, str] | None = None
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
                spread=0,
            )

        yields = list(children_yields.values())

        # Calculate CV
        cv = self.stats.coefficient_of_variation(yields)

        # Find best and worst
        sorted_children = sorted(children_yields.items(), key=lambda x: x[1], reverse=True)
        best_cdk, best_yield = sorted_children[0]
        worst_cdk, worst_yield = sorted_children[-1]

        spread = best_yield - worst_yield

        # Interpretation
        if cv < 10:
            interpretation = "Low inequality - children performing similarly"
            plain = "After the split, all successor districts are performing at similar yield levels."
        elif cv < 25:
            interpretation = "Moderate inequality between successors"
            plain = f"There is a moderate gap of {round(spread, 0)} kg/ha between the best and worst performing successor districts."
        elif cv < 40:
            interpretation = "High inequality - significant performance gaps"
            plain = f"Significant inequality: the best successor yields {round(spread, 0)} kg/ha more than the worst. The split may have created winners and losers."
        else:
            interpretation = "Very high inequality - extreme divergence"
            plain = f"Extreme inequality among successors. One district yields {round(spread, 0)} kg/ha more than another — the split created very unequal outcomes."

        return DivergenceResult(
            score=round(cv, 2),
            interpretation=interpretation,
            best_performer=best_cdk,
            best_yield=round(best_yield, 2),
            worst_performer=worst_cdk,
            worst_yield=round(worst_yield, 2),
            spread=round(spread, 2),
            plain_english=plain,
        )

    def calculate_convergence_trend(
        self, yearly_children_data: dict[int, dict[str, float]], split_year: int
    ) -> ConvergenceResult:
        """
        Analyze if children are converging or diverging over time.

        Computes CV of children's yields for each year post-split,
        then calculates the trend of that CV.
        """
        if not yearly_children_data or len(yearly_children_data) < 3:
            return ConvergenceResult(
                trend="insufficient_data", rate=0, interpretation="Need at least 3 post-split years for trend analysis"
            )

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
                trend="insufficient_data", rate=0, interpretation="Insufficient post-split data with multiple children"
            )

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

        return ConvergenceResult(trend=trend, rate=round(trend_result.slope, 4), interpretation=interpretation)

    def calculate_effect_size(self, pre_values: list[float], post_values: list[float]) -> EffectSizeResult:
        """
        Calculate Cohen's d effect size.

        Cohen's d = (mean_post - mean_pre) / pooled_std_dev

        Interpretation:
        - 0.2: Small effect
        - 0.5: Medium effect
        - 0.8: Large effect
        - 1.2+: Very large effect
        """
        if not pre_values or not post_values or len(pre_values) < 2 or len(post_values) < 2:
            return EffectSizeResult(cohens_d=0, interpretation="Insufficient data", confidence=0)

        mean_pre = self.stats.mean(pre_values)
        mean_post = self.stats.mean(post_values)

        var_pre = self.stats.variance(pre_values)
        var_post = self.stats.variance(post_values)

        n_pre = len(pre_values)
        n_post = len(post_values)

        # Pooled standard deviation
        pooled_var = ((n_pre - 1) * var_pre + (n_post - 1) * var_post) / (n_pre + n_post - 2)
        pooled_std = math.sqrt(pooled_var) if pooled_var > 1e-4 else 1e-2

        cohens_d = (mean_post - mean_pre) / pooled_std

        # Interpretation with plain english
        abs_d = abs(cohens_d)
        direction = "higher" if cohens_d > 0 else "lower"
        if abs_d < 0.2:
            interpretation = "Negligible effect"
            plain = "The split had virtually no measurable effect on yields."
        elif abs_d < 0.5:
            interpretation = "Small effect"
            plain = f"Yields are slightly {direction} after the split, but the difference is small relative to normal year-to-year variation."
        elif abs_d < 0.8:
            interpretation = "Medium effect"
            plain = f"Yields are noticeably {direction} after the split — the change is meaningful and exceeds typical annual fluctuations."
        elif abs_d < 1.2:
            interpretation = "Large effect"
            plain = f"The split is associated with a large {direction} shift in yields that clearly stands out from historical variation."
        else:
            interpretation = "Very large effect"
            plain = f"Yields shifted dramatically {direction} after the split — this is an unusually large change."

        # Proper confidence: SE of Cohen's d ≈ sqrt((n1+n2)/(n1*n2) + d²/(2*(n1+n2)))
        se_d = math.sqrt((n_pre + n_post) / (n_pre * n_post) + (cohens_d**2) / (2 * (n_pre + n_post)))
        # 95% CI: d ± 1.96 * SE; confidence = 1 if CI doesn't cross 0
        ci_lower = cohens_d - 1.96 * se_d
        ci_upper = cohens_d + 1.96 * se_d
        # Confidence as probability the true effect is non-zero (CI doesn't cross 0)
        confidence = 0.95 if (ci_lower > 0 or ci_upper < 0) else round(min(0.9, abs(cohens_d / se_d) / 1.96 * 0.5 + 0.4), 2) if se_d > 0 else 0.5

        return EffectSizeResult(
            cohens_d=round(cohens_d, 4), interpretation=interpretation, confidence=round(confidence, 2), plain_english=plain
        )

    def calculate_counterfactual(
        self, pre_values: list[float], pre_years: list[int], post_mean: float, projection_year: int
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
                interpretation="Insufficient pre-split data for projection",
            )

        # Fit linear trend to pre-split data
        trend = self.stats.linear_trend(pre_values)

        if not trend.significant:
            # Use mean as projection if no clear trend
            projected = self.stats.mean(pre_values)
            method = "mean_projection"
        else:
            # Extrapolate from the FITTED endpoint (not raw last value)
            # This avoids outlier contamination from drought/flood years
            n = len(pre_values)
            fitted_endpoint = trend.intercept + trend.slope * (n - 1)
            last_pre_year = max(pre_years)
            years_ahead = projection_year - last_pre_year
            projected = fitted_endpoint + (trend.slope * years_ahead)
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

        # Interpretation with plain english
        if abs(attribution_pct) < 5:
            interpretation = "Split had minimal impact - outcome matches trend"
            plain = f"Yields after the split ({round(post_mean, 0)} kg/ha) are close to what we'd expect ({round(projected, 0)} kg/ha) had the split never happened. The split itself didn't significantly change outcomes."
        elif attribution_pct > 10:
            interpretation = f"Split associated with {attribution_pct:.1f}% improvement above trend"
            plain = f"Actual post-split yields ({round(post_mean, 0)} kg/ha) are {attribution_pct:.1f}% higher than the {round(projected, 0)} kg/ha we'd expect without the split. This suggests the reorganisation may have had a positive effect."
        elif attribution_pct < -10:
            interpretation = f"Split associated with {abs(attribution_pct):.1f}% decline below trend"
            plain = f"Actual post-split yields ({round(post_mean, 0)} kg/ha) are {abs(attribution_pct):.1f}% lower than the {round(projected, 0)} kg/ha projected without the split. The reorganisation may have disrupted performance."
        else:
            interpretation = "Split had modest impact on performance trajectory"
            plain = f"There is a small difference between actual ({round(post_mean, 0)} kg/ha) and projected ({round(projected, 0)} kg/ha) yields. The split's impact is modest."

        return CounterfactualResult(
            projected_yield=round(projected, 2),
            method=method,
            actual_yield=round(post_mean, 2),
            attribution_pct=round(attribution_pct, 2),
            interpretation=interpretation,
            plain_english=plain,
        )

    def analyze_child_performance(
        self,
        yearly_data: dict[int, dict[str, dict[str, float]]],
        child_cdks: list[str],
        child_names: dict[str, str] | None = None,
        split_year: int = 0,
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
            cv = self.stats.coefficient_of_variation(values) if len(values) >= 2 else 0

            # Calculate CAGR
            cagr = self.stats.cagr(values[0], values[-1], len(values) - 1) if len(values) >= 2 else 0

            # Generate plain english interpretation
            direction = "growing" if cagr > 0 else "declining" if cagr < 0 else "stable"
            volatility = "highly volatile" if cv > 30 else "moderately volatile" if cv > 15 else "stable"
            dist_name = child_names.get(cdk, cdk) if child_names else cdk
            plain = f"{dist_name} has a post-split mean yield of {round(mean_yield, 0)} kg/ha. It is {direction} over time (CAGR: {round(cagr, 1)}%) and its year-to-year performance is {volatility}."

            children_stats.append(
                ChildPerformance(
                    cdk=cdk,
                    name=child_names.get(cdk) if child_names else None,
                    mean_yield=round(mean_yield, 2),
                    cv=round(cv, 2),
                    cagr=round(cagr, 2),
                    observations=len(values),
                    rank=0,  # Will be filled after sorting
                    plain_english=plain,
                )
            )

        # Assign ranks
        children_stats.sort(key=lambda x: x.mean_yield, reverse=True)
        for i, child in enumerate(children_stats):
            child.rank = i + 1

        return children_stats

    def calculate_zoning_sensitivity(
        self, area_weighted_values: list[float], equal_split_values: list[float]
    ) -> MaupZoningResult:
        """Calculate divergence between area_weighted and equal_split reconstructions."""
        if not area_weighted_values or not equal_split_values or len(area_weighted_values) != len(equal_split_values):
            return MaupZoningResult(
                divergence_score=0.0, interpretation="Insufficient data for zoning analysis", is_sensitive=False
            )

        differences = [abs(a - e) for a, e in zip(area_weighted_values, equal_split_values, strict=False)]
        mean_diff = sum(differences) / len(differences)
        mean_area = sum(area_weighted_values) / len(area_weighted_values)

        divergence_pct = mean_diff / mean_area * 100 if mean_area > 0 else 0.0

        is_sensitive = divergence_pct > 10.0

        if divergence_pct < 2.0:
            interp = "Robust against MAUP zoning effect"
            plain = "The results are very reliable — they don't change much regardless of how we combine the districts."
        elif divergence_pct < 10.0:
            interp = "Moderate sensitivity to aggregation boundaries"
            plain = "The results are mostly reliable, but changing how we group the districts changes the outcome slightly."
        else:
            interp = "High MAUP zoning risk: Timeline is highly sensitive to the spatial weighting method"
            plain = "Warning: The results are highly sensitive to how we group the new districts. The trends shown may be artificial effects of boundary changes rather than real agricultural changes."

        return MaupZoningResult(
            divergence_score=round(divergence_pct, 2), interpretation=interp, is_sensitive=is_sensitive, plain_english=plain
        )

    def calculate_scale_effect(self, pre_variance: float, children_pooled_variance: float) -> MaupScaleResult:
        """Compare variance before split vs pooled variance of children."""
        if pre_variance <= 0 or children_pooled_variance <= 0:
            return MaupScaleResult(
                variance_difference=0.0, interpretation="Insufficient variance data", is_smoothing=False
            )

        variance_diff_pct = ((children_pooled_variance - pre_variance) / pre_variance) * 100

        is_smoothing = variance_diff_pct > 20.0

        if is_smoothing:
            interp = "High MAUP scale effect: Parent district suppressed local variance"
            plain = "The old large district hid a lot of extreme high and low yields. The new smaller districts show much more variation."
        elif variance_diff_pct < -20.0:
            interp = "Inverse scale effect: Parent variance exceeded local variance"
            plain = "The new districts actually show less variation in yields than the old combined district did."
        else:
            interp = "Stable scale variance across split"
            plain = "The split didn't artificially change how much variation we see in the crop yields."

        return MaupScaleResult(
            variance_difference=round(variance_diff_pct, 2), interpretation=interp, is_smoothing=is_smoothing, plain_english=plain
        )

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
        yearly_data: dict[int, dict[str, dict[str, float]]] | None = None,
        equal_split_values: list[float] | None = None,
        pre_variance: float = 0.0,
        children_pooled_variance: float = 0.0,
    ) -> SplitInsights:
        """
        Compute complete split impact insights.
        """
        warnings = []

        # Fragmentation
        fragmentation = self.calculate_fragmentation(len(child_cdks))

        # Divergence
        divergence = self.calculate_divergence(children_mean_yields, child_names)

        # Convergence trend
        convergence = self.calculate_convergence_trend(yearly_children_data, split_year)

        # Effect size
        effect_size = self.calculate_effect_size(pre_values, post_values)

        # Counterfactual — project to midpoint of actual post-split data
        post_mean = self.stats.mean(post_values) if post_values else 0
        if pre_years and post_values:
            # Use the actual midpoint of post-split data, not a fixed +5
            last_pre = max(pre_years)
            n_post = len(post_values)
            projection_year = last_pre + max(1, n_post // 2)
        else:
            projection_year = split_year + 5
        counterfactual = self.calculate_counterfactual(pre_values, pre_years, post_mean, projection_year)

        # Child performance
        if yearly_data:
            children_performance = self.analyze_child_performance(yearly_data, child_cdks, child_names, split_year)
        else:
            children_performance = []

        # MAUP Insights
        zoning = self.calculate_zoning_sensitivity(post_values, equal_split_values or [])
        scale = self.calculate_scale_effect(pre_variance, children_pooled_variance)

        if zoning.is_sensitive and scale.is_smoothing:
            overall = "High vulnerability to MAUP effects"
        elif zoning.is_sensitive or scale.is_smoothing:
            overall = "Moderate vulnerability to MAUP effects"
        else:
            overall = "Robust to MAUP scale and zoning effects"

        maup = MaupInsights(zoning=zoning, scale=scale, overall_reliability=overall)

        # Add warnings
        if len(pre_values) < 5:
            warnings.append(f"Limited pre-split data ({len(pre_values)} years)")
        if len(post_values) < 5:
            warnings.append(f"Limited post-split data ({len(post_values)} years)")
        if len(child_cdks) < 2:
            warnings.append("Single successor - divergence analysis not applicable")
        if zoning.is_sensitive:
            warnings.append("Zoning sensitivity is high. Aggregation method significantly impacts outcomes.")

        return SplitInsights(
            fragmentation=fragmentation,
            divergence=divergence,
            convergence=convergence,
            effect_size=effect_size,
            counterfactual=counterfactual,
            maup=maup,
            children_performance=children_performance,
            warnings=warnings,
        )


def get_insights_analyzer() -> SplitImpactInsightsAnalyzer:
    """Get a split impact insights analyzer instance."""
    return SplitImpactInsightsAnalyzer()
