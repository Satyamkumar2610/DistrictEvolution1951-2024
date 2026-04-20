"""
Soil-Yield Nexus & Input Tracker Module.

Analyses the relationship between soil properties, fertilizer (N/P/K) usage,
and agricultural yield to identify:
  - Diminishing returns on over-fertilization.
  - Districts where input intensification is not translating to yield gains.
  - Soil-type suitability mapping against actual crop choices.

Data Sources:
  - NBSS&LUP soil type classification (ingested separately).
  - Ministry of Agriculture N/P/K district-level consumption data.
  - Existing agri_metrics yield time series.
"""

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)

try:
    from scipy import stats as scipy_stats  # noqa: F401
    from scipy.optimize import curve_fit
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SoilProfile:
    """Soil characteristics for a district."""
    cdk: str
    soil_type: str               # e.g. "Alluvial", "Black Cotton", "Red Laterite"
    texture: str | None          # "Sandy Loam", "Clay", etc.
    organic_carbon_pct: float    # 0-5%
    ph: float                    # soil pH
    depth_cm: float              # effective rooting depth
    suitability_class: str       # "Highly Suitable", "Suitable", "Marginal", "Unsuitable"


@dataclass
class FertilizerSnapshot:
    """N/P/K usage for a district in a given year."""
    cdk: str
    year: int
    nitrogen_kg_ha: float
    phosphorus_kg_ha: float
    potassium_kg_ha: float
    total_npk_kg_ha: float
    npk_ratio: str               # e.g. "4:2:1"


@dataclass
class DiminishingReturnResult:
    """Result of input-yield diminishing returns analysis."""
    crop: str
    current_input_level: float   # total NPK kg/ha
    estimated_optimal: float     # NPK where marginal yield peaks
    marginal_yield_at_current: float  # kg yield per additional kg NPK
    over_fertilized: bool
    efficiency_loss_pct: float   # % yield gain lost to over-application
    model_r2: float
    interpretation: str


@dataclass
class SoilYieldGap:
    """Gap between potential yield for soil type vs actual."""
    cdk: str
    crop: str
    soil_type: str
    actual_yield: float
    soil_potential_yield: float  # benchmark for that soil type
    gap_pct: float
    recommendation: str


@dataclass
class InputEfficiencyReport:
    """Complete soil-yield-input analysis for a district."""
    cdk: str
    soil_profile: SoilProfile | None
    fertilizer_trend: list[FertilizerSnapshot]
    diminishing_returns: list[DiminishingReturnResult]
    soil_yield_gaps: list[SoilYieldGap]
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Reference benchmarks (simplified — in production these come from NBSS data)
# ---------------------------------------------------------------------------

