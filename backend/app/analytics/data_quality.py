"""
Data Quality Scoring Module.
Provides automated data quality assessment for districts.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

import asyncpg


class QualityLevel(str, Enum):
    """Data quality classification."""
    EXCELLENT = "excellent"  # 90-100%
    GOOD = "good"           # 70-89%
    FAIR = "fair"           # 50-69%
    POOR = "poor"           # <50%


@dataclass
class DataQualityReport:
    """Comprehensive data quality report for a district."""
    cdk: str
    completeness_score: float  # % of years with data
    consistency_score: float   # Cross-metric validation
    timeliness_score: float    # How recent is data
    accuracy_score: float      # Outlier/anomaly detection
    overall_score: float
    quality_level: QualityLevel
    issues: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["quality_level"] = self.quality_level.value
        return result


class DataQualityScorer:
    """
    Automated data quality assessment.

    Scoring Components:
    - Completeness: % of years with at least one metric
    - Consistency: Cross-validation between related metrics
    - Timeliness: How recent is the latest data
    - Accuracy: Detection of outliers and anomalies
    """

    def __init__(self, db: asyncpg.Connection):
        self.db = db
        # Expected year range
        self.min_year = 1966
        self.max_year = 2017
        self.expected_years = self.max_year - self.min_year + 1

    async def score_district(self, cdk: str) -> DataQualityReport:
        """Generate comprehensive quality report for a district."""
        issues = []
        recommendations = []

        # 1. Completeness Score
        completeness = await self._check_completeness(cdk)
        if completeness < 0.5:
            issues.append(f"Low data coverage: only {completeness * 100:.0f}% of years have data")
            recommendations.append("Consider data interpolation for missing years")

        # 2. Consistency Score
        consistency = await self._check_consistency(cdk)
        if consistency < 0.8:
            issues.append("Potential data inconsistencies detected")
            recommendations.append(
                "Review yield calculation: production/area mismatch")

        # 3. Timeliness Score
        timeliness = await self._check_timeliness(cdk)
        if timeliness < 0.7:
            issues.append("Data may be outdated")
            recommendations.append("Update with latest available statistics")

        # 4. Accuracy Score
        accuracy = await self._check_accuracy(cdk)
        if accuracy < 0.8:
            issues.append("Potential outliers detected in yield values")
            recommendations.append(
                "Review extreme values for data entry errors")

        # Calculate weighted overall score
        overall = (
            completeness * 0.35
            + consistency * 0.25
            + timeliness * 0.15
            + accuracy * 0.25
        )

        # Determine quality level
        if overall >= 0.9:
            level = QualityLevel.EXCELLENT
        elif overall >= 0.7:
            level = QualityLevel.GOOD
        elif overall >= 0.5:
            level = QualityLevel.FAIR
        else:
            level = QualityLevel.POOR

        return DataQualityReport(
            cdk=cdk,
            completeness_score=round(completeness, 3),
            consistency_score=round(consistency, 3),
            timeliness_score=round(timeliness, 3),
            accuracy_score=round(accuracy, 3),
            overall_score=round(overall, 3),
            quality_level=level,
            issues=issues,
            recommendations=recommendations
        )

    async def _check_completeness(self, cdk: str) -> float:
        """Check % of years with data."""
        result = await self.db.fetchval("""
            SELECT COUNT(DISTINCT year)
            FROM agri_metrics
            WHERE district_lgd::text = $1 AND year >= $2 AND year <= $3
        """, cdk, self.min_year, self.max_year)

        years_with_data = result or 0
        return min(1.0, years_with_data / self.expected_years)

    async def _check_consistency(self, cdk: str) -> float:
        """
        Check consistency between related metrics.
        E.g., production should roughly equal area * yield
        """
        # Check rice metrics as example
        result = await self.db.fetch("""
            SELECT year, variable_name, value
            FROM agri_metrics
            WHERE district_lgd::text = $1
            AND variable_name IN ('rice_area', 'rice_production', 'rice_yield')
            ORDER BY year, variable_name
        """, cdk)

        if len(result) < 3:
            return 1.0  # Not enough data to check

        # Group by year
        by_year: dict[int, dict[str, float]] = {}
        for row in result:
            year = row['year']
            if year not in by_year:
                by_year[year] = {}
            by_year[year][row['variable_name']] = row['value']

        # Check consistency: yield ≈ production/area
        consistent_years = 0
        total_years = 0

        for year, data in by_year.items():
            if all(
                k in data for k in [
                    'rice_area',
                    'rice_production',
                    'rice_yield']):
                total_years += 1
                area = data['rice_area']
                prod = data['rice_production']
                yld = data['rice_yield']

                if area > 0:
                    # Assuming production in '000 tonnes
                    expected_yield = (prod / area) * 1000
                    if yld > 0 and 0.5 <= expected_yield / yld <= 2.0:  # Within 2x tolerance
                        consistent_years += 1

        return consistent_years / total_years if total_years > 0 else 1.0

    async def _check_timeliness(self, cdk: str) -> float:
        """Check how recent the data is."""
        result = await self.db.fetchval("""
            SELECT MAX(year)
            FROM agri_metrics
            WHERE district_lgd::text = $1
        """, cdk)

        latest_year = result or self.min_year
        years_behind = self.max_year - latest_year

        # Score: 1.0 if up to date, decreasing linearly
        return max(0.0, 1.0 - (years_behind / 10))

    async def _check_accuracy(self, cdk: str) -> float:
        """
        Check for outliers using Z-score approach.
        Returns 1.0 if no outliers, decreasing with more outliers.
        """
        # Get yield values
        result = await self.db.fetch("""
            SELECT value
            FROM agri_metrics
            WHERE district_lgd::text = $1 AND variable_name LIKE '%_yield' AND value > 0
        """, cdk)

        if len(result) < 5:
            return 1.0  # Not enough data

        values = [r['value'] for r in result]

        # Calculate mean and std
        mean_val = sum(values) / len(values)
        variance = sum((v - mean_val) ** 2 for v in values) / len(values)
        std_val = variance ** 0.5

        if std_val == 0:
            return 1.0

        # Count outliers (|z| > 3)
        outliers = sum(1 for v in values if abs((v - mean_val) / std_val) > 3)

        return max(0.0, 1.0 - (outliers / len(values)))


async def get_state_quality_summary(
    db: asyncpg.Connection,
    state: str
) -> dict[str, Any]:
    """Get aggregated quality metrics for a state."""
    # Get all CDKs in state
    cdks = await db.fetch("""
        SELECT lgd_code::text as cdk FROM districts WHERE state_name = $1
    """, state)

    if not cdks:
        return {"error": f"No districts found for state: {state}"}

    scorer = DataQualityScorer(db)
    reports = []

    for row in cdks[:20]:  # Limit to 20 for performance
        report = await scorer.score_district(row['cdk'])
        reports.append(report)

    # Aggregate
    avg_score = sum(r.overall_score for r in reports) / len(reports)
    quality_dist = {level.value: 0 for level in QualityLevel}
    for r in reports:
        quality_dist[r.quality_level.value] += 1

    return {
        "state": state,
        "districts_analyzed": len(reports),
        "average_quality_score": round(avg_score, 3),
        "quality_distribution": quality_dist,
        "top_issues": _aggregate_issues(reports)
    }


def _aggregate_issues(reports: list[DataQualityReport]) -> list[str]:
    """Aggregate common issues across reports."""
    issue_counts: dict[str, int] = {}
    for r in reports:
        for issue in r.issues:
            # Normalize issue text
            key = issue.split(":")[0] if ":" in issue else issue
            issue_counts[key] = issue_counts.get(key, 0) + 1

    # Return top 5 most common issues
    sorted_issues = sorted(issue_counts.items(), key=lambda x: -x[1])
    return [f"{issue} ({count} districts)" for issue,
            count in sorted_issues[:5]]
