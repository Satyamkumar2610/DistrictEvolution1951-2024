"""
Time series analysis utilities for I-ASCAP.
Provides functions for analyzing temporal agricultural data.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict

from scipy import stats as scipy_stats

from app.analytics.statistics import StatisticalAnalyzer


@dataclass
class AnomalyResult:
    """Result of anomaly detection."""
    index: int
    year: int
    value: float
    expected_value: float
    deviation: float
    severity: str  # "mild", "moderate", "severe"


@dataclass
class TimeSeriesAnalysis:
    """Complete time series analysis result."""
    start_year: int
    end_year: int
    data_points: int
    missing_years: List[int]
    summary_stats: Dict[str, Any]
    trend: Dict[str, Any]
    growth_rates: List[float]
    moving_averages: Dict[int, List[float]]  # window -> values
    anomalies: List[Dict]
    seasonality: Optional[Dict[str, Any]] = None


class TimeSeriesAnalyzer:
    """
    Analyzer for time series agricultural data.
    """

    def __init__(self, confidence_level: float = 0.95):
        self.stats = StatisticalAnalyzer(confidence_level)

    def analyze(
        self,
        years: List[int],
        values: List[float],
        detect_anomalies: bool = True,
        windows: List[int] = [3, 5],
    ) -> TimeSeriesAnalysis:
        """
        Perform comprehensive time series analysis.

        Args:
            years: List of years
            values: Corresponding metric values
            detect_anomalies: Whether to detect anomalies
            windows: Moving average window sizes

        Returns:
            TimeSeriesAnalysis with all results
        """
        if len(years) != len(values):
            raise ValueError("Years and values must have same length")

        if not years:
            raise ValueError("Empty time series")

        # Sort by year
        sorted_pairs = sorted(zip(years, values), key=lambda x: x[0])
        years = [p[0] for p in sorted_pairs]
        values = [p[1] for p in sorted_pairs]

        # Find missing years
        all_years = range(min(years), max(years) + 1)
        missing_years = [y for y in all_years if y not in years]

        # Calculate statistics
        summary = self.stats.summary_stats(values)
        trend = self.stats.linear_trend(values)
        growth_rates = self.stats.year_over_year_growth(values)

        # Moving averages
        moving_avgs = {}
        for window in windows:
            moving_avgs[window] = self.stats.moving_average(values, window)

        # Anomaly detection
        anomalies = []
        if detect_anomalies and len(values) >= 5:
            anomalies = self._detect_anomalies(years, values)

        return TimeSeriesAnalysis(
            start_year=min(years),
            end_year=max(years),
            data_points=len(values),
            missing_years=missing_years,
            summary_stats=summary,
            trend={
                "direction": trend.direction.value,
                "slope": trend.slope,
                "intercept": trend.intercept,
                "r_squared": trend.r_squared,
                "p_value": trend.p_value,
                "significant": trend.significant,
            },
            growth_rates=growth_rates,
            moving_averages=moving_avgs,
            anomalies=[
                asdict(a) if hasattr(  # type: ignore
                    a,
                    '__dataclass_fields__') else a for a in anomalies],
        )

    def _detect_anomalies(
        self,
        years: List[int],
        values: List[float]
    ) -> List[AnomalyResult]:
        """
        Detect anomalies using multiple methods.
        """
        anomalies = []

        # Method 1: IQR-based outliers
        iqr_outliers = self.stats.detect_outliers_iqr(values)

        # Method 2: Z-score outliers
        zscore_outliers = self.stats.detect_outliers_zscore(
            values, threshold=2.5)

        # Combine unique outliers
        all_outliers = set(iqr_outliers) | set(zscore_outliers)

        # Calculate expected values using moving average
        ma = self.stats.moving_average(values, window=3)
        mean = self.stats.mean(values)
        std = self.stats.std_dev(values)

        for idx in all_outliers:
            expected = ma[idx] if idx < len(ma) else mean
            deviation = abs(values[idx] - expected)

            # Determine severity
            if std > 0:
                z = deviation / std
                if z > 3:
                    severity = "severe"
                elif z > 2:
                    severity = "moderate"
                else:
                    severity = "mild"
            else:
                severity = "mild"

            anomalies.append(AnomalyResult(
                index=idx,
                year=years[idx],
                value=round(float(values[idx]), 2),  # type: ignore
                expected_value=round(float(expected), 2),  # type: ignore
                deviation=round(float(deviation), 2),  # type: ignore
                severity=severity,
            ))

        return sorted(anomalies, key=lambda a: a.year)

    def calculate_cumulative(self, values: List[float]) -> List[float]:
        """Calculate cumulative sum."""
        cumulative = []
        total = 0.0
        for v in values:
            total += float(v)
            cumulative.append(round(total, 4))  # type: ignore
        return cumulative

    def period_comparison(
        self,
        years: List[int],
        values: List[float],
        period1: Tuple[int, int],
        period2: Tuple[int, int],
    ) -> Dict[str, Any]:
        """
        Compare two time periods.

        Args:
            years: List of years
            values: Corresponding values
            period1: (start_year, end_year) for first period
            period2: (start_year, end_year) for second period

        Returns:
            Comparison statistics
        """
        # Extract values for each period
        data = dict(zip(years, values))

        p1_values = [
            data[y] for y in range(  # type: ignore
                period1[0],
                period1[1]
                + 1) if y in data]  # type: ignore
        p2_values = [
            data[y] for y in range(  # type: ignore
                period2[0],
                period2[1]
                + 1) if y in data]  # type: ignore

        if not p1_values or not p2_values:
            return {"error": "Insufficient data for comparison"}

        # Calculate statistics for each period
        p1_mean = self.stats.mean(p1_values)
        p2_mean = self.stats.mean(p2_values)

        # Calculate change
        absolute_change = p2_mean - p1_mean
        percent_change = (
            absolute_change
            / p1_mean
            * 100) if p1_mean != 0 else 0

        # T-test for significant difference
        if len(p1_values) >= 2 and len(p2_values) >= 2:
            t_stat, p_value = scipy_stats.ttest_ind(p1_values, p2_values)
            significant = p_value < (1 - self.stats.confidence_level)
        else:
            t_stat, p_value, significant = 0, 1, False

        return {
            "period1": {
                "years": f"{period1[0]}-{period1[1]}",
                "count": len(p1_values),
                "mean": round(p1_mean, 4),  # type: ignore
                "std_dev": round(self.stats.std_dev(p1_values), 4),  # type: ignore
            },
            "period2": {
                "years": f"{period2[0]}-{period2[1]}",
                "count": len(p2_values),
                "mean": round(p2_mean, 4),  # type: ignore
                "std_dev": round(self.stats.std_dev(p2_values), 4),  # type: ignore
            },
            "comparison": {
                "absolute_change": round(float(absolute_change), 4),  # type: ignore
                "percent_change": round(float(percent_change), 2),  # type: ignore
                "t_statistic": round(float(t_stat), 4),  # type: ignore
                "p_value": round(float(p_value), 4),  # type: ignore
                "significant": significant,
            }
        }

    def calculate_cagr_over_period(
        self,
        years: List[int],
        values: List[float],
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Calculate CAGR over a specified period.
        """
        data = dict(zip(years, values))

        start = start_year or min(years)
        end = end_year or max(years)

        if start not in data or end not in data:
            return {"error": "Start or end year not in data"}

        start_value = data[start]  # type: ignore
        end_value = data[end]  # type: ignore
        num_years = end - start

        if num_years <= 0:
            return {"error": "End year must be after start year"}

        cagr = self.stats.cagr(start_value, end_value, num_years)

        return {
            "start_year": start, "end_year": end, "start_value": round(  # type: ignore
                float(start_value), 4), "end_value": round(  # type: ignore
                float(end_value), 4), "years": num_years, "cagr": round(  # type: ignore
                float(cagr), 2), "total_growth_percent": round(  # type: ignore
                    float((end_value / start_value - 1) * 100), 2) if start_value > 0 else 0.0, }


def get_time_series_analyzer(
        confidence_level: float = 0.95) -> TimeSeriesAnalyzer:
    """Get a time series analyzer instance."""
    return TimeSeriesAnalyzer(confidence_level)
