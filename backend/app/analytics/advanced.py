"""
Advanced Analytics Module for I-ASCAP.
Provides Crop Diversification Index, Yield Efficiency, and Risk Profiling.
"""

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from app.analytics.statistics import get_analyzer  # type: ignore


class RiskCategory(StrEnum):
    """Risk classification based on volatility."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DiversificationResult:
    """Result of crop diversification analysis."""

    cdi: float  # Crop Diversification Index (0-1)
    interpretation: str  # Human-readable interpretation
    dominant_crop: str | None  # Most grown crop
    dominant_share: float  # Share of dominant crop (0-1)
    crop_count: int  # Number of crops grown
    breakdown: dict[str, float]  # Crop -> share mapping


@dataclass
class EfficiencyResult:
    """Result of yield efficiency analysis."""

    efficiency_score: float  # 0-1, how close to potential
    district_yield: float
    potential_yield: float  # 95th percentile in state
    yield_gap: float  # Absolute difference
    yield_gap_pct: float  # Percentage gap
    percentile_rank: float  # District's rank within state


@dataclass
class RiskProfile:
    """Risk profile for a district."""

    risk_category: RiskCategory
    volatility_score: float  # CV percentage
    reliability_rating: str  # A/B/C/D/F
    trend_stability: str  # Stable/Unstable
    worst_year: int | None
    best_year: int | None


@dataclass
class HistoricalEfficiencyResult:
    """Result of historical efficiency analysis."""

    efficiency_ratio: float  # current / historical_mean
    current_yield: float
    historical_mean: float  # 10-year mean
    yield_diff: float  # current - mean
    is_above_trend: bool


@dataclass
class ResilienceResult:
    """Result of resilience analysis."""

    resilience_score: float  # 0-1 composite score
    volatility_component: float  # normalized (1-CV)
    retention_component: float  # P10/Median ratio
    drought_risk: str  # Low/Med/High based on retention
    reliability_rating: str  # A-F


@dataclass
class GrowthResult:
    """Result of growth matrix analysis."""

    cagr_5y: float
    cagr_historical: float
    mean_yield_5y: float
    matrix_quadrant: str  # Star, Cash Cow, Emerging, Lagging
    trend_direction: str
    formula: str = "((End/Start)^(1/n) - 1) * 100"


@dataclass
class SimulationResult:
    """Result of impact simulation model."""

    baseline_yield: float
    slope: float  # kg/ha change per mm rainfall
    intercept: float
    r_squared: float
    correlation: float
    confidence_interval: float  # Margin of error at 95%
    data_points: list[dict[str, float]]  # For scatter plot
    model_equation: str  # String representation


class AdvancedAnalyzer:
    """
    Advanced analytics for agricultural data.

    Provides:
    - Crop Diversification Index (CDI)
    - Yield Efficiency/Gap Analysis
    - Volatility and Risk Profiling
    """

    def __init__(self):
        self.stats = get_analyzer()

    # -------------------------------------------------------------------------
    # Crop Diversification Index (CDI)
    # -------------------------------------------------------------------------

    def calculate_diversification(
        self,
        crop_areas: dict[str, float],
    ) -> DiversificationResult:
        """
        Calculate Crop Diversification Index using Simpson's Diversity Index.

        Formula: CDI = 1 - Σ(pi²) where pi = proportion of crop i

        Args:
            crop_areas: Dictionary of crop name -> area in hectares

        Returns:
            DiversificationResult with CDI and interpretation
        """
        if not crop_areas:
            return DiversificationResult(
                cdi=0,
                interpretation="No crop data available",
                dominant_crop=None,
                dominant_share=0,
                crop_count=0,
                breakdown={},
            )

        total_area = sum(crop_areas.values())
        if total_area == 0:
            return DiversificationResult(
                cdi=0,
                interpretation="Zero total area",
                dominant_crop=None,
                dominant_share=0,
                crop_count=0,
                breakdown={},
            )

        # Calculate proportions and sum of squares
        proportions = {crop: area / total_area for crop, area in crop_areas.items()}
        sum_of_squares = sum(p**2 for p in proportions.values())

        # Simpson's Diversity Index
        cdi = 1 - sum_of_squares

        # Find dominant crop
        dominant_crop = max(crop_areas.items(), key=lambda x: x[1])[0]
        dominant_share = proportions[dominant_crop]

        # Interpretation
        if cdi < 0.2:
            interpretation = "Monoculture risk - highly concentrated in single crop"
        elif cdi < 0.4:
            interpretation = "Low diversification - 1-2 major crops dominate"
        elif cdi < 0.6:
            interpretation = "Moderate diversification - reasonable crop mix"
        elif cdi < 0.8:
            interpretation = "Good diversification - well balanced portfolio"
        else:
            interpretation = "Excellent diversification - highly resilient crop mix"

        return DiversificationResult(
            cdi=round(float(cdi), 4),  # type: ignore
            interpretation=interpretation,
            dominant_crop=dominant_crop,
            dominant_share=round(float(dominant_share), 4),  # type: ignore
            crop_count=len(crop_areas),
            breakdown={k: round(float(v), 4) for k, v in proportions.items()},  # type: ignore
        )

    # -------------------------------------------------------------------------
    # Yield Efficiency / Gap Analysis
    # -------------------------------------------------------------------------

    def calculate_efficiency(
        self,
        district_yield: float,
        state_yields: list[float],
    ) -> EfficiencyResult:
        """
        Calculate yield efficiency compared to state potential.

        Potential yield = 95th percentile of state yields.

        Args:
            district_yield: Yield for the district
            state_yields: List of yields for all districts in state

        Returns:
            EfficiencyResult with efficiency score and gap
        """
        if not state_yields or district_yield <= 0:
            return EfficiencyResult(
                efficiency_score=0,
                district_yield=district_yield,
                potential_yield=0,
                yield_gap=0,
                yield_gap_pct=0,
                percentile_rank=0,
            )

        # Calculate potential (95th percentile)
        potential_yield = self.stats.percentile(state_yields, 95)

        # Calculate efficiency
        efficiency = min(district_yield / potential_yield, 1.0) if potential_yield > 0 else 0

        # Calculate gap
        yield_gap = potential_yield - district_yield
        yield_gap_pct = (yield_gap / potential_yield * 100) if potential_yield > 0 else 0

        # Percentile rank within state
        percentile_rank = self.stats.percentile_rank(district_yield, state_yields)

        return EfficiencyResult(
            efficiency_score=round(float(efficiency), 4),  # type: ignore
            district_yield=round(float(district_yield), 2),  # type: ignore
            potential_yield=round(float(potential_yield), 2),  # type: ignore
            yield_gap=round(float(max(0.0, yield_gap)), 2),  # type: ignore
            yield_gap_pct=round(float(max(0.0, yield_gap_pct)), 2),  # type: ignore
            percentile_rank=round(float(percentile_rank), 2),  # type: ignore
        )

    def calculate_historical_efficiency(
        self,
        current_yield: float,
        historical_yields: list[float],
    ) -> HistoricalEfficiencyResult:
        """
        Calculate efficiency compared to district's own history (10-year mean).

        Args:
            current_yield: Yield for the current year
            historical_yields: List of yields for previous years (up to 10)

        Returns:
            HistoricalEfficiencyResult
        """
        if not historical_yields:
            return HistoricalEfficiencyResult(
                efficiency_ratio=0,
                current_yield=current_yield,
                historical_mean=0,
                yield_diff=0,
                is_above_trend=False,
            )

        # Calculate 10-year mean (or available)
        mean_yield = sum(historical_yields) / len(historical_yields)

        if mean_yield == 0:
            return HistoricalEfficiencyResult(
                efficiency_ratio=0,
                current_yield=current_yield,
                historical_mean=0,
                yield_diff=0,
                is_above_trend=False,
            )

        ratio = current_yield / mean_yield
        diff = current_yield - mean_yield

        return HistoricalEfficiencyResult(
            efficiency_ratio=round(float(ratio), 4),  # type: ignore
            current_yield=round(float(current_yield), 2),  # type: ignore
            historical_mean=round(float(mean_yield), 2),  # type: ignore
            yield_diff=round(float(diff), 2),  # type: ignore
            is_above_trend=bool(diff > 0),
        )

    # -------------------------------------------------------------------------
    # Risk Profiling
    # -------------------------------------------------------------------------

    def calculate_risk_profile(
        self,
        yearly_values: dict[int, float],
    ) -> RiskProfile:
        """
        Calculate risk profile based on historical volatility.
        """
        if not yearly_values or len(yearly_values) < 3:
            return RiskProfile(
                risk_category=RiskCategory.MEDIUM,  # Default
                volatility_score=0,
                reliability_rating="C",
                trend_stability="Unknown",
                worst_year=None,
                best_year=None,
            )

        values = list(yearly_values.values())

        # 1. Volatility (CV)
        cv = self.stats.coefficient_of_variation(values)

        # 2. Risk Category
        if cv < 15:
            category = RiskCategory.LOW
        elif cv < 30:
            category = RiskCategory.MEDIUM
        elif cv < 50:
            category = RiskCategory.HIGH
        else:
            category = RiskCategory.CRITICAL

        # 3. Reliability Rating (Consistency)
        # Based on how often yield is within 20% of mean
        mean = self.stats.mean(values)
        if mean > 0:
            consistent_years = sum(1 for v in values if abs(v - mean) / mean <= 0.2)
            consistency_ratio = consistent_years / len(values)
        else:
            consistency_ratio = 0

        if consistency_ratio > 0.8:
            rating = "A"
        elif consistency_ratio > 0.6:
            rating = "B"
        elif consistency_ratio > 0.4:
            rating = "C"
        else:
            rating = "D"

        # 4. Trend Stability using Mann-Kendall proxy (simple linear slope for
        # now)
        trend = self.stats.linear_trend(values)
        if trend.significant and trend.slope > 0:
            stability = "Stable Growth"
        elif trend.significant and trend.slope < 0:
            stability = "Declining"
        else:
            stability = "Volatile" if cv > 30 else "Stable"

        # 5. Extremes
        sorted_years = sorted(yearly_values.items(), key=lambda x: x[1])
        worst_year = sorted_years[0][0]
        best_year = sorted_years[-1][0]

        return RiskProfile(
            risk_category=category,
            volatility_score=round(cv, 2),  # type: ignore
            reliability_rating=rating,
            trend_stability=stability,
            worst_year=worst_year,
            best_year=best_year,
        )

    # -------------------------------------------------------------------------
    # Resilience & Growth
    # -------------------------------------------------------------------------

    def calculate_resilience(self, yearly_values: dict[int, float]) -> ResilienceResult:
        """
        Calculate resilience score.
        Score = 0.6 * (1 - CV_norm) + 0.4 * Retention_Ratio
        Retention_Ratio = 10th Percentile Yield / Median Yield (Proxy for drought resistance)
        """
        if not yearly_values or len(yearly_values) < 5:
            return ResilienceResult(0, 0, 0, "N/A", "N/A")

        values = list(yearly_values.values())

        # 1. Volatility Component
        cv = self.stats.coefficient_of_variation(values)
        # Normalize CV: Assume CV > 40% is 0 score, CV < 5% is 1 score.
        cv_norm = float(max(0.0, min(1.0, (40.0 - cv) / 35.0)))

        # 2. Retention Component (Drought Proxy)
        median = self.stats.percentile(values, 50)
        p10 = self.stats.percentile(values, 10)
        retention = (p10 / median) if median > 0 else 0
        retention = min(retention, 1.0)

        # Composite Score
        score = (0.6 * cv_norm) + (0.4 * retention)

        # Categorization
        if retention < 0.6:
            drought_risk = "High"
        elif retention < 0.8:
            drought_risk = "Medium"
        else:
            drought_risk = "Low"

        rating = "A" if score > 0.8 else "B" if score > 0.6 else "C" if score > 0.4 else "D"

        return ResilienceResult(
            resilience_score=round(float(score), 2),  # type: ignore
            volatility_component=round(float(cv_norm), 2),  # type: ignore
            retention_component=round(float(retention), 2),  # type: ignore
            drought_risk=drought_risk,
            reliability_rating=rating,
        )

    def calculate_growth_matrix(self, yearly_values: dict[int, float]) -> GrowthResult:
        """
        Calculate Compound Annual Growth Rate (CAGR) and classify matrix quadrant.
        """
        if not yearly_values or len(yearly_values) < 5:
            return GrowthResult(0.0, 0.0, 0.0, "Insufficient Data", "Flat")

        sorted_years = list(sorted(yearly_values.keys()))
        recent_years = sorted_years[-5:]  # type: ignore

        start_val = yearly_values[recent_years[0]]
        end_val = yearly_values[recent_years[-1]]
        years = len(recent_years) - 1

        # CAGR Formula: (End/Start)^(1/n) - 1
        cagr = (end_val / start_val) ** (1 / years) - 1 if start_val > 0 and years > 0 else 0

        mean_yield = sum(yearly_values[y] for y in recent_years) / len(recent_years)

        # Determine Quadrant (Thresholds need state context, but using generic for now)
        # Assuming "High Growth" > 2%, "High Yield" > ??? (Relative to what? Self-history?)
        # Ideally this needs State Mean context. For now, we return raw values.
        # We'll use a placeholder classification based on CAGR.

        if cagr > 0.02:
            quadrant = "Growth Leader"
        elif cagr > 0:
            quadrant = "Stable"
        else:
            quadrant = "Declining"

        # Calculate Historical CAGR (All available years)
        hist_years = sorted_years
        hist_start_val = yearly_values[hist_years[0]]
        hist_end_val = yearly_values[hist_years[-1]]
        hist_n = len(hist_years) - 1

        cagr_hist = (hist_end_val / hist_start_val) ** (1 / hist_n) - 1 if hist_start_val > 0 and hist_n > 0 else 0

        return GrowthResult(
            cagr_5y=round(float(cagr * 100), 2),  # type: ignore
            cagr_historical=round(float(cagr_hist * 100), 2),  # type: ignore
            mean_yield_5y=round(float(mean_yield), 2),  # type: ignore
            matrix_quadrant=quadrant,
            trend_direction="Positive" if cagr > 0 else "Negative",
        )

    # -------------------------------------------------------------------------
    # Batch Analysis Helpers
    # -------------------------------------------------------------------------

    def analyze_district_complete(
        self,
        crop_areas: dict[str, float],
        district_yield: float,
        state_yields: list[float],
        yearly_values: dict[int, float],
    ) -> dict[str, Any]:
        """
        Perform complete advanced analysis for a district.

        Returns combined results for diversification, efficiency, and risk.
        """
        diversification = self.calculate_diversification(crop_areas)
        efficiency = self.calculate_efficiency(district_yield, state_yields)
        risk = self.calculate_risk_profile(yearly_values)

        return {
            "diversification": asdict(diversification),  # type: ignore
            "efficiency": asdict(efficiency),  # type: ignore
            "risk": {
                **asdict(risk),  # type: ignore
                "risk_category": risk.risk_category.value,
            },
        }

    # -------------------------------------------------------------------------
    # Simulation Models
    # -------------------------------------------------------------------------

    def calculate_impact_simulation(
        self, rainfall: list[float], yields: list[float], years: list[int]
    ) -> SimulationResult:
        """
        Create a linear simulation model for Rainfall -> Yield.
        """
        if not rainfall or not yields or len(rainfall) != len(yields) or len(rainfall) < 5:
            return SimulationResult(0, 0, 0, 0, 0, 0, [], "Insufficient Data")

        # 1. Regression
        reg = self.stats.linear_regression(rainfall, yields)
        corr = self.stats.pearson_correlation(rainfall, yields)

        # 2. Baseline (Current Expected Yield at Mean Rainfall)
        mean_rain = self.stats.mean(rainfall)
        baseline_yield = (reg.slope * mean_rain) + reg.intercept

        # 3. Confidence Interval (Simplified estimation)
        # Using standard error of estimate for prediction interval would be better,
        # but for now we use std_err of slope * range as a proxy for visual
        # margin
        ci = reg.std_err * 1.96 * (max(rainfall) - min(rainfall)) if reg.slope != 0 else 0

        # 4. Data Points for Plotting
        points = [{"year": y, "rain": r, "yield": yld} for y, r, yld in zip(years, rainfall, yields, strict=False)]

        return SimulationResult(
            baseline_yield=round(baseline_yield, 2),  # type: ignore
            slope=round(reg.slope, 4),  # type: ignore
            intercept=round(reg.intercept, 4),  # type: ignore
            r_squared=round(reg.r_squared, 4),  # type: ignore
            correlation=round(corr.value, 4),  # type: ignore
            confidence_interval=round(ci, 2),  # type: ignore
            data_points=points,
            model_equation=f"Yield = {reg.slope:.2f} * Rain + {reg.intercept:.2f}",
        )


def get_advanced_analyzer() -> AdvancedAnalyzer:
    """Get an advanced analyzer instance."""
    return AdvancedAnalyzer()
