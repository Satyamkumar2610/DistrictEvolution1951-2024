"""
Statistical analysis module for I-ASCAP.
Provides comprehensive statistical functions for agricultural data analysis.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
from scipy import stats as scipy_stats


class TrendDirection(str, Enum):
    """Direction of a trend."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"


@dataclass
class StatisticResult:
    """Result of a statistical calculation with metadata."""
    value: float
    confidence_interval: tuple[float, float] | None = None
    p_value: float | None = None
    significant: bool | None = None
    method: str = ""


@dataclass
class TrendResult:
    """Result of trend analysis."""
    direction: TrendDirection
    slope: float
    intercept: float
    r_squared: float
    p_value: float
    significant: bool
    projected_values: list[float] | None = None


@dataclass
class RegressionResult:
    """Result of linear regression analysis."""
    slope: float
    intercept: float
    r_squared: float
    p_value: float
    std_err: float
    significant: bool


class StatisticalAnalyzer:
    """
    Comprehensive statistical analysis for time series agricultural data.
    """

    def __init__(self, confidence_level: float = 0.95):
        self.confidence_level = confidence_level
        self.alpha = 1 - confidence_level

    # -------------------------------------------------------------------------
    # Basic Statistics
    # -------------------------------------------------------------------------

    def mean(self, values: list[float]) -> float:
        """Calculate arithmetic mean."""
        if not values:
            return 0.0
        return float(np.mean(values))

    def median(self, values: list[float]) -> float:
        """Calculate median."""
        if not values:
            return 0.0
        return float(np.median(values))

    def mode(self, values: list[float]) -> float:
        """Calculate mode (most frequent value)."""
        if not values:
            return 0.0
        mode_result = scipy_stats.mode(values, keepdims=True)
        return float(mode_result.mode[0])

    def std_dev(self, values: list[float], sample: bool = True) -> float:
        """Calculate standard deviation."""
        if not values or len(values) < 2:
            return 0.0
        ddof = 1 if sample else 0
        return float(np.std(values, ddof=ddof))

    def variance(self, values: list[float], sample: bool = True) -> float:
        """Calculate variance."""
        if not values or len(values) < 2:
            return 0.0
        ddof = 1 if sample else 0
        return float(np.var(values, ddof=ddof))

    def min_max_range(self, values: list[float]) -> tuple[float, float, float]:
        """Calculate min, max, and range."""
        if not values:
            return (0.0, 0.0, 0.0)
        min_val = float(np.min(values))
        max_val = float(np.max(values))
        return (min_val, max_val, max_val - min_val)

    def quartiles(self, values: list[float]) -> dict[str, float]:
        """Calculate quartiles and IQR."""
        if not values:
            return {"q1": 0, "q2": 0, "q3": 0, "iqr": 0}
        q1, q2, q3 = np.percentile(values, [25, 50, 75])
        return {
            "q1": float(q1),
            "q2": float(q2),
            "q3": float(q3),
            "iqr": float(q3 - q1),
        }

    def percentile(self, values: list[float], p: float) -> float:
        """Calculate specific percentile."""
        if not values:
            return 0.0
        return float(np.percentile(values, p))

    def coefficient_of_variation(self, values: list[float]) -> float:
        """Calculate CV (std dev / mean as percentage)."""
        if not values:
            return 0.0
        mean = self.mean(values)
        if mean == 0:
            return 0.0
        return (self.std_dev(values) / mean) * 100

    def summary_stats(self, values: list[float]) -> dict[str, Any]:
        """Calculate comprehensive summary statistics."""
        if not values:
            return {}

        quartile_data = self.quartiles(values)
        min_val, max_val, range_val = self.min_max_range(values)

        return {
            "count": len(values),
            "mean": round(self.mean(values), 4),
            "median": round(self.median(values), 4),
            "std_dev": round(self.std_dev(values), 4),
            "variance": round(self.variance(values), 4),
            "min": round(min_val, 4),
            "max": round(max_val, 4),
            "range": round(range_val, 4),
            "q1": round(quartile_data["q1"], 4),
            "q3": round(quartile_data["q3"], 4),
            "iqr": round(quartile_data["iqr"], 4),
            "cv": round(self.coefficient_of_variation(values), 2),
        }

    # -------------------------------------------------------------------------
    # Growth Rate Calculations
    # -------------------------------------------------------------------------

    def cagr(self, start_value: float, end_value: float, years: int) -> float:
        """
        Calculate Compound Annual Growth Rate.
        CAGR = (End/Start)^(1/years) - 1
        """
        if start_value <= 0 or end_value <= 0 or years <= 0:
            return 0.0
        return (pow(end_value / start_value, 1 / years) - 1) * 100

    def year_over_year_growth(self, values: list[float]) -> list[float]:
        """Calculate year-over-year growth rates."""
        if len(values) < 2:
            return []

        growth_rates = []
        for i in range(1, len(values)):
            if values[i - 1] != 0:
                rate = ((values[i] - values[i - 1]) / values[i - 1]) * 100
                growth_rates.append(round(rate, 2))
            else:
                growth_rates.append(0.0)

        return growth_rates

    def average_growth_rate(self, values: list[float]) -> float:
        """Calculate average year-over-year growth rate."""
        yoy_rates = self.year_over_year_growth(values)
        if not yoy_rates:
            return 0.0
        return round(self.mean(yoy_rates), 2)

    # -------------------------------------------------------------------------
    # Trend Analysis
    # -------------------------------------------------------------------------

    def linear_trend(self, values: list[float]) -> TrendResult:
        """
        Perform linear regression to identify trend.
        Returns slope, intercept, R-squared, and significance.
        """
        if len(values) < 3:
            return TrendResult(
                direction=TrendDirection.STABLE,
                slope=0, intercept=0, r_squared=0,
                p_value=1.0, significant=False
            )

        x = np.arange(len(values))
        slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(
            x, values)

        r_squared = r_value ** 2
        significant = bool(p_value < self.alpha)

        # Determine direction
        if significant:
            if slope > 0:
                direction = TrendDirection.INCREASING
            elif slope < 0:
                direction = TrendDirection.DECREASING
            else:
                direction = TrendDirection.STABLE
        else:
            direction = TrendDirection.STABLE

        return TrendResult(
            direction=direction,
            slope=round(float(slope), 4),
            intercept=round(float(intercept), 4),
            r_squared=round(r_squared, 4),
            p_value=round(float(p_value), 4),
            significant=significant,
        )

    def moving_average(
            self,
            values: list[float],
            window: int = 3) -> list[float]:
        """Calculate moving average with specified window."""
        if len(values) < window:
            return values

        result = []
        for i in range(len(values)):
            start = max(0, i - window + 1)
            window_values = values[start:i + 1]
            result.append(round(self.mean(window_values), 4))

        return result

    def detect_inflection_points(
        self,
        values: list[float],
        threshold: float = 0.1
    ) -> list[int]:
        """
        Detect inflection points where trend direction changes significantly.
        Returns indices of inflection points.
        """
        if len(values) < 5:
            return []

        inflection_points = []
        smoothed = self.moving_average(values, window=3)

        for i in range(2, len(smoothed) - 2):
            before_slope = smoothed[i] - smoothed[i - 2]
            after_slope = smoothed[i + 2] - smoothed[i]

            # Check for sign change (direction reversal)
            if before_slope * after_slope < 0:
                # Check if change is significant
                if abs(after_slope - before_slope) > threshold * \
                        abs(smoothed[i]):
                    inflection_points.append(i)

        return inflection_points

    # -------------------------------------------------------------------------
    # Correlation & Regression
    # -------------------------------------------------------------------------

    def linear_regression(
            self,
            x: list[float],
            y: list[float]) -> RegressionResult:
        """
        Perform linear regression of y on x.
        Returns detailed regression statistics.
        """
        if len(x) != len(y) or len(x) < 3:
            return RegressionResult(0, 0, 0, 1.0, 0, False)

        # scipy.stats.linregress(x, y)
        slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(
            x, y)

        return RegressionResult(
            slope=float(slope),
            intercept=float(intercept),
            r_squared=float(r_value**2),
            p_value=float(p_value),
            std_err=float(std_err),
            significant=bool(p_value < self.alpha)
        )

    def pearson_correlation(
        self,
        x: list[float],
        y: list[float]
    ) -> StatisticResult:
        """Calculate Pearson correlation coefficient."""
        if len(x) != len(y) or len(x) < 3:
            return StatisticResult(
                value=0,
                p_value=1.0,
                significant=False,
                method="pearson")

        r, p_value = scipy_stats.pearsonr(x, y)

        return StatisticResult(
            value=round(float(r), 4),
            p_value=round(float(p_value), 4),
            significant=bool(p_value < self.alpha),
            method="pearson",
        )

    def spearman_correlation(
        self,
        x: list[float],
        y: list[float]
    ) -> StatisticResult:
        """Calculate Spearman rank correlation coefficient."""
        if len(x) != len(y) or len(x) < 3:
            return StatisticResult(
                value=0,
                p_value=1.0,
                significant=False,
                method="spearman")

        rho, p_value = scipy_stats.spearmanr(x, y)

        return StatisticResult(
            value=round(float(rho), 4),
            p_value=round(float(p_value), 4),
            significant=bool(p_value < self.alpha),
            method="spearman",
        )

    # -------------------------------------------------------------------------
    # Distribution Analysis
    # -------------------------------------------------------------------------

    def skewness(self, values: list[float]) -> float:
        """Calculate skewness of distribution."""
        if len(values) < 3:
            return 0.0
        return round(float(scipy_stats.skew(values)), 4)

    def kurtosis(self, values: list[float]) -> float:
        """Calculate kurtosis of distribution."""
        if len(values) < 4:
            return 0.0
        return round(float(scipy_stats.kurtosis(values)), 4)

    def normality_test(self, values: list[float]) -> StatisticResult:
        """
        Test for normality using Shapiro-Wilk test.
        Returns statistic and p-value.
        """
        if len(values) < 8:
            return StatisticResult(
                value=0,
                p_value=1.0,
                significant=False,
                method="shapiro-wilk")

        # Shapiro-Wilk has a sample size limit
        sample = values[:5000] if len(values) > 5000 else values
        stat, p_value = scipy_stats.shapiro(sample)

        return StatisticResult(
            value=round(float(stat), 4),
            p_value=round(float(p_value), 4),
            significant=bool(
                p_value >= self.alpha),
            # Significant means IS normal
            method="shapiro-wilk",
        )

    # -------------------------------------------------------------------------
    # Outlier Detection
    # -------------------------------------------------------------------------

    def detect_outliers_iqr(self, values: list[float]) -> list[int]:
        """
        Detect outliers using IQR method.
        Returns indices of outlier values.
        """
        if len(values) < 4:
            return []

        quartile_data = self.quartiles(values)
        q1 = quartile_data["q1"]
        q3 = quartile_data["q3"]
        iqr = quartile_data["iqr"]

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outliers = []
        for i, v in enumerate(values):
            if v < lower_bound or v > upper_bound:
                outliers.append(i)

        return outliers

    def detect_outliers_zscore(
        self,
        values: list[float],
        threshold: float = 3.0
    ) -> list[int]:
        """
        Detect outliers using Z-score method.
        Returns indices of outlier values.
        """
        if len(values) < 3:
            return []

        mean = self.mean(values)
        std = self.std_dev(values)

        if std == 0:
            return []

        outliers = []
        for i, v in enumerate(values):
            z_score = abs((v - mean) / std)
            if z_score > threshold:
                outliers.append(i)

        return outliers

    # -------------------------------------------------------------------------
    # Comparative Analysis
    # -------------------------------------------------------------------------

    def rank_values(
            self,
            values: list[float],
            descending: bool = True) -> list[int]:
        """
        Rank values from 1 to N.
        Higher values get rank 1 if descending=True.
        """
        if not values:
            return []

        sorted_indices = sorted(
            range(len(values)),
            key=lambda i: values[i],
            reverse=descending
        )

        ranks = [0] * len(values)
        for rank, idx in enumerate(sorted_indices, 1):
            ranks[idx] = rank

        return ranks

    def percentile_rank(
            self,
            value: float,
            reference_values: list[float]) -> float:
        """
        Calculate the percentile rank of a value within a reference set.
        Returns percentage of values that are lower.
        """
        if not reference_values:
            return 0.0

        below_count = sum(1 for v in reference_values if v < value)
        return round((below_count / len(reference_values)) * 100, 2)

    def compare_to_average(
        self,
        value: float,
        reference_values: list[float]
    ) -> dict[str, Any]:
        """
        Compare a value to the average of reference values.
        Returns absolute and percentage difference.
        """
        if not reference_values:
            return {
                "difference": 0,
                "percent_difference": 0,
                "above_average": False}

        avg = self.mean(reference_values)
        difference = value - avg
        percent_diff = (difference / avg * 100) if avg != 0 else 0

        return {
            "reference_mean": round(avg, 4),
            "difference": round(difference, 4),
            "percent_difference": round(percent_diff, 2),
            "above_average": value > avg,
            "percentile_rank": self.percentile_rank(value, reference_values),
        }


# Convenience function to get analyzer instance
def get_analyzer(confidence_level: float = 0.95) -> StatisticalAnalyzer:
    """Get a statistical analyzer instance."""
    return StatisticalAnalyzer(confidence_level)
