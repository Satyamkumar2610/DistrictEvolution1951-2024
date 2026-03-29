"""
Anomaly Detection Module.
Provides automated detection of outliers, suspicious patterns, and risk alerts.
"""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import asyncpg


class AnomalyType(StrEnum):
    """Types of anomalies detected."""
    YIELD_OUTLIER = "yield_outlier"           # > 3 std from state mean
    YOY_SPIKE = "yoy_spike"                   # Year-over-year change > 50%
    MISSING_SEQUENCE = "missing_sequence"     # > 3 consecutive years missing
    CONSISTENCY_ERROR = "consistency_error"   # Area * Yield != Production
    ZERO_VALUE = "zero_value"                 # Unexpected zero values
    NEGATIVE_VALUE = "negative_value"         # Should never happen


class RiskLevel(StrEnum):
    """Risk assessment levels."""
    CRITICAL = "critical"   # Immediate attention needed
    HIGH = "high"           # Significant concern
    MEDIUM = "medium"       # Worth monitoring
    LOW = "low"             # Minor issue


@dataclass
class Anomaly:
    """Represents a detected anomaly."""
    anomaly_type: AnomalyType
    cdk: str
    year: int | None
    variable: str | None
    value: float | None
    expected_range: tuple[float, float] | None
    severity: RiskLevel
    description: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result['anomaly_type'] = self.anomaly_type.value
        result['severity'] = self.severity.value
        return result


@dataclass
class RiskAlert:
    """Risk early warning alert."""
    cdk: str
    district_name: str
    risk_level: RiskLevel
    risk_score: float  # 0-100
    factors: list[str]
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result['risk_level'] = self.risk_level.value
        return result


@dataclass
class AnomalyReport:
    """Comprehensive anomaly report for a district."""
    cdk: str
    total_anomalies: int
    anomalies_by_type: dict[str, int]
    critical_count: int
    high_count: int
    anomalies: list[Anomaly]
    risk_alert: RiskAlert | None
    scan_timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cdk": self.cdk,
            "total_anomalies": self.total_anomalies,
            "anomalies_by_type": self.anomalies_by_type,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "anomalies": [
                a.to_dict() for a in self.anomalies],
            "risk_alert": self.risk_alert.to_dict() if self.risk_alert else None,
            "scan_timestamp": self.scan_timestamp}


