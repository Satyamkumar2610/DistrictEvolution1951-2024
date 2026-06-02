"""
Yield Forecasting Module.
Provides SARIMA-based time-series yield predictions with linear fallback.
"""

import logging
import math
import warnings
from dataclasses import asdict, dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ForecastPoint:
    """A single forecast point with confidence interval."""

    year: int
    predicted_yield: float
    lower_bound: float
    upper_bound: float
    confidence: float  # 0-1


@dataclass
class ForecastResult:
    """Complete forecast result with model details."""

    cdk: str
    crop: str
    historical_years: int
    method: str
    trend_direction: str
    forecasts: list[ForecastPoint]
    model_stats: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["forecasts"] = [asdict(f) for f in self.forecasts]
        return result


class YieldForecaster:
    """
    Yield forecasting using SARIMA with automatic fallback to linear regression.

    Strategy:
    - If >= 10 data points: attempt SARIMA(1,1,1) fitting
    - If SARIMA fails or < 10 points: degrade to linear regression
    - Always returns confidence intervals
    """

    SARIMA_MIN_POINTS = 10
    LINEAR_MIN_POINTS = 5

    def __init__(self):
        self._sarima_available = self._check_sarima()

    @staticmethod
    def _check_sarima() -> bool:
        """Check if statsmodels is available."""
        try:
            import statsmodels.tsa.statespace.sarimax  # noqa: F401

            return True
        except ImportError:
            logger.warning(
                "statsmodels not installed — SARIMA forecasting disabled. Install with: pip install statsmodels>=0.14.0"
            )
            return False

    def forecast(
        self,
        cdk: str,
        crop: str,
        historical_yields: dict[int, float],
        horizon_years: int = 3,
        exog_data: dict[int, list[float]] | None = None,
        confidence_level: float = 0.95,
    ) -> ForecastResult | None:
        """
        Generate yield forecasts based on historical data.

        Uses SARIMAX when sufficient data and exogenous variables are available,
        falls back to linear regression otherwise.
        """
        # Filter valid data
        valid_data = {y: v for y, v in historical_yields.items() if v and v > 0}

        if len(valid_data) < self.LINEAR_MIN_POINTS:
            return None

        years = sorted(valid_data.keys())
        yields = [valid_data[y] for y in years]
        n = len(years)

        # Try SARIMAX first
        if self._sarima_available and n >= self.SARIMA_MIN_POINTS:
            exog_list = None
            if exog_data:
                exog_list = [exog_data[y] for y in years if y in exog_data]
                if len(exog_list) != n:
                    exog_list = None  # Require complete exog data

            result = self._forecast_sarima(cdk, crop, years, yields, horizon_years, confidence_level, exog_list)
            if result is not None:
                return result
            logger.info(f"SARIMAX failed for {cdk}/{crop}, falling back to linear")

        # Fallback to linear
        return self._forecast_linear(cdk, crop, years, yields, horizon_years, confidence_level)

    # ------------------------------------------------------------------ #
    # SARIMA Forecasting
    # ------------------------------------------------------------------ #
    def _forecast_sarima(
        self,
        cdk: str,
        crop: str,
        years: list[int],
        yields: list[float],
        horizon_years: int,
        confidence_level: float,
        exog: list[list[float]] | None = None,
    ) -> ForecastResult | None:
        """Fit SARIMAX(1,1,1) and generate forecasts."""
        try:
            import numpy as np
            from statsmodels.tsa.statespace.sarimax import SARIMAX

            endog = np.array(yields, dtype=float)
            n = len(endog)

            # Suppress convergence warnings for cleaner output
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")

                best_aic = float("inf")
                best_fit = None
                best_order = (1, 1, 1)

                # Grid search for the best order based on AIC
                for p in range(3):
                    for q in range(3):
                        try:
                            exog_arr = np.array(exog, dtype=float) if exog else None
                            model = SARIMAX(
                                endog,
                                exog=exog_arr,
                                order=(p, 1, q),
                                enforce_stationarity=False,
                                enforce_invertibility=False,
                            )
                            fit = model.fit(disp=False, maxiter=200)
                            if hasattr(fit, "aic") and not np.isnan(fit.aic) and fit.aic < best_aic:
                                best_aic = fit.aic
                                best_fit = fit
                                best_order = (p, 1, q)
                        except Exception:
                            continue

                if best_fit is None:
                    raise ValueError("SARIMA grid search failed to find a valid model.")

                fit = best_fit

            # Generate forecasts with confidence intervals
            future_exog = None
            if exog is not None and len(exog) > 0:
                # Use the mean of the last 5 years to project future exogenous variables
                recent_exog = np.array(exog[-5:], dtype=float)
                mean_exog = np.mean(recent_exog, axis=0)
                future_exog = np.tile(mean_exog, (horizon_years, 1))

            forecast_obj = fit.get_forecast(steps=horizon_years, exog=future_exog)
            predicted = forecast_obj.predicted_mean
            conf_int = forecast_obj.conf_int(alpha=1 - confidence_level)

            last_year = max(years)
            forecasts = []

            for i in range(horizon_years):
                forecast_year = last_year + i + 1
                pred = float(predicted.iloc[i]) if hasattr(predicted, "iloc") else float(predicted[i])
                lower = float(conf_int.iloc[i, 0]) if hasattr(conf_int, "iloc") else float(conf_int[i, 0])
                upper = float(conf_int.iloc[i, 1]) if hasattr(conf_int, "iloc") else float(conf_int[i, 1])

                # Ensure non-negative yields
                pred = max(0, pred)
                lower = max(0, lower)
                upper = max(0, upper)

                # Confidence decreases with horizon
                conf = max(0.5, confidence_level - 0.03 * (i + 1))

                forecasts.append(
                    ForecastPoint(
                        year=forecast_year,
                        predicted_yield=round(pred, 2),
                        lower_bound=round(lower, 2),
                        upper_bound=round(upper, 2),
                        confidence=round(conf, 2),
                    )
                )

            # Model stats
            aic = float(fit.aic) if hasattr(fit, "aic") else 0.0
            bic = float(fit.bic) if hasattr(fit, "bic") else 0.0

            # Trend direction from first forecast vs last historical value
            last_yield = yields[-1]
            first_pred = forecasts[0].predicted_yield
            pct_change = ((first_pred - last_yield) / last_yield * 100) if last_yield > 0 else 0
            trend = self._classify_trend(pct_change)

            return ForecastResult(
                cdk=cdk,
                crop=crop,
                historical_years=n,
                method="sarima",
                trend_direction=trend,
                forecasts=forecasts,
                model_stats={
                    "aic": round(aic, 2),
                    "bic": round(bic, 2),
                    "data_points": float(n),
                    "order": str(best_order),
                },
            )
        except Exception as e:
            logger.warning(f"SARIMA fitting error: {e}")
            return None

    # ------------------------------------------------------------------ #
    # Linear Fallback
    # ------------------------------------------------------------------ #
    def _forecast_linear(
        self,
        cdk: str,
        crop: str,
        years: list[int],
        yields: list[float],
        horizon_years: int,
        confidence_level: float,
    ) -> ForecastResult | None:
        """Linear trend extrapolation (original method)."""
        n = len(years)
        x_mean = sum(years) / n
        y_mean = sum(yields) / n

        # Calculate slope and intercept
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(years, yields, strict=False))
        denominator = sum((x - x_mean) ** 2 for x in years)

        if denominator == 0:
            slope: float = 0.0
            intercept = y_mean
        else:
            slope = numerator / denominator
            intercept = y_mean - slope * x_mean

        # Calculate residuals for confidence interval
        predictions = [slope * x + intercept for x in years]
        residuals = [y - p for y, p in zip(yields, predictions, strict=False)]

        # Standard error of prediction
        if n > 2:
            mse = sum(r**2 for r in residuals) / (n - 2)
            se = math.sqrt(mse)
        else:
            se = sum(abs(r) for r in residuals) / n if residuals else 0

        # R-squared
        ss_tot = sum((y - y_mean) ** 2 for y in yields)
        ss_res = sum(r**2 for r in residuals)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # Generate forecasts
        last_year = max(years)
        forecasts = []
        z = 1.96 if confidence_level >= 0.95 else 1.645

        for i in range(1, horizon_years + 1):
            forecast_year = last_year + i
            predicted = slope * forecast_year + intercept

            # Wider interval further into future
            if denominator > 0:
                interval_width = z * se * math.sqrt(1 + 1 / n + (forecast_year - x_mean) ** 2 / denominator)
            else:
                interval_width = z * se * (1 + 0.1 * i)

            predicted = max(0, predicted)
            lower = max(0, predicted - interval_width)
            upper = predicted + interval_width

            conf = max(0.5, confidence_level - 0.05 * i)

            forecasts.append(
                ForecastPoint(
                    year=forecast_year,
                    predicted_yield=round(predicted, 2),
                    lower_bound=round(lower, 2),
                    upper_bound=round(upper, 2),
                    confidence=round(conf, 2),
                )
            )

        pct_change = (slope / y_mean * 100) if y_mean > 0 else 0
        trend = self._classify_trend(pct_change)

        return ForecastResult(
            cdk=cdk,
            crop=crop,
            historical_years=n,
            method="linear_fallback",
            trend_direction=trend,
            forecasts=forecasts,
            model_stats={
                "slope": round(slope, 4),
                "intercept": round(intercept, 2),
                "r_squared": round(r_squared, 4),
                "std_error": round(se, 2),
                "data_points": n,
            },
        )

    @staticmethod
    def _classify_trend(pct_change: float) -> str:
        """Classify trend direction from percentage change."""
        if pct_change > 5:
            return "strong_increase"
        elif pct_change > 0:
            return "mild_increase"
        elif pct_change > -5:
            return "mild_decrease"
        else:
            return "strong_decrease"


