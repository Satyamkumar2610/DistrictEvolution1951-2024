"""
Forecast Backtesting Panel.

Provides rigorous walk-forward validation of yield forecasting models.
Exposes real backtested performance metrics (RMSE, MAPE, coverage, bias)
via an API-ready data structure, giving users total transparency into
forecast trustworthiness.

Methodology:
    - Walk-forward (expanding window) cross-validation
    - At each step, train on years [0, ..., t] and predict year t+1
    - Compare prediction vs actual to compute error metrics
    - Track prediction intervals for coverage analysis
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BacktestStep:
    """A single walk-forward validation step."""
    train_end_year: int         # last year in training window
    forecast_year: int          # year being predicted
    actual_yield: float
    predicted_yield: float
    lower_bound: float
    upper_bound: float
    absolute_error: float
    percentage_error: float     # MAPE contribution (|actual - pred| / actual × 100)
    within_ci: bool             # did actual fall within confidence interval?
    method_used: str


@dataclass
class BacktestMetrics:
    """Aggregated backtesting performance metrics."""
    rmse: float                 # Root Mean Squared Error
    mae: float                  # Mean Absolute Error
    mape: float                 # Mean Absolute Percentage Error (%)
    bias: float                 # Mean signed error (positive = over-predicting)
    coverage_pct: float         # % of actuals falling within CI
    n_steps: int
    best_year: int | None       # year with lowest error
    worst_year: int | None      # year with highest error
    directional_accuracy: float # % of times trend direction was correct


@dataclass
class BacktestReport:
    """Complete backtesting report for a district-crop pair."""
    cdk: str
    crop: str
    forecast_method: str
    horizon: int
    confidence_level: float
    metrics: BacktestMetrics
    steps: list[BacktestStep]
    interpretation: str
    trustworthiness_grade: str  # A/B/C/D/F based on MAPE + coverage
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core Backtester
# ---------------------------------------------------------------------------

class ForecastBacktester:
    """
    Walk-forward backtesting engine for yield forecasting models.

    Accepts any forecasting function with the signature:
        forecast_fn(years, values, horizon) -> list[dict]
    where each dict has 'predicted_yield', 'lower_bound', 'upper_bound'.
    """

    def __init__(
        self,
        min_train_years: int = 8,
        horizon: int = 1,
        confidence_level: float = 0.95,
    ):
        self.min_train_years = min_train_years
        self.horizon = horizon
        self.confidence_level = confidence_level

    def backtest(
        self,
        cdk: str,
        crop: str,
        historical_yields: dict[int, float],
        forecast_fn: Callable[[list[int], list[float], int], list[dict[str, float]] | None],
        method_name: str = "unknown",
    ) -> BacktestReport | None:
        """
        Run walk-forward backtesting.

        Args:
            cdk: District identifier.
            crop: Crop name.
            historical_yields: {year: yield_kg_ha} — full history.
            forecast_fn: Function(years, values, horizon) -> [{"predicted_yield", "lower_bound", "upper_bound"}]
            method_name: Label for the method being tested.

        Returns:
            BacktestReport or None if insufficient data.
        """
        valid = {y: v for y, v in historical_yields.items() if v and v > 0}
        years = sorted(valid.keys())
        n = len(years)

        if n < self.min_train_years + 2:
            return None

        steps: list[BacktestStep] = []
        warnings_list: list[str] = []

        # Walk forward: train on [0..t], predict t+1
        for split_idx in range(self.min_train_years, n - self.horizon + 1):
            train_years = years[:split_idx]
            train_values = [valid[y] for y in train_years]
            test_year = years[split_idx]
            actual = valid[test_year]

            try:
                result = forecast_fn(train_years, train_values, self.horizon)
                if result is None or len(result) == 0:
                    continue

                pred = result[0]
                predicted = pred.get("predicted_yield", 0)
                lower = pred.get("lower_bound", predicted * 0.8)
                upper = pred.get("upper_bound", predicted * 1.2)

                abs_err = abs(actual - predicted)
                pct_err = (abs_err / actual * 100) if actual > 0 else 0
                within = lower <= actual <= upper

                steps.append(BacktestStep(
                    train_end_year=train_years[-1],
                    forecast_year=test_year,
                    actual_yield=round(actual, 2),
                    predicted_yield=round(predicted, 2),
                    lower_bound=round(lower, 2),
                    upper_bound=round(upper, 2),
                    absolute_error=round(abs_err, 2),
                    percentage_error=round(pct_err, 2),
                    within_ci=bool(within),
                    method_used=method_name,
                ))
            except Exception as e:
                logger.warning(f"Backtest step failed at split {split_idx}: {e}")

        if len(steps) < 3:
            warnings_list.append(f"Only {len(steps)} valid backtest steps — metrics may be unreliable.")

        if not steps:
            return None

        # Compute metrics
        metrics = self._compute_metrics(steps)

        # Interpretation
        interp = self._interpret(metrics, method_name)
        grade = self._grade(metrics)

        return BacktestReport(
            cdk=cdk,
            crop=crop,
            forecast_method=method_name,
            horizon=self.horizon,
            confidence_level=self.confidence_level,
            metrics=metrics,
            steps=steps,
            interpretation=interp,
            trustworthiness_grade=grade,
            warnings=warnings_list,
        )

    def backtest_compare(
        self,
        cdk: str,
        crop: str,
        historical_yields: dict[int, float],
        methods: dict[str, Callable],
    ) -> dict[str, BacktestReport | None]:
        """
        Run backtesting for multiple forecasting methods and compare results.

        Args:
            cdk: District identifier.
            crop: Crop name.
            historical_yields: Full history.
            methods: {method_name: forecast_fn}

        Returns:
            {method_name: BacktestReport}
        """
        results = {}
        for name, fn in methods.items():
            logger.info(f"Backtesting {name} for {cdk}/{crop}...")
            results[name] = self.backtest(cdk, crop, historical_yields, fn, name)
        return results

    # ------------------------------------------------------------------
    # Metrics computation
    # ------------------------------------------------------------------
    def _compute_metrics(self, steps: list[BacktestStep]) -> BacktestMetrics:
        """Compute aggregate error metrics from backtest steps."""
        n = len(steps)
        actuals = np.array([s.actual_yield for s in steps])
        preds = np.array([s.predicted_yield for s in steps])
        errors = actuals - preds

        rmse = float(np.sqrt(np.mean(errors ** 2)))
        mae = float(np.mean(np.abs(errors)))
        mape = float(np.mean([s.percentage_error for s in steps]))
        bias = float(np.mean(errors))  # negative = under-predicting

        coverage = sum(1 for s in steps if s.within_ci) / n * 100

        # Directional accuracy: did trend direction match?
        correct_dir = 0
        for i in range(1, len(steps)):
            actual_dir = steps[i].actual_yield - steps[i - 1].actual_yield
            pred_dir = steps[i].predicted_yield - steps[i - 1].predicted_yield
            if actual_dir * pred_dir >= 0:  # same sign
                correct_dir += 1
        dir_acc = (correct_dir / (n - 1) * 100) if n > 1 else 0

        # Best and worst years
        errors_abs = [s.absolute_error for s in steps]
        best_idx = int(np.argmin(errors_abs))
        worst_idx = int(np.argmax(errors_abs))

        return BacktestMetrics(
            rmse=round(rmse, 2),
            mae=round(mae, 2),
            mape=round(mape, 2),
            bias=round(bias, 2),
            coverage_pct=round(coverage, 1),
            n_steps=n,
            best_year=steps[best_idx].forecast_year,
            worst_year=steps[worst_idx].forecast_year,
            directional_accuracy=round(dir_acc, 1),
        )

    # ------------------------------------------------------------------
    # Interpretation
    # ------------------------------------------------------------------
    @staticmethod
    def _interpret(metrics: BacktestMetrics, method: str) -> str:
        parts = []

        # MAPE interpretation
        if metrics.mape < 10:
            parts.append(f"Highly accurate (MAPE {metrics.mape:.1f}%)")
        elif metrics.mape < 20:
            parts.append(f"Good accuracy (MAPE {metrics.mape:.1f}%)")
        elif metrics.mape < 30:
            parts.append(f"Moderate accuracy (MAPE {metrics.mape:.1f}%)")
        else:
            parts.append(f"Low accuracy (MAPE {metrics.mape:.1f}%) — predictions should be used with caution")

        # Coverage
        if metrics.coverage_pct >= 90:
            parts.append(f"excellent CI coverage ({metrics.coverage_pct:.0f}%)")
        elif metrics.coverage_pct >= 70:
            parts.append(f"adequate CI coverage ({metrics.coverage_pct:.0f}%)")
        else:
            parts.append(f"poor CI coverage ({metrics.coverage_pct:.0f}%) — intervals are too narrow")

        # Bias
        if abs(metrics.bias) > metrics.mae * 0.5:
            direction = "over-predicting" if metrics.bias < 0 else "under-predicting"
            parts.append(f"systematic {direction} detected (bias={metrics.bias:.1f} kg/ha)")

        return f"{method}: {'; '.join(parts)}. Based on {metrics.n_steps} walk-forward validation steps."

    @staticmethod
    def _grade(metrics: BacktestMetrics) -> str:
        """Grade forecast trustworthiness based on MAPE and coverage."""
        score = 0

        # MAPE component (0-50 points)
        if metrics.mape < 10:
            score += 50
        elif metrics.mape < 15:
            score += 40
        elif metrics.mape < 20:
            score += 30
        elif metrics.mape < 30:
            score += 15
        # else 0

        # Coverage component (0-30 points)
        if metrics.coverage_pct >= 90:
            score += 30
        elif metrics.coverage_pct >= 80:
            score += 20
        elif metrics.coverage_pct >= 70:
            score += 10

        # Direction component (0-20 points)
        if metrics.directional_accuracy >= 80:
            score += 20
        elif metrics.directional_accuracy >= 60:
            score += 10

        if score >= 80:
            return "A"
        elif score >= 60:
            return "B"
        elif score >= 40:
            return "C"
        elif score >= 20:
            return "D"
        return "F"
