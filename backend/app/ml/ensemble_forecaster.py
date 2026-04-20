"""
Ensemble Yield Forecaster: Prophet + XGBoost with SHAP Explainability.

Replaces the SARIMA(1,1,1) approach with a two-stage ensemble:
  Stage 1 — Prophet captures trend + seasonality decomposition.
  Stage 2 — XGBoost learns residuals using exogenous climate features.

SHAP waterfall values are derived per-prediction for frontend display.
"""

import logging
import warnings
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ShapContribution:
    """Single SHAP feature contribution."""
    feature: str
    value: float       # raw feature value
    shap_value: float  # contribution to prediction (kg/ha)


@dataclass
class EnsembleForecastPoint:
    """A single prediction from the ensemble."""
    year: int
    predicted_yield: float
    lower_bound: float
    upper_bound: float
    confidence: float
    prophet_component: float
    xgb_residual_component: float
    shap_contributions: list[ShapContribution] = field(default_factory=list)


@dataclass
class EnsembleForecastResult:
    """Complete ensemble forecast output."""
    cdk: str
    crop: str
    historical_years: int
    method: str  # "prophet_xgboost_ensemble"
    trend_direction: str
    forecasts: list[EnsembleForecastPoint]
    model_stats: dict[str, Any]
    feature_importance: dict[str, float]  # global SHAP importance

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["forecasts"] = [asdict(f) for f in self.forecasts]
        return result


# ---------------------------------------------------------------------------
# Availability checks
# ---------------------------------------------------------------------------

def _check_prophet() -> bool:
    try:
        from prophet import Prophet  # noqa: F401
        return True
    except ImportError:
        logger.warning("prophet not installed — ensemble forecasting disabled.")
        return False


def _check_xgboost() -> bool:
    try:
        import xgboost  # noqa: F401
        return True
    except ImportError:
        logger.warning("xgboost not installed — ensemble forecasting disabled.")
        return False


def _check_shap() -> bool:
    try:
        import shap  # noqa: F401
        return True
    except ImportError:
        logger.warning("shap not installed — feature importance will be unavailable.")
        return False


PROPHET_OK = _check_prophet()
XGB_OK = _check_xgboost()
SHAP_OK = _check_shap()


# ---------------------------------------------------------------------------
# Core Ensemble
# ---------------------------------------------------------------------------