class AnomalyDetector:
    """
    Automated anomaly and risk detection.

    Detection Methods:
    - Statistical outliers (Z-score)
    - Year-over-year spikes (>50% change)
    - Missing data sequences (>3 consecutive years)
    - Consistency checks (production = area * yield)
    - Risk early warning (combines multiple signals)
    """

    def __init__(self, db: asyncpg.Connection):
        self.db = db
        self.yoy_threshold = 0.5  # 50% year-over-year change
        self.z_score_threshold = 3.0  # 3 standard deviations
        self.missing_sequence_threshold = 3  # 3+ consecutive missing years

    async def scan_district(self, cdk: str) -> AnomalyReport:
        """Run full anomaly scan for a district."""
        anomalies: list[Anomaly] = []

        # Run all detection methods
        anomalies.extend(await self._detect_yield_outliers(cdk))
        anomalies.extend(await self._detect_yoy_spikes(cdk))
        anomalies.extend(await self._detect_missing_sequences(cdk))
        anomalies.extend(await self._detect_consistency_errors(cdk))
        anomalies.extend(await self._detect_invalid_values(cdk))

        # Generate risk alert
        risk_alert = await self._generate_risk_alert(cdk, anomalies)

        # Count by type and severity
        by_type: dict[str, int] = {}
        critical_count = 0
        high_count = 0

        for a in anomalies:
            type_key = a.anomaly_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1
            if a.severity == RiskLevel.CRITICAL:
                critical_count += 1
            elif a.severity == RiskLevel.HIGH:
                high_count += 1

        return AnomalyReport(
            cdk=cdk,
            total_anomalies=len(anomalies),
            anomalies_by_type=by_type,
            critical_count=critical_count,
            high_count=high_count,
            anomalies=anomalies[:50],  # Limit to 50 for response size
            risk_alert=risk_alert,
            scan_timestamp=datetime.now(UTC).isoformat()
        )

    async def _detect_yield_outliers(self, cdk: str) -> list[Anomaly]:
        """Detect yields that are > 3 std from state mean."""
        anomalies: list[Anomaly] = []

        # Get district's state
        state = await self.db.fetchval("""
            SELECT state_name FROM districts WHERE lgd_code::text = $1
        """, cdk)

        if not state:
            return anomalies

        # Get state-level statistics for yield variables
        state_stats = await self.db.fetch("""
            SELECT
                am.variable_name,
                AVG(am.value) as mean_val,
                STDDEV(am.value) as std_val
            FROM agri_metrics am
            JOIN districts d ON am.district_lgd = d.lgd_code
            WHERE d.state_name = $1
            AND am.variable_name LIKE '%_yield'
            AND am.value > 0
            GROUP BY am.variable_name
            HAVING STDDEV(am.value) > 0
        """, state)

        stats_map = {row['variable_name']: (row['mean_val'], row['std_val'])
                     for row in state_stats}

        # Check district values against state stats
        district_yields = await self.db.fetch("""
            SELECT year, variable_name, value
            FROM agri_metrics
            WHERE district_lgd::text = $1 AND variable_name LIKE '%_yield' AND value > 0
        """, cdk)

        for row in district_yields:
            var = row['variable_name']
            if var not in stats_map:
                continue

            mean_val, std_val = stats_map[var]
            z_score = abs((row['value'] - mean_val) / std_val)

            if z_score > self.z_score_threshold:
                crop = var.replace('_yield', '')
                anomalies.append(
                    Anomaly(
                        anomaly_type=AnomalyType.YIELD_OUTLIER,
                        cdk=cdk,
                        year=row['year'],
                        variable=var,
                        value=row['value'],
                        expected_range=(
                            round(
                                mean_val - 2 * std_val,
                                2),
                            round(
                                mean_val + 2 * std_val,
                                2)),
                        severity=RiskLevel.HIGH if z_score > 4 else RiskLevel.MEDIUM,
                        description=f"{crop.upper()} yield {row['value']:.1f} is {z_score:.1f} std deviations from state mean"
                    )
                )

        return anomalies

    async def _detect_yoy_spikes(self, cdk: str) -> list[Anomaly]:
        """Detect year-over-year changes > 50%."""
        anomalies = []

        # Get yield time series
        yields = await self.db.fetch("""
            SELECT year, variable_name, value
            FROM agri_metrics
            WHERE district_lgd::text = $1 AND variable_name LIKE '%_yield' AND value > 0
            ORDER BY variable_name, year
        """, cdk)

        # Group by variable
        by_var: dict[str, list[tuple[int, float]]] = {}
        for row in yields:
            var = row['variable_name']
            if var not in by_var:
                by_var[var] = []
            by_var[var].append((row['year'], row['value']))

        # Check consecutive years
        for var, series in by_var.items():
            series.sort(key=lambda x: x[0])

            for i in range(1, len(series)):
                prev_year, prev_val = series[i - 1]
                curr_year, curr_val = series[i]

                # Only check consecutive years
                if curr_year - prev_year != 1:
                    continue

                if prev_val > 0:
                    pct_change = abs(curr_val - prev_val) / prev_val

                    if pct_change > self.yoy_threshold:
                        crop = var.replace('_yield', '')
                        direction = "increase" if curr_val > prev_val else "decrease"
                        anomalies.append(
                            Anomaly(
                                anomaly_type=AnomalyType.YOY_SPIKE,
                                cdk=cdk,
                                year=curr_year,
                                variable=var,
                                value=curr_val,
                                expected_range=(
                                    round(
                                        prev_val
                                        * 0.5,
                                        2),
                                    round(
                                        prev_val
                                        * 1.5,
                                        2)),
                                severity=RiskLevel.MEDIUM,
                                description=f"{crop.upper()} yield {direction} {pct_change * 100:.0f}% from {prev_year} to {curr_year}"
                            )
                        )

        return anomalies

    async def _detect_missing_sequences(self, cdk: str) -> list[Anomaly]:
        """Detect sequences of 3+ consecutive missing years."""
        anomalies: list[Anomaly] = []

        # Get years with data
        result = await self.db.fetch("""
            SELECT DISTINCT year FROM agri_metrics
            WHERE district_lgd::text = $1
            ORDER BY year
        """, cdk)

        if len(result) < 2:
            return anomalies

        years_with_data = sorted([r['year'] for r in result])
        min_year, max_year = years_with_data[0], years_with_data[-1]

        # Find gaps
        current_gap_start = None
        current_gap_length = 0

        for year in range(min_year, max_year + 1):
            if year not in years_with_data:
                if current_gap_start is None:
                    current_gap_start = year
                current_gap_length += 1
            else:
                if current_gap_length >= self.missing_sequence_threshold:
                    anomalies.append(
                        Anomaly(
                            anomaly_type=AnomalyType.MISSING_SEQUENCE,
                            cdk=cdk,
                            year=current_gap_start,
                            variable=None,
                            value=None,
                            expected_range=None,
                            severity=RiskLevel.HIGH if current_gap_length >= 5 else RiskLevel.MEDIUM,
                            description=f"Missing data for {current_gap_length} consecutive years ({current_gap_start}-{current_gap_start + current_gap_length - 1})"  # type: ignore[operator]
                        )
                    )
                current_gap_start = None
                current_gap_length = 0

        # Check final gap
        if current_gap_length >= self.missing_sequence_threshold:
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.MISSING_SEQUENCE,
                    cdk=cdk,
                    year=current_gap_start,
                    variable=None,
                    value=None,
                    expected_range=None,
                    severity=RiskLevel.HIGH if current_gap_length >= 5 else RiskLevel.MEDIUM,
                    description=f"Missing data for {current_gap_length} consecutive years ({current_gap_start}-{current_gap_start + current_gap_length - 1})"  # type: ignore[operator]
                )
            )

        return anomalies

    async def _detect_consistency_errors(self, cdk: str) -> list[Anomaly]:
        """Detect production != area * yield inconsistencies."""
        anomalies = []

        # Get all crop metrics
        metrics = await self.db.fetch("""
            SELECT year, variable_name, value
            FROM agri_metrics
            WHERE district_lgd::text = $1 AND value > 0
            ORDER BY year
        """, cdk)

        # Group by year and extract crop prefixes
        by_year: dict[int, dict[str, float]] = {}
        for row in metrics:
            year = row['year']
            if year not in by_year:
                by_year[year] = {}
            by_year[year][row['variable_name']] = row['value']

        # Check consistency for each crop
        crops = ['rice', 'wheat', 'maize', 'pulses', 'cotton']

        for year, data in by_year.items():
            for crop in crops:
                area_key = f'{crop}_area'
                prod_key = f'{crop}_production'
                yield_key = f'{crop}_yield'

                if all(k in data for k in [area_key, prod_key, yield_key]):
                    area = data[area_key]
                    prod = data[prod_key]
                    yld = data[yield_key]

                    if area > 0 and yld > 0:
                        # Expected: production = area * yield / 1000 (unit conversion)
                        # Allow tolerance for rounding
                        expected_prod = area * yld / 1000

                        if prod > 0:
                            ratio = expected_prod / prod

                            # If ratio is far from 1.0, flag it
                            if ratio < 0.3 or ratio > 3.0:
                                anomalies.append(
                                    Anomaly(
                                        anomaly_type=AnomalyType.CONSISTENCY_ERROR,
                                        cdk=cdk,
                                        year=year,
                                        variable=crop,
                                        value=prod,
                                        expected_range=(
                                            round(
                                                expected_prod * 0.8,
                                                2),
                                            round(
                                                expected_prod * 1.2,
                                                2)),
                                        severity=RiskLevel.MEDIUM,
                                        description=f"{crop.upper()} production {prod:.0f} doesn't match area×yield calculation"
                                    )
                                )

        return anomalies

    async def _detect_invalid_values(self, cdk: str) -> list[Anomaly]:
        """Detect zero or negative values where they shouldn't exist."""
        anomalies = []

        # Check for negative values (should never happen)
        negatives = await self.db.fetch("""
            SELECT year, variable_name, value
            FROM agri_metrics
            WHERE district_lgd::text = $1 AND value < 0
        """, cdk)

        for row in negatives:
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.NEGATIVE_VALUE,
                    cdk=cdk,
                    year=row['year'],
                    variable=row['variable_name'],
                    value=row['value'],
                    expected_range=(0.0, float('inf')),
                    severity=RiskLevel.CRITICAL,
                    description=f"Negative value {row['value']} for {row['variable_name']} in {row['year']}"
                )
            )

        return anomalies

    async def _generate_risk_alert(
        self,
        cdk: str,
        anomalies: list[Anomaly]
    ) -> RiskAlert | None:
        """Generate risk early warning based on anomalies and rainfall."""
        if not anomalies:
            return None

        # Get district name
        district_info = await self.db.fetchrow("""
            SELECT district_name FROM districts WHERE lgd_code::text = $1
        """, cdk)

        district_name = district_info['district_name'] if district_info else cdk

        # Calculate risk score based on anomalies
        critical_weight = 30
        high_weight = 15
        medium_weight = 5
        low_weight = 1

        risk_score = sum(
            critical_weight if a.severity == RiskLevel.CRITICAL else
            high_weight if a.severity == RiskLevel.HIGH else
            medium_weight if a.severity == RiskLevel.MEDIUM else
            low_weight
            for a in anomalies
        )

        # Cap at 100
        risk_score = min(100, risk_score)

        # Determine risk level
        if risk_score >= 70:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 40:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 20:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        # Compile risk factors
        factors = []
        if any(a.anomaly_type == AnomalyType.YIELD_OUTLIER for a in anomalies):
            factors.append(
                "Yield values significantly deviate from state average")
        if any(a.anomaly_type == AnomalyType.YOY_SPIKE for a in anomalies):
            factors.append("Volatile year-over-year yield changes detected")
        if any(a.anomaly_type == AnomalyType.MISSING_SEQUENCE for a in anomalies):
            factors.append("Significant data gaps may hide trends")
        if any(a.anomaly_type == AnomalyType.CONSISTENCY_ERROR for a in anomalies):
            factors.append("Data consistency issues affect reliability")
        if any(a.anomaly_type == AnomalyType.NEGATIVE_VALUE for a in anomalies):
            factors.append("Critical data errors require immediate correction")

        # Generate recommendation
        if risk_level == RiskLevel.CRITICAL:
            recommendation = "Immediate data review required. Do not use for decision-making until resolved."
        elif risk_level == RiskLevel.HIGH:
            recommendation = "Schedule data quality review. Cross-validate with alternative sources."
        elif risk_level == RiskLevel.MEDIUM:
            recommendation = "Flag for periodic review. Note data limitations in analyses."
        else:
            recommendation = "Standard monitoring sufficient. Minor issues noted."

        return RiskAlert(
            cdk=cdk,
            district_name=district_name,
            risk_level=risk_level,
            risk_score=round(risk_score, 1),
            factors=factors,
            recommendation=recommendation
        )