SOIL_YIELD_BENCHMARKS: dict[str, dict[str, float]] = {
    # soil_type -> {crop: potential_yield_kg_ha}
    "alluvial": {"rice": 4500, "wheat": 5000, "sugarcane": 75000, "maize": 4000},
    "black_cotton": {"cotton": 1800, "soyabean": 2200, "wheat": 3800, "sorghum": 2500},
    "red_laterite": {"groundnut": 2000, "rice": 3000, "maize": 3200, "pearl_millet": 1800},
    "sandy": {"pearl_millet": 1500, "groundnut": 1600, "mustard": 1200},
    "mountain": {"rice": 2500, "maize": 2800, "wheat": 2200},
}


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class SoilYieldAnalyzer:
    """
    Analyses the nexus between soil properties, input usage, and yield outcomes.
    """

    def analyze_diminishing_returns(
        self,
        crop: str,
        yearly_input_yield: dict[int, dict[str, float]],
    ) -> DiminishingReturnResult | None:
        """
        Fit a Mitscherlich-type (log-linear) response curve to detect
        diminishing returns on fertilizer application.

        Args:
            crop: Target crop.
            yearly_input_yield: {year: {"total_npk": ..., "yield": ...}}

        Returns:
            DiminishingReturnResult or None if insufficient data.
        """
        if not SCIPY_OK:
            logger.warning("SciPy unavailable — cannot fit response curve.")
            return None

        # Extract paired data
        inputs = []
        yields = []
        for _yr, data in sorted(yearly_input_yield.items()):
            npk = data.get("total_npk", 0)
            yld = data.get("yield", 0)
            if npk > 0 and yld > 0:
                inputs.append(npk)
                yields.append(yld)

        if len(inputs) < 5:
            return None

        x = np.array(inputs)
        y = np.array(yields)

        # Fit Mitscherlich: y = A * (1 - exp(-b * x)) + c
        try:
            def mitscherlich(x_val, a, b, c):
                return a * (1 - np.exp(-b * x_val)) + c

            popt, _ = curve_fit(
                mitscherlich, x, y,
                p0=[np.max(y), 0.01, np.min(y)],
                maxfev=5000,
            )
            a, b, c = popt

            # R²
            y_pred = mitscherlich(x, *popt)
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

            # Marginal yield at current input level
            current_npk = x[-1]
            marginal = float(a * b * np.exp(-b * current_npk))

            # Optimal: where marginal yield drops below 1 kg yield per kg NPK
            optimal_npk = -np.log(1 / (a * b)) / b if a * b > 1 else current_npk

            over_fert = current_npk > optimal_npk * 1.1

            # Efficiency loss
            if over_fert:
                mitscherlich(optimal_npk, *popt)
                mitscherlich(current_npk, *popt)
                extra_input = current_npk - optimal_npk
                extra_input * marginal
                eff_loss = (extra_input / current_npk) * 100
            else:
                eff_loss = 0.0

            # Interpretation
            if over_fert and marginal < 0.5:
                interp = (
                    f"Severe over-fertilization: adding NPK yields only "
                    f"{marginal:.1f} kg/ha per kg input. Consider reducing by "
                    f"{current_npk - optimal_npk:.0f} kg/ha."
                )
            elif over_fert:
                interp = (
                    f"Moderate over-fertilization detected. "
                    f"Current {current_npk:.0f} kg/ha exceeds optimal "
                    f"{optimal_npk:.0f} kg/ha."
                )
            elif marginal > 5:
                interp = (
                    f"Input-responsive district: each additional kg NPK yields "
                    f"{marginal:.1f} kg/ha. Room for intensification."
                )
            else:
                interp = "Input levels are near optimal for current soil conditions."

            return DiminishingReturnResult(
                crop=crop,
                current_input_level=round(float(current_npk), 1),
                estimated_optimal=round(float(optimal_npk), 1),
                marginal_yield_at_current=round(float(marginal), 2),
                over_fertilized=bool(over_fert),
                efficiency_loss_pct=round(float(eff_loss), 1),
                model_r2=round(float(r2), 4),
                interpretation=interp,
            )

        except Exception as e:
            logger.warning(f"Mitscherlich curve fitting failed for {crop}: {e}")
            return None

    def analyze_soil_yield_gap(
        self,
        cdk: str,
        crop: str,
        soil_type: str,
        actual_yield: float,
    ) -> SoilYieldGap | None:
        """
        Compare actual yield to the benchmark for the given soil type.

        Returns:
            SoilYieldGap or None if no benchmark exists.
        """
        soil_key = soil_type.lower().replace(" ", "_")
        benchmarks = SOIL_YIELD_BENCHMARKS.get(soil_key, {})
        potential = benchmarks.get(crop.lower())

        if potential is None:
            return None

        gap_pct = ((potential - actual_yield) / potential) * 100 if potential > 0 else 0

        if gap_pct > 40:
            rec = "Significant underperformance — investigate soil degradation, water stress, or variety mismatch."
        elif gap_pct > 20:
            rec = "Moderate gap — improved varieties or input optimization can close this."
        elif gap_pct > 0:
            rec = "Near potential — focus on maintaining soil health."
        else:
            rec = "Exceeding soil benchmark — verify data accuracy or update benchmark."

        return SoilYieldGap(
            cdk=cdk,
            crop=crop,
            soil_type=soil_type,
            actual_yield=round(actual_yield, 1),
            soil_potential_yield=round(potential, 1),
            gap_pct=round(max(0, gap_pct), 1),
            recommendation=rec,
        )

    def build_report(
        self,
        cdk: str,
        soil_profile: SoilProfile | None,
        fertilizer_history: list[FertilizerSnapshot],
        crop_yields: dict[str, dict[int, dict[str, float]]],
    ) -> InputEfficiencyReport:
        """
        Build a comprehensive soil-yield-input report for a district.

        Args:
            cdk: District identifier.
            soil_profile: District soil characteristics.
            fertilizer_history: List of yearly NPK snapshots.
            crop_yields: {crop: {year: {"total_npk": ..., "yield": ...}}}
        """
        warnings: list[str] = []
        dim_returns: list[DiminishingReturnResult] = []
        soil_gaps: list[SoilYieldGap] = []

        # Diminishing returns per crop
        for crop, yearly_data in crop_yields.items():
            result = self.analyze_diminishing_returns(crop, yearly_data)
            if result:
                dim_returns.append(result)

        # Soil-yield gaps
        if soil_profile:
            for crop, yearly_data in crop_yields.items():
                latest_year = max(yearly_data.keys()) if yearly_data else None
                if latest_year:
                    actual_yld = yearly_data[latest_year].get("yield", 0)
                    if actual_yld > 0:
                        gap = self.analyze_soil_yield_gap(
                            cdk, crop, soil_profile.soil_type, actual_yld
                        )
                        if gap:
                            soil_gaps.append(gap)
        else:
            warnings.append("No soil profile available — soil-yield gap analysis skipped.")

        if not fertilizer_history:
            warnings.append("No fertilizer consumption data available.")

        return InputEfficiencyReport(
            cdk=cdk,
            soil_profile=soil_profile,
            fertilizer_trend=fertilizer_history,
            diminishing_returns=dim_returns,
            soil_yield_gaps=soil_gaps,
            warnings=warnings,
        )
