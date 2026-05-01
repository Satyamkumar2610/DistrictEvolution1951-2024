"""
Unit tests for the anomaly detection module.
"""
from unittest.mock import AsyncMock

import pytest

from app.analytics.anomaly_detection import (
    Anomaly,
    AnomalyDetector,
    AnomalyReport,
    AnomalyType,
    RiskAlert,
    RiskLevel,
    scan_state_anomalies,
)


class TestAnomalyTypes:
    """Test anomaly type enums."""

    def test_anomaly_types_exist(self):
        assert AnomalyType.YIELD_OUTLIER == "yield_outlier"
        assert AnomalyType.YOY_SPIKE == "yoy_spike"
        assert AnomalyType.MISSING_SEQUENCE == "missing_sequence"
        assert AnomalyType.CONSISTENCY_ERROR == "consistency_error"
        assert AnomalyType.ZERO_VALUE == "zero_value"
        assert AnomalyType.NEGATIVE_VALUE == "negative_value"

    def test_risk_levels_exist(self):
        assert RiskLevel.CRITICAL == "critical"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.LOW == "low"


class TestAnomalyDataclass:
    """Test Anomaly dataclass."""

    def test_create_anomaly(self):
        anomaly = Anomaly(
            anomaly_type=AnomalyType.YIELD_OUTLIER,
            cdk="UP_agra_1971",
            year=2010,
            variable="wheat_yield",
            value=5000.0,
            expected_range=(2000.0, 3500.0),
            severity=RiskLevel.HIGH,
            description="Wheat yield is unusually high"
        )

        assert anomaly.cdk == "UP_agra_1971"
        assert anomaly.year == 2010
        assert anomaly.severity == RiskLevel.HIGH

    def test_anomaly_to_dict(self):
        anomaly = Anomaly(
            anomaly_type=AnomalyType.YOY_SPIKE,
            cdk="MH_pune_1971",
            year=2015,
            variable="rice_yield",
            value=4500.0,
            expected_range=(2000.0, 3000.0),
            severity=RiskLevel.MEDIUM,
            description="Rice yield increased by 55%"
        )

        result = anomaly.to_dict()

        assert result['anomaly_type'] == "yoy_spike"
        assert result['severity'] == "medium"
        assert result['cdk'] == "MH_pune_1971"
        assert result['year'] == 2015


class TestRiskAlert:
    """Test RiskAlert dataclass."""

    def test_create_risk_alert(self):
        alert = RiskAlert(
            cdk="TN_chennai_1971",
            district_name="Chennai",
            risk_level=RiskLevel.HIGH,
            risk_score=65.0,
            factors=["Yield volatility", "Data gaps"],
            recommendation="Schedule data quality review"
        )

        assert alert.cdk == "TN_chennai_1971"
        assert alert.risk_score == 65.0
        assert len(alert.factors) == 2

    def test_risk_alert_to_dict(self):
        alert = RiskAlert(
            cdk="GJ_ahmedabad_1971",
            district_name="Ahmedabad",
            risk_level=RiskLevel.CRITICAL,
            risk_score=85.0,
            factors=["Negative values detected"],
            recommendation="Immediate data review required"
        )

        result = alert.to_dict()

        assert result['risk_level'] == "critical"
        assert result['risk_score'] == 85.0


class TestAnomalyReport:
    """Test AnomalyReport dataclass."""

    def test_empty_report(self):
        report = AnomalyReport(
            cdk="UP_agra_1971",
            total_anomalies=0,
            anomalies_by_type={},
            critical_count=0,
            high_count=0,
            anomalies=[],
            risk_alert=None,
            scan_timestamp="2026-02-06T12:00:00"
        )

        assert report.total_anomalies == 0
        assert report.risk_alert is None

    def test_report_to_dict(self):
        anomaly = Anomaly(
            anomaly_type=AnomalyType.YIELD_OUTLIER,
            cdk="KA_bangalore_1971",
            year=2012,
            variable="cotton_yield",
            value=800.0,
            expected_range=(300.0, 500.0),
            severity=RiskLevel.HIGH,
            description="Cotton yield outlier"
        )

        alert = RiskAlert(
            cdk="KA_bangalore_1971",
            district_name="Bangalore",
            risk_level=RiskLevel.MEDIUM,
            risk_score=35.0,
            factors=["Outlier detected"],
            recommendation="Monitor quarterly"
        )

        report = AnomalyReport(
            cdk="KA_bangalore_1971",
            total_anomalies=1,
            anomalies_by_type={"yield_outlier": 1},
            critical_count=0,
            high_count=1,
            anomalies=[anomaly],
            risk_alert=alert,
            scan_timestamp="2026-02-06T12:00:00"
        )

        result = report.to_dict()

        assert result['total_anomalies'] == 1
        assert result['high_count'] == 1
        assert len(result['anomalies']) == 1
        assert result['risk_alert']['risk_level'] == "medium"


