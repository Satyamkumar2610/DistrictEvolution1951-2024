"""
Multi-Factor Yield Prediction Engine.

Provides a robust, explainable prediction model that combines:
- Spatial regression (cross-district rainfall vs yield)
- Temporal signals (historical yield trend, volatility)
- Agronomic context (crop area, monsoon seasonality)

Uses Ridge-style regularized regression via numpy (no sklearn dependency).
"""

import logging
import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Data Classes
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class FactorImportance:
    """Importance of a single feature in the model."""

    name: str  # Human-readable name
    key: str  # Machine key
    importance: float  # Standardized coefficient magnitude (0-1 scale)
    coefficient: float  # Raw model coefficient
    # Contribution to prediction (coeff * feature_value)
    contribution: float
    direction: str  # "positive" or "negative"
    description: str  # Plain-English explanation


@dataclass
class PredictionResult:
    """Full prediction result with explainability."""

    # Core prediction
    predicted_yield: float
    baseline_yield: float
    confidence_lower: float
    confidence_upper: float

    # Interactive simulation
    slope_rain: float  # kg/ha per mm of rainfall deviation
    mean_rain: float  # Mean rainfall for slider baseline

    # Model quality
    r_squared: float
    adjusted_r_squared: float
    rmse: float
    sample_size: int
    feature_count: int
    method: str  # "multi_factor_ridge" or "simple_ols"

    # Explainability
    factors: list[FactorImportance]  # Sorted by importance desc
    model_equation: str  # Human-readable equation
    methodology: str  # Explanation paragraph
    data_quality_notes: list[str]  # Warnings / notes

    # Viz data
    data_points: list[dict[str, float]]  # [{rain, yield, district}]
    regression_line: list[dict[str, float]]  # [{x, y}] for trend line

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)  # type: ignore
        return d


# ──────────────────────────────────────────────────────────────────────────────
# Prediction Engine
# ──────────────────────────────────────────────────────────────────────────────