async def scan_state_anomalies(
    db: asyncpg.Connection,
    state: str,
    limit: int = 20
) -> dict[str, Any]:
    """Scan all districts in a state for anomalies."""
    # Get districts in state
    districts = await db.fetch("""
        SELECT lgd_code::text as cdk, district_name FROM districts
        WHERE state_name = $1
        LIMIT $2
    """, state, limit)

    if not districts:
        return {"error": f"No districts found for state: {state}"}

    detector = AnomalyDetector(db)
    results = []
    total_critical = 0
    total_high = 0

    for row in districts:
        report = await detector.scan_district(row['cdk'])
        total_critical += report.critical_count
        total_high += report.high_count

        results.append({
            "cdk": row['cdk'],
            "district_name": row['district_name'],
            "total_anomalies": report.total_anomalies,
            "critical": report.critical_count,
            "high": report.high_count,
            "risk_level": report.risk_alert.risk_level.value if report.risk_alert else "none",
            "risk_score": report.risk_alert.risk_score if report.risk_alert else 0
        })

    # Sort by risk score descending
    results.sort(key=lambda x: -x['risk_score'])

    return {
        "state": state,
        "districts_scanned": len(results),
        "total_critical_anomalies": total_critical,
        "total_high_anomalies": total_high,
        "high_risk_districts": [r for r in results if r['risk_score'] >= 40],
        "all_districts": results
    }