class EnsembleForecaster:
    """
    Two-stage Prophet + XGBoost ensemble forecaster with SHAP explanations.

    Workflow:
        1. Fit Prophet on the yield time series to capture trend + changepoints.
        2. Compute Prophet residuals for historical period.
        3. Train XGBoost on residuals using exogenous features
           (rainfall, temperature, NDVI, soil, etc.).
        4. For future years, combine Prophet trend forecast + XGB residual
           prediction.
        5. Derive SHAP values for the XGB component so users can understand
           *why* the model predicts what it does.
    """

    MIN_POINTS = 8  # need at least 8 years for meaningful ensemble

    def __init__(self):
        self.prophet_available = PROPHET_OK
        self.xgb_available = XGB_OK
        self.shap_available = SHAP_OK

    def forecast(
        self,
        cdk: str,
        crop: str,
        historical_yields: dict[int, float],
        exogenous_features: dict[int, dict[str, float]] | None = None,
        horizon_years: int = 3,
        confidence_level: float = 0.95,
    ) -> EnsembleForecastResult | None:
        """
        Run the full ensemble pipeline.

        Args:
            cdk: District identifier.
            crop: Crop name.
            historical_yields: {year: yield_kg_ha}.
            exogenous_features: {year: {feature_name: value}} — optional
                climate / soil variables for the XGB stage.
            horizon_years: How many years to project.
            confidence_level: CI width (0.95 → 95 %).

        Returns:
            EnsembleForecastResult or None if data is insufficient.
        """
        valid = {y: v for y, v in historical_yields.items() if v and v > 0}
        if len(valid) < self.MIN_POINTS:
            return None

        years = sorted(valid.keys())
        yields = np.array([valid[y] for y in years], dtype=float)

        # ------------------------------------------------------------------
        # Stage 1: Prophet
        # ------------------------------------------------------------------
        prophet_preds, prophet_future, prophet_model = self._fit_prophet(
            years, yields, horizon_years, confidence_level
        )
        if prophet_preds is None:
            return None

        # ------------------------------------------------------------------
        # Stage 2: XGBoost on residuals
        # ------------------------------------------------------------------
        residuals = yields - prophet_preds[:len(years)]

        xgb_model = None
        xgb_future_residuals = np.zeros(horizon_years)
        feature_names: list[str] = []
        global_importance: dict[str, float] = {}
        shap_per_point: list[list[ShapContribution]] = [[] for _ in range(horizon_years)]

        if self.xgb_available and exogenous_features:
            xgb_result = self._fit_xgboost(
                years, residuals, exogenous_features, horizon_years
            )
            if xgb_result is not None:
                xgb_model, xgb_future_residuals, feature_names, global_importance, shap_per_point = xgb_result

        # ------------------------------------------------------------------
        # Combine
        # ------------------------------------------------------------------
        last_year = max(years)
        forecasts: list[EnsembleForecastPoint] = []

        for i in range(horizon_years):
            prophet_val = float(prophet_future["yhat"].iloc[i])
            prophet_lower = float(prophet_future["yhat_lower"].iloc[i])
            prophet_upper = float(prophet_future["yhat_upper"].iloc[i])

            xgb_adj = float(xgb_future_residuals[i]) if xgb_future_residuals is not None else 0.0

            predicted = max(0.0, prophet_val + xgb_adj)
            lower = max(0.0, prophet_lower + xgb_adj)
            upper = max(0.0, prophet_upper + xgb_adj)

            conf = max(0.5, confidence_level - 0.03 * (i + 1))

            forecasts.append(EnsembleForecastPoint(
                year=last_year + i + 1,
                predicted_yield=round(predicted, 2),
                lower_bound=round(lower, 2),
                upper_bound=round(upper, 2),
                confidence=round(conf, 2),
                prophet_component=round(prophet_val, 2),
                xgb_residual_component=round(xgb_adj, 2),
                shap_contributions=shap_per_point[i] if i < len(shap_per_point) else [],
            ))

        # Trend classification
        pct_change = (
            (forecasts[0].predicted_yield - yields[-1]) / yields[-1] * 100
            if yields[-1] > 0 else 0
        )
        trend = self._classify_trend(pct_change)

        return EnsembleForecastResult(
            cdk=cdk,
            crop=crop,
            historical_years=len(years),
            method="prophet_xgboost_ensemble",
            trend_direction=trend,
            forecasts=forecasts,
            model_stats={
                "prophet_data_points": float(len(years)),
                "xgb_r2": round(float(self._r2(residuals, xgb_model, years, exogenous_features, feature_names)), 4)
                if xgb_model else 0.0,
                "exogenous_features_used": feature_names,
            },
            feature_importance=global_importance,
        )

    # ------------------------------------------------------------------
    # Prophet stage
    # ------------------------------------------------------------------
    def _fit_prophet(
        self,
        years: list[int],
        yields: np.ndarray,
        horizon: int,
        confidence: float,
    ) -> tuple[np.ndarray | None, Any, Any]:
        """Fit Facebook Prophet on yearly yield data."""
        if not self.prophet_available:
            return None, None, None

        try:
            import pandas as pd
            from prophet import Prophet

            # Prophet requires a DataFrame with 'ds' and 'y' columns
            df = pd.DataFrame({
                "ds": pd.to_datetime([f"{y}-06-15" for y in years]),
                "y": yields,
            })

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = Prophet(
                    yearly_seasonality=False,
                    weekly_seasonality=False,
                    daily_seasonality=False,
                    interval_width=confidence,
                    changepoint_prior_scale=0.05,
                )
                model.fit(df)

            # Future dataframe
            future_dates = pd.DataFrame({
                "ds": pd.to_datetime(
                    [f"{years[-1] + i + 1}-06-15" for i in range(horizon)]
                )
            })

            all_dates = pd.concat([df[["ds"]], future_dates], ignore_index=True)
            forecast = model.predict(all_dates)

            historical_preds = forecast["yhat"].values[:len(years)]
            future_forecast = forecast.iloc[len(years):]

            return historical_preds, future_forecast, model

        except Exception as e:
            logger.warning(f"Prophet fitting failed: {e}")
            return None, None, None

    # ------------------------------------------------------------------
    # XGBoost stage
    # ------------------------------------------------------------------
    def _fit_xgboost(
        self,
        years: list[int],
        residuals: np.ndarray,
        exogenous: dict[int, dict[str, float]],
        horizon: int,
    ) -> tuple[Any, np.ndarray, list[str], dict[str, float], list[list[ShapContribution]]] | None:
        """Fit XGBoost on Prophet residuals using exogenous features."""
        try:
            import xgboost as xgb

            # Build feature matrix for historical years
            feature_names = sorted(
                {k for feat in exogenous.values() for k in feat.keys()}
            )
            if not feature_names:
                return None

            X_rows = []
            y_rows = []
            for i, yr in enumerate(years):
                if yr in exogenous:
                    row = [exogenous[yr].get(f, 0.0) for f in feature_names]
                    X_rows.append(row)
                    y_rows.append(residuals[i])

            if len(X_rows) < 5:
                return None

            X = np.array(X_rows)
            y = np.array(y_rows)

            model = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=3,
                learning_rate=0.1,
                subsample=0.8,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42,
                verbosity=0,
            )
            model.fit(X, y)

            # Predict future residuals (use last available features as proxy)
            last_features = exogenous.get(years[-1], {})
            future_row = np.array(
                [[last_features.get(f, 0.0) for f in feature_names]]
            )
            future_residuals = np.array([
                float(model.predict(future_row)[0]) for _ in range(horizon)
            ])

            # SHAP explanations
            global_importance: dict[str, float] = {}
            shap_per_point: list[list[ShapContribution]] = []

            if self.shap_available:
                try:
                    import shap as shap_lib
                    explainer = shap_lib.TreeExplainer(model)
                    shap_values_future = explainer.shap_values(future_row)

                    # Global importance from training data
                    shap_values_train = explainer.shap_values(X)
                    mean_abs = np.mean(np.abs(shap_values_train), axis=0)
                    global_importance = {
                        fn: round(float(v), 4)
                        for fn, v in zip(feature_names, mean_abs)
                    }

                    # Per-point contributions for future forecasts
                    for _ in range(horizon):
                        contribs = [
                            ShapContribution(
                                feature=fn,
                                value=round(float(future_row[0][j]), 4),
                                shap_value=round(float(shap_values_future[0][j]), 4),
                            )
                            for j, fn in enumerate(feature_names)
                        ]
                        shap_per_point.append(contribs)
                except Exception as e:
                    logger.warning(f"SHAP computation failed: {e}")
                    shap_per_point = [[] for _ in range(horizon)]

            return model, future_residuals, feature_names, global_importance, shap_per_point

        except Exception as e:
            logger.warning(f"XGBoost residual fitting failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _r2(
        residuals: np.ndarray,
        model: Any,
        years: list[int],
        exogenous: dict[int, dict[str, float]] | None,
        feature_names: list[str],
    ) -> float:
        """Compute R² of the XGB residual model on training data."""
        if model is None or not exogenous or not feature_names:
            return 0.0
        try:
            X = np.array([
                [exogenous.get(yr, {}).get(f, 0.0) for f in feature_names]
                for yr in years if yr in exogenous
            ])
            y_true = np.array([
                residuals[i] for i, yr in enumerate(years) if yr in exogenous
            ])
            y_pred = model.predict(X)
            ss_res = np.sum((y_true - y_pred) ** 2)
            ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
            return 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        except Exception:
            return 0.0

    @staticmethod
    def _classify_trend(pct_change: float) -> str:
        if pct_change > 5:
            return "strong_increase"
        elif pct_change > 0:
            return "mild_increase"
        elif pct_change > -5:
            return "mild_decrease"
        else:
            return "strong_decrease"