class CropRecommender:
    """
    Recommends crops based on historical performance and efficiency.
    """

    def __init__(self):
        self.major_crops = [
            "rice",
            "wheat",
            "maize",
            "sorghum",
            "pearl_millet",
            "chickpea",
            "pigeonpea",
            "groundnut",
            "soyabean",
            "sugarcane",
            "cotton",
        ]

    def recommend(
        self, crop_performances: dict[str, dict[str, float]], state_benchmarks: dict[str, float], top_n: int = 5
    ) -> list[dict[str, Any]]:
        """
        Recommend crops based on efficiency and growth potential.

        Args:
            crop_performances: Dict[crop] -> {yield, area, trend}
            state_benchmarks: Dict[crop] -> state average yield
            top_n: Number of recommendations

        Returns:
            List of crop recommendations with scores
        """
        recommendations = []

        for crop, data in crop_performances.items():
            if crop not in self.major_crops:
                continue

            district_yield = data.get("yield", 0)
            district_area = data.get("area", 0)
            trend = data.get("trend", 0)

            if district_yield <= 0:
                continue

            # Calculate efficiency vs state
            state_avg = state_benchmarks.get(crop, district_yield)
            efficiency = district_yield / state_avg if state_avg > 0 else 1.0

            # Score: efficiency + trend bonus
            score = efficiency * 0.7 + min(1.5, max(0.5, 1 + trend / 100)) * 0.3

            recommendations.append(
                {
                    "crop": crop,
                    "score": round(score, 3),
                    "efficiency": round(efficiency, 3),
                    "current_yield": round(district_yield, 2),
                    "state_average": round(state_avg, 2),
                    "current_area": round(district_area, 2),
                    "trend_pct": round(trend, 2),
                    "recommendation": "expand" if score > 1.1 else "maintain" if score > 0.9 else "review",
                }
            )

        # Sort by score
        recommendations.sort(key=lambda x: -float(x.get("score", 0)))  # type: ignore[arg-type]

        return recommendations[:top_n]