class TestAnomalyDetector:
    """Test AnomalyDetector class."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database connection."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def detector(self, mock_db):
        """Create an AnomalyDetector with mocked DB."""
        return AnomalyDetector(mock_db)

    @pytest.mark.asyncio
    async def test_detect_negative_values(self, detector, mock_db):
        """Test detection of negative values."""
        # Mock negative value query
        mock_db.fetch.return_value = [
            {'year': 2010, 'variable_name': 'wheat_yield', 'value': -100.0}
        ]

        anomalies = await detector._detect_invalid_values("TEST_cdk")

        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.NEGATIVE_VALUE
        assert anomalies[0].severity == RiskLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_no_negative_values(self, detector, mock_db):
        """Test when no negative values exist."""
        mock_db.fetch.return_value = []

        anomalies = await detector._detect_invalid_values("TEST_cdk")

        assert len(anomalies) == 0

    @pytest.mark.asyncio
    async def test_detect_missing_sequences(self, detector, mock_db):
        """Test detection of missing data sequences."""
        # Mock years with data (gap from 2005-2009)
        mock_db.fetch.return_value = [
            {'year': 2001},
            {'year': 2002},
            {'year': 2003},
            {'year': 2004},
            # Gap: 2005, 2006, 2007, 2008, 2009
            {'year': 2010},
            {'year': 2011},
        ]

        anomalies = await detector._detect_missing_sequences("TEST_cdk")

        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.MISSING_SEQUENCE
        assert anomalies[0].severity == RiskLevel.HIGH  # 5+ years gap

    @pytest.mark.asyncio
    async def test_no_missing_sequences(self, detector, mock_db):
        """Test when no significant gaps exist."""
        mock_db.fetch.return_value = [
            {'year': 2010},
            {'year': 2011},
            {'year': 2012},
            {'year': 2013},
        ]

        anomalies = await detector._detect_missing_sequences("TEST_cdk")

        assert len(anomalies) == 0

    @pytest.mark.asyncio
    async def test_detect_yoy_spikes(self, detector, mock_db):
        """Test detection of year-over-year spikes."""
        # 60% increase from 2010 to 2011
        mock_db.fetch.return_value = [
            {'year': 2010, 'variable_name': 'wheat_yield', 'value': 2000.0},
            {'year': 2011, 'variable_name': 'wheat_yield', 'value': 3200.0},  # +60%
        ]

        anomalies = await detector._detect_yoy_spikes("TEST_cdk")

        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.YOY_SPIKE
        assert "60%" in anomalies[0].description

    @pytest.mark.asyncio
    async def test_scan_district_integration(self, detector, mock_db):
        """Test full district scan."""
        # Setup mocks for all detection methods
        mock_db.fetchval.return_value = "Test State"
        mock_db.fetch.side_effect = [
            [],  # state stats for outliers
            [],  # district yields
            [],  # YoY data
            [{'year': 2010}, {'year': 2011}],  # missing sequence data
            [],  # consistency data
            [],  # negative values
        ]
        mock_db.fetchrow.return_value = {'district_name': 'Test District'}

        report = await detector.scan_district("TEST_cdk")

        assert report.cdk == "TEST_cdk"
        assert report.total_anomalies == 0
        assert isinstance(report.scan_timestamp, str)


class TestRiskAlertGeneration:
    """Test risk alert generation logic."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.fetchrow.return_value = {'district_name': 'Test District'}
        return db

    @pytest.fixture
    def detector(self, mock_db):
        return AnomalyDetector(mock_db)

    @pytest.mark.asyncio
    async def test_critical_risk_from_critical_anomalies(self, detector):
        """Test that critical anomalies produce critical risk."""
        critical_anomaly = Anomaly(
            anomaly_type=AnomalyType.NEGATIVE_VALUE,
            cdk="TEST",
            year=2010,
            variable="wheat_yield",
            value=-100.0,
            expected_range=None,
            severity=RiskLevel.CRITICAL,
            description="Negative value"
        )

        alert = await detector._generate_risk_alert("TEST", [critical_anomaly] * 3)

        assert alert is not None
        assert alert.risk_level == RiskLevel.CRITICAL
        assert alert.risk_score >= 70

    @pytest.mark.asyncio
    async def test_no_alert_for_empty_anomalies(self, detector):
        """Test no alert when no anomalies."""
        alert = await detector._generate_risk_alert("TEST", [])

        assert alert is None


class TestScanStateAnomalies:
    """Test state-level anomaly scanning."""

    @pytest.mark.asyncio
    async def test_scan_state_no_districts(self):
        """Test scanning state with no districts."""
        mock_db = AsyncMock()
        mock_db.fetch.return_value = []

        result = await scan_state_anomalies(mock_db, "Empty State", limit=10)

        assert "error" in result

    @pytest.mark.asyncio
    async def test_scan_state_with_districts(self):
        """Test scanning state with districts."""
        mock_db = AsyncMock()

        # Mock districts query
        mock_db.fetch.side_effect = [
            [{'cdk': 'TEST_1', 'district_name': 'District 1'}],  # districts
            [],  # state stats
            [],  # yields
            [],  # yoy
            [{'year': 2010}],  # missing
            [],  # consistency
            [],  # negatives
        ]
        mock_db.fetchval.return_value = "Test State"
        mock_db.fetchrow.return_value = {'district_name': 'District 1'}

        result = await scan_state_anomalies(mock_db, "Test State", limit=5)

        assert result['state'] == "Test State"
        assert result['districts_scanned'] == 1