class PredictionEngine:
    """
    Multi-factor yield prediction with full explainability.

    Strategy:
    - With ≥ 8 districts of matched data: Ridge regression with 5 features
    - With 5-7 districts: simple OLS (rainfall → yield only)
    - With < 5 districts: insufficient data

    Features (when available):
    1. Rainfall (annual mm)
    2. Monsoon ratio (monsoon_jjas / annual)
    3. Historical yield trend (slope of yield over time for that district)
    4. Yield volatility (coefficient of variation of historical yields)
    5. Crop area (hectares under the given crop for that district)
    """

    RIDGE_MIN = 8
    OLS_MIN = 5
    RIDGE_ALPHA = 1.0  # Regularization strength

    def predict(
        self,
        district_data: list[dict[str, Any]],
        target_district: str,
    ) -> PredictionResult | None:
        """
        Build a prediction model from cross-district data and predict
        for the target district.

        Args:
            district_data: List of dicts, each with:
                - district: str
                - yield_value: float (kg/ha)
                - rainfall: float (annual mm)
                - monsoon_jjas: float (optional)
                - yield_trend: float (optional, slope of yield over years)
                - yield_cv: float (optional, coefficient of variation)
                - crop_area: float (optional, hectares)
            target_district: Name of the district to explain prediction for.

        Returns:
            PredictionResult or None if insufficient data.
        """
        if not district_data or len(district_data) < self.OLS_MIN:
            return None

        n = len(district_data)

        if n >= self.RIDGE_MIN:
            return self._predict_multi_factor(district_data, target_district)
        else:
            return self._predict_simple(district_data, target_district)

    # ──────────────────────────────────────────────────────────────────────
    # Multi-Factor Ridge Regression
    # ──────────────────────────────────────────────────────────────────────

    def _predict_multi_factor(
        self,
        data: list[dict[str, Any]],
        target_district: str,
    ) -> PredictionResult:
        """Ridge regression with multiple features."""
        n = len(data)

        # Extract raw feature arrays
        yields = np.array([d["yield_value"] for d in data], dtype=float)
        rainfall = np.array([d["rainfall"] for d in data], dtype=float)

        # Optional features — use zeros if missing
        monsoon_jjas = np.array([d.get("monsoon_jjas", 0) for d in data], dtype=float)
        has_monsoon = np.any(monsoon_jjas > 0)
        monsoon_ratio = np.where(rainfall > 0, monsoon_jjas / rainfall, 0.0) if has_monsoon else np.zeros(n)

        yield_trend = np.array([d.get("yield_trend", 0) for d in data], dtype=float)
        has_trend = np.any(yield_trend != 0)

        yield_cv = np.array([d.get("yield_cv", 0) for d in data], dtype=float)
        has_cv = np.any(yield_cv > 0)

        crop_area = np.array([d.get("crop_area", 0) for d in data], dtype=float)
        has_area = np.any(crop_area > 0)

        temperature = np.array([d.get("temperature", 0) for d in data], dtype=float)
        has_temp = np.any(temperature > 0)

        soil_moisture = np.array([d.get("soil_moisture", 0) for d in data], dtype=float)
        has_moisture = np.any(soil_moisture > 0)

        rainfall_sq = rainfall**2

        # Build feature matrix (only include features with actual data)
        feature_names = ["rainfall", "rainfall_squared"]
        feature_keys = ["rainfall", "rainfall_sq"]
        feature_descriptions = [
            "Annual rainfall normal (mm) — primary climate driver of crop yield",
            "Squared rainfall — captures non-linear optimal water requirements",
        ]
        raw_features = [rainfall, rainfall_sq]

        if has_monsoon:
            feature_names.append("monsoon_ratio")
            feature_keys.append("monsoon_ratio")
            feature_descriptions.append(
                "Proportion of annual rainfall during monsoon (Jun-Sep) — captures rainfall seasonality"
            )
            raw_features.append(monsoon_ratio)

        if has_trend:
            feature_names.append("yield_trend")
            feature_keys.append("yield_trend")
            feature_descriptions.append(
                "Historical yield growth rate (kg/ha per year) — indicates improving or declining productivity"
            )
            raw_features.append(yield_trend)

        if has_cv:
            feature_names.append("yield_stability")
            feature_keys.append("yield_cv")
            feature_descriptions.append(
                "Yield coefficient of variation (%) — lower CV means more consistent production"
            )
            raw_features.append(yield_cv)

        if has_area:
            feature_names.append("crop_area")
            feature_keys.append("crop_area")
            feature_descriptions.append("Area under crop (hectares) — proxy for local agronomic suitability")
            raw_features.append(crop_area)

        if has_temp:
            feature_names.append("temperature")
            feature_keys.append("temperature")
            feature_descriptions.append(
                "Annual average temperature (°C) — influences evapotranspiration and heat stress"
            )
            raw_features.append(temperature)

        if has_moisture:
            feature_names.append("soil_moisture")
            feature_keys.append("soil_moisture")
            feature_descriptions.append("Soil moisture index (0-100) — represents root-zone water availability")
            raw_features.append(soil_moisture)

        p = len(raw_features)
        X_raw = np.column_stack(raw_features)  # (n, p)

        # Standardize features for Ridge (Z-score)
        X_mean = X_raw.mean(axis=0)
        X_std = X_raw.std(axis=0)
        X_std[X_std == 0] = 1.0  # Avoid division by zero
        X_z = (X_raw - X_mean) / X_std

        y_mean = yields.mean()
        y_centered = yields - y_mean

        # Ridge regression: β = (X'X + αI)^(-1) X'y
        XtX = X_z.T @ X_z
        Xty = X_z.T @ y_centered
        identity = np.eye(p)
        beta_z = np.linalg.solve(XtX + self.RIDGE_ALPHA * identity, Xty)

        # Convert standardized coefficients back to original scale
        beta_raw = beta_z / X_std
        intercept = y_mean - np.dot(beta_raw, X_mean)

        # Predictions & residuals
        y_pred = X_raw @ beta_raw + intercept
        residuals = yields - y_pred
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((yields - y_mean) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        adj_r_sq = 1 - (1 - r_squared) * (n - 1) / (n - p - 1) if n > p + 1 else r_squared
        rmse = math.sqrt(ss_res / n) if n > 0 else 0.0

        # Standard error for prediction interval
        se = math.sqrt(ss_res / max(1, n - p - 1))

        # Find target district
        target_idx = None
        for i, d in enumerate(data):
            if d["district"].upper() == target_district.upper():
                target_idx = i
                break

        # Predicted yield for target
        if target_idx is not None:
            predicted = float(y_pred[target_idx])
            target_features = X_raw[target_idx]
        else:
            # If target not in data, predict at mean features
            predicted = float(y_mean)
            target_features = X_mean

        predicted = max(0.0, predicted)

        # Confidence interval (prediction interval)
        t_value = 1.96  # ~95%
        ci_half = t_value * se * math.sqrt(1 + 1 / n)
        conf_lower = max(0.0, predicted - ci_half)
        conf_upper = predicted + ci_half

        # Factor importances & contributions
        abs_beta_z = np.abs(beta_z)
        beta_z_sum = abs_beta_z.sum()
        importances = abs_beta_z / beta_z_sum if beta_z_sum > 0 else np.zeros(p)

        factors = []
        for i in range(p):
            contribution = float(beta_raw[i] * target_features[i])
            factors.append(
                FactorImportance(
                    name=self._humanize(feature_names[i]),
                    key=feature_keys[i],
                    importance=round(float(importances[i]), 4),  # type: ignore
                    coefficient=round(float(beta_raw[i]), 6),  # type: ignore
                    contribution=round(contribution, 2),  # type: ignore
                    direction="positive" if beta_raw[i] > 0 else "negative",
                    description=feature_descriptions[i],
                )
            )

        factors.sort(key=lambda f: f.importance, reverse=True)

        # Regression line for scatter (rainfall vs yield)
        rain_min, rain_max = float(rainfall.min()), float(rainfall.max())
        rain_range = np.linspace(rain_min, rain_max, 50)

        # For the regression line, predict using rainfall only (holding other
        # features at mean)
        rain_slope = float(beta_raw[0])  # Rainfall is always feature 0
        rain_line_y = [
            max(0.0, float(intercept + rain_slope * r + sum(beta_raw[j] * X_mean[j] for j in range(1, p))))
            for r in rain_range
        ]
        regression_line = [
            {"x": round(float(r), 1), "y": round(y, 1)}  # type: ignore
            for r, y in zip(rain_range, rain_line_y, strict=False)
        ]

        # Data points for scatter
        data_points = [
            {
                "rain": round(float(d["rainfall"]), 1),  # type: ignore
                "yield": round(float(d["yield_value"]), 1),  # type: ignore
                "district": d["district"],
            }
            for d in data
        ]

        # Model equation
        terms = [f"{beta_raw[i]:+.3f}×{feature_names[i]}" for i in range(p)]
        equation = f"Yield = {intercept:.1f} {' '.join(terms)}"

        # Methodology text
        methodology = (
            f"This prediction uses **Multi-Factor Ridge Regression** trained on "
            f"{n} districts within the same state. The model considers {p} factors: "
            f"{', '.join(self._humanize(fn) for fn in feature_names)}. "
            f"Ridge regularization (α={self.RIDGE_ALPHA}) prevents overfitting "
            f"when features are correlated. Features are Z-score standardized "
            f"before fitting, so factor importances reflect true explanatory power. "
            f"The prediction interval is a 95% confidence band accounting for "
            f"model uncertainty."
        )

        # Data quality notes
        notes = []
        if n < 15:
            notes.append(f"Small sample ({n} districts) — predictions may be less reliable.")
        if r_squared < 0.3:
            notes.append(
                "Low R² — yield variance is poorly explained by available factors. Other unmeasured variables (soil, irrigation) may dominate."
            )
        if not has_trend:
            notes.append("Historical yield trend data was unavailable — temporal signal not included.")
        if not has_monsoon:
            notes.append("Monthly rainfall breakdown unavailable — monsoon seasonality not modeled.")

        mean_rain = float(rainfall.mean())

        return PredictionResult(
            predicted_yield=round(predicted, 1),  # type: ignore
            baseline_yield=round(float(y_mean), 1),  # type: ignore
            confidence_lower=round(conf_lower, 1),  # type: ignore
            confidence_upper=round(conf_upper, 1),  # type: ignore
            slope_rain=round(rain_slope, 4),  # type: ignore
            mean_rain=round(mean_rain, 1),  # type: ignore
            r_squared=round(float(r_squared), 4),  # type: ignore
            adjusted_r_squared=round(float(adj_r_sq), 4),  # type: ignore
            rmse=round(rmse, 1),  # type: ignore
            sample_size=n,
            feature_count=p,
            method="multi_factor_ridge",
            factors=factors,
            model_equation=equation,
            methodology=methodology,
            data_quality_notes=notes,
            data_points=data_points,
            regression_line=regression_line,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Simple OLS Fallback (5-7 data points)
    # ──────────────────────────────────────────────────────────────────────

    def _predict_simple(
        self,
        data: list[dict[str, Any]],
        target_district: str,
    ) -> PredictionResult:
        """Single-variable OLS: Rainfall → Yield."""
        n = len(data)
        rainfall = np.array([d["rainfall"] for d in data], dtype=float)
        yields = np.array([d["yield_value"] for d in data], dtype=float)

        # OLS
        x_mean = rainfall.mean()
        y_mean = yields.mean()
        ss_xy = np.sum((rainfall - x_mean) * (yields - y_mean))
        ss_xx = np.sum((rainfall - x_mean) ** 2)

        if ss_xx == 0:
            slope = 0.0
            intercept = y_mean
        else:
            slope = float(ss_xy / ss_xx)
            intercept = float(y_mean - slope * x_mean)

        y_pred = slope * rainfall + intercept
        residuals = yields - y_pred
        ss_res = float(np.sum(residuals**2))
        ss_tot = float(np.sum((yields - y_mean) ** 2))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        rmse = math.sqrt(ss_res / n) if n > 0 else 0.0
        se = math.sqrt(ss_res / max(1, n - 2))

        # Target district prediction
        target_rain = x_mean
        for d in data:
            if d["district"].upper() == target_district.upper():
                target_rain = d["rainfall"]
                break

        predicted = max(0.0, float(slope * target_rain + intercept))  # type: ignore
        ci_half = 1.96 * se * math.sqrt(1 + 1 / n)

        # Single factor
        contribution = float(slope * target_rain)  # type: ignore
        factors = [
            FactorImportance(
                name="Annual Rainfall",
                key="rainfall",
                importance=1.0,
                coefficient=round(float(slope), 6),  # type: ignore
                contribution=round(contribution, 2),  # type: ignore
                direction="positive" if slope > 0 else "negative",
                description="Annual rainfall normal (mm) — the only predictor in this simplified model",
            )
        ]

        # Regression line
        rain_min, rain_max = float(rainfall.min()), float(rainfall.max())
        rain_range = np.linspace(rain_min, rain_max, 50)
        regression_line = [
            {"x": round(float(r), 1), "y": round(float(max(0.0, float(slope * r + intercept))), 1)}  # type: ignore
            for r in rain_range
        ]

        data_points = [
            {
                "rain": round(float(d["rainfall"]), 1),  # type: ignore
                "yield": round(float(d["yield_value"]), 1),  # type: ignore
                "district": d["district"],
            }
            for d in data
        ]

        methodology = (
            f"This prediction uses **Simple Linear Regression** (OLS) trained on "
            f"{n} districts. Only annual rainfall is used as a predictor because "
            f"the sample size ({n} districts) is too small for multi-factor modeling "
            f"(minimum 8 required). The model captures the spatial relationship "
            f"between long-term rainfall and crop yield across the state."
        )

        notes = [
            f"Limited sample ({n} districts) — using simplified single-variable model.",
            "Additional factors (trend, volatility, area) require ≥ 8 districts.",
        ]
        if r_squared < 0.3:
            notes.append("Low R² — rainfall alone poorly explains yield variation.")

        return PredictionResult(
            predicted_yield=round(predicted, 1),  # type: ignore
            baseline_yield=round(float(y_mean), 1),  # type: ignore
            confidence_lower=round(float(max(0.0, float(predicted - ci_half))), 1),  # type: ignore
            confidence_upper=round(predicted + ci_half, 1),  # type: ignore
            slope_rain=round(float(slope), 4),  # type: ignore
            mean_rain=round(float(x_mean), 1),  # type: ignore
            r_squared=round(r_squared, 4),  # type: ignore
            adjusted_r_squared=round(r_squared, 4),  # type: ignore
            rmse=round(rmse, 1),  # type: ignore
            sample_size=n,
            feature_count=1,
            method="simple_ols",
            factors=factors,
            model_equation=f"Yield = {intercept:.1f} + {slope:.3f} × Rainfall",
            methodology=methodology,
            data_quality_notes=notes,
            data_points=data_points,
            regression_line=regression_line,
        )

    @staticmethod
    def _humanize(key: str) -> str:
        """Convert feature key to human-readable name."""
        mapping = {
            "rainfall": "Annual Rainfall",
            "monsoon_ratio": "Monsoon Seasonality",
            "yield_trend": "Yield Growth Rate",
            "yield_stability": "Yield Stability",
            "yield_cv": "Yield Variability",
            "crop_area": "Crop Area",
            "temperature": "Mean Temperature",
            "soil_moisture": "Soil Moisture Index",
        }
        return mapping.get(key, key.replace("_", " ").title())
