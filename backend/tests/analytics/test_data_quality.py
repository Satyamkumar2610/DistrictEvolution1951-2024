"""
Unit tests for the data quality module.
"""
from unittest.mock import AsyncMock

import pytest

from app.analytics.data_quality import (
    DataQualityReport,
    DataQualityScorer,
    QualityLevel,
    get_state_quality_summary,
)


class TestQualityLevel:
    """Test QualityLevel enum."""

    def test_quality_levels_exist(self):
        assert QualityLevel.EXCELLENT == "excellent"
        assert QualityLevel.GOOD == "good"
        assert QualityLevel.FAIR == "fair"
        assert QualityLevel.POOR == "poor"


class TestDataQualityReport:
    """Test DataQualityReport dataclass."""

    def test_create_report(self):
        report = DataQualityReport(
            cdk="UP_agra_1971",
            completeness_score=0.85,
            consistency_score=0.90,
            timeliness_score=0.75,
            accuracy_score=0.95,
            overall_score=0.86,
            quality_level=QualityLevel.GOOD,
            issues=["Data may be outdated"],
            recommendations=["Update with latest statistics"]
        )

        assert report.cdk == "UP_agra_1971"
        assert report.overall_score == 0.86
        assert report.quality_level == QualityLevel.GOOD

    def test_report_to_dict(self):
        report = DataQualityReport(
            cdk="MH_pune_1971",
            completeness_score=0.95,
            consistency_score=0.98,
            timeliness_score=0.90,
            accuracy_score=0.92,
            overall_score=0.94,
            quality_level=QualityLevel.EXCELLENT,
            issues=[],
            recommendations=[]
        )

        result = report.to_dict()

        assert result['quality_level'] == "excellent"
        assert result['overall_score'] == 0.94
        assert isinstance(result['issues'], list)


class TestDataQualityScorer:
    """Test DataQualityScorer class."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database connection."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def scorer(self, mock_db):
        """Create a DataQualityScorer with mocked DB."""
        return DataQualityScorer(mock_db)

    @pytest.mark.asyncio
    async def test_check_completeness_full(self, scorer, mock_db):
        """Test completeness score with full data."""
        # 52 years expected (1966-2017)
        mock_db.fetchval.return_value = 52

        score = await scorer._check_completeness("TEST_cdk")

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_check_completeness_partial(self, scorer, mock_db):
        """Test completeness score with partial data."""
        # Only 26 years of data (50%)
        mock_db.fetchval.return_value = 26

        score = await scorer._check_completeness("TEST_cdk")

        assert 0.49 <= score <= 0.51

    @pytest.mark.asyncio
    async def test_check_completeness_no_data(self, scorer, mock_db):
        """Test completeness score with no data."""
        mock_db.fetchval.return_value = None

        score = await scorer._check_completeness("TEST_cdk")

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_check_timeliness_current(self, scorer, mock_db):
        """Test timeliness score with current data."""
        mock_db.fetchval.return_value = 2017  # max_year

        score = await scorer._check_timeliness("TEST_cdk")

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_check_timeliness_old(self, scorer, mock_db):
        """Test timeliness score with old data."""
        mock_db.fetchval.return_value = 2007  # 10 years behind

        score = await scorer._check_timeliness("TEST_cdk")

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_check_accuracy_no_outliers(self, scorer, mock_db):
        """Test accuracy with normal data."""
        # Values with no outliers (all close to mean)
        mock_db.fetch.return_value = [
            {'value': 2500},
            {'value': 2600},
            {'value': 2550},
            {'value': 2450},
            {'value': 2525},
        ]

        score = await scorer._check_accuracy("TEST_cdk")

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_check_accuracy_with_outliers(self, scorer, mock_db):
        """Test accuracy with outliers."""
        # 10 normal values clustered around 100, with 1 extreme value at 1000
        # Mean ≈ 181, Std ≈ 270, z-score of 1000 ≈ 3.03 (just over threshold)
        mock_db.fetch.return_value = [
            {'value': 100},
            {'value': 102},
            {'value': 98},
            {'value': 101},
            {'value': 99},
            {'value': 103},
            {'value': 97},
            {'value': 100},
            {'value': 101},
            {'value': 99},
            {'value': 1000},  # Extreme outlier - z-score > 3
        ]

        score = await scorer._check_accuracy("TEST_cdk")

        # With 1 outlier in 11 values, score should be ~0.91
        assert score < 1.0

    @pytest.mark.asyncio
    async def test_check_accuracy_insufficient_data(self, scorer, mock_db):
        """Test accuracy with insufficient data."""
        mock_db.fetch.return_value = [
            {'value': 2500},
            {'value': 2600},
        ]

        score = await scorer._check_accuracy("TEST_cdk")

        assert score == 1.0  # Returns 1.0 when not enough data

    @pytest.mark.asyncio
    async def test_check_consistency_with_matching_data(self, scorer, mock_db):
        """Test consistency with matching area * yield = production."""
        mock_db.fetch.return_value = [
            {'year': 2010, 'variable_name': 'rice_area', 'value': 100.0},
            {'year': 2010, 'variable_name': 'rice_production', 'value': 250.0},
            {'year': 2010, 'variable_name': 'rice_yield', 'value': 2500.0},  # 100 * 2500 / 1000 = 250
        ]

        score = await scorer._check_consistency("TEST_cdk")

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_score_district_excellent(self, scorer, mock_db):
        """Test scoring a district with excellent data."""
        mock_db.fetchval.side_effect = [52, 2017]  # completeness, timeliness
        mock_db.fetch.side_effect = [
            [],  # consistency (no rice data = 1.0)
            [{'value': 2500}, {'value': 2600}, {'value': 2550}, {'value': 2450}, {'value': 2525}],  # accuracy
        ]

        report = await scorer.score_district("TEST_cdk")

        assert report.cdk == "TEST_cdk"
        assert report.quality_level == QualityLevel.EXCELLENT
        assert report.overall_score >= 0.9


class TestGetStateQualitySummary:
    """Test state-level quality summary function."""

    @pytest.mark.asyncio
    async def test_no_districts(self):
        """Test with no districts in state."""
        mock_db = AsyncMock()
        mock_db.fetch.return_value = []

        result = await get_state_quality_summary(mock_db, "Empty State")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_with_districts(self):
        """Test with districts in state."""
        mock_db = AsyncMock()

        # First call: get districts
        # Subsequent calls: scorer methods
        mock_db.fetch.side_effect = [
            [{'cdk': 'TEST_1'}, {'cdk': 'TEST_2'}],  # districts
            [],  # consistency 1
            [{'value': 2500}, {'value': 2600}, {'value': 2550}, {'value': 2450}, {'value': 2525}],  # accuracy 1
            [],  # consistency 2
            [{'value': 2500}, {'value': 2600}, {'value': 2550}, {'value': 2450}, {'value': 2525}],  # accuracy 2
        ]
        mock_db.fetchval.side_effect = [52, 2017, 52, 2017]

        result = await get_state_quality_summary(mock_db, "Test State")

        assert result['state'] == "Test State"
        assert result['districts_analyzed'] == 2
        assert 'average_quality_score' in result
        assert 'quality_distribution' in result
