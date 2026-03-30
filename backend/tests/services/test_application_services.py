import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call, patch

import pytest
from fastapi import Response

from app.analytics.advanced import SimulationResult
from app.exceptions import NotFoundError, ValidationError
from app.schemas.lineage import DistrictHistoryItem, TrackingCoverage, TrackingDistrict
from app.services.advanced_analytics_service import AdvancedAnalyticsFacade
from app.services.anomaly_service import AnomalyService
from app.services.climate_service import ClimateService
from app.services.forecast_service import ForecastService
from app.services.lineage_service import LineageService
from app.services.report_service import ReportService
from app.services.search_service import SearchService
from app.services.simulation_service import SimulationService
from app.services.spatial_service import SpatialService
from app.services.state_service import StateService


@pytest.mark.asyncio
async def test_search_service_combines_results_and_applies_limit(mock_db):
    service = SearchService(mock_db)
    service.repo = AsyncMock()
    service.repo.search_districts = AsyncMock(
        return_value=[
            {
                "cdk": "BR_patna_1991",
                "name": "Patna",
                "state": "Bihar",
                "result_type": "district",
                "start_year": 1991,
            }
        ]
    )
    service.repo.search_states = AsyncMock(
        return_value=[
            {
                "name": "Bihar",
                "state": "Bihar",
                "result_type": "state",
                "district_count": 38,
            },
            {
                "name": "Bihar Rural",
                "state": "Bihar",
                "result_type": "state",
                "district_count": 10,
            },
        ]
    )

    result = await service.search_response("Bi", "all", 2)

    assert result.query == "Bi"
    assert result.total == 3
    assert len(result.results) == 2
    assert result.results[0].cdk == "BR_patna_1991"
    assert result.results[1].district_count == 38


@pytest.mark.asyncio
async def test_state_service_builds_overview_with_default_year(mock_db):
    service = StateService(mock_db)
    service.repo = AsyncMock()
    service.repo.state_exists = AsyncMock(return_value=True)
    service.repo.get_total_districts = AsyncMock(return_value=38)
    service.repo.get_year_range = AsyncMock(return_value={"min_year": 1966, "max_year": 2017})
    service.repo.get_avg_yield = AsyncMock(return_value=2420.5)
    service.repo.get_performers = AsyncMock(
        side_effect=[
            [{"district_name": "Patna", "cdk": "BR_patna_1991", "yield_value": 2800.0}],
            [{"district_name": "Gaya", "cdk": "BR_gaya_1991", "yield_value": 1500.0}],
        ]
    )
    service.repo.get_metric_totals = AsyncMock(
        return_value={"total_area": 4200.0, "total_production": 9100.0}
    )
    service.repo.count_districts_with_data = AsyncMock(return_value=32)
    service.repo.get_available_crops = AsyncMock(return_value=["rice", "wheat"])

    overview = await service.get_overview("Bihar", "rice")

    assert overview.year == 2017
    assert overview.total_districts == 38
    assert overview.avg_yield == 2420.5
    assert overview.top_performers[0].district_name == "Patna"
    assert overview.bottom_performers[0].district_name == "Gaya"
    assert overview.available_crops == ["rice", "wheat"]


@pytest.mark.asyncio
async def test_state_service_raises_not_found_for_missing_state(mock_db):
    service = StateService(mock_db)
    service.repo = AsyncMock()
    service.repo.state_exists = AsyncMock(return_value=False)

    with pytest.raises(NotFoundError):
        await service.get_overview("Missing", "rice")


@pytest.mark.asyncio
async def test_state_service_lists_state_counts(mock_db):
    service = StateService(mock_db)
    service.repo = AsyncMock()
    service.repo.list_state_counts = AsyncMock(
        return_value=[
            {"state": "Bihar", "district_count": 38},
            {"state": "Odisha", "district_count": 30},
        ]
    )

    result = await service.list_states()

    assert [(item.state, item.district_count) for item in result] == [
        ("Bihar", 38),
        ("Odisha", 30),
    ]


@pytest.mark.asyncio
async def test_report_service_returns_json_report(mock_db):
    service = ReportService(mock_db)
    service.repo = AsyncMock()
    service.repo.get_district_context = AsyncMock(
        return_value={"district_name": "Patna", "state_name": "Bihar"}
    )
    service.repo.get_crop_metric_history = AsyncMock(
        return_value=[
            {"year": 2018, "variable_name": "rice_yield", "value": 1800},
            {"year": 2018, "variable_name": "rice_area", "value": 100},
            {"year": 2019, "variable_name": "rice_yield", "value": 2400},
            {"year": 2019, "variable_name": "rice_area", "value": 120},
            {"year": 2020, "variable_name": "rice_yield", "value": 3000},
            {"year": 2020, "variable_name": "rice_area", "value": 130},
        ]
    )
    service.repo.get_state_average_yield = AsyncMock(return_value=2200.0)

    report = await service.get_district_profile_report("BR_patna_1991", "rice", "json")

    assert report.district.name == "Patna"
    assert report.statistics.mean_yield == 2400.0
    assert report.statistics.mean_area == 116.67
    assert report.state_benchmark.efficiency == 1.091
    assert report.yearly_data[0]["year"] == 2018


@pytest.mark.asyncio
async def test_report_service_returns_csv_response(mock_db):
    service = ReportService(mock_db)
    service.repo = AsyncMock()
    service.repo.get_district_context = AsyncMock(
        return_value={"district_name": "Patna", "state_name": "Bihar"}
    )
    service.repo.get_crop_metric_history = AsyncMock(return_value=[])
    service.repo.get_state_average_yield = AsyncMock(return_value=None)
    exporter = SimpleNamespace(
        to_csv_response=Mock(
            return_value=Response(content="year,yield\n", media_type="text/csv")
        )
    )

    with patch("app.services.report_service.get_exporter", return_value=exporter):
        response = await service.get_district_profile_report("BR_patna_1991", "rice", "csv")

    assert isinstance(response, Response)
    exporter.to_csv_response.assert_called_once()


@pytest.mark.asyncio
async def test_report_service_raises_not_found_when_district_missing(mock_db):
    service = ReportService(mock_db)
    service.repo = AsyncMock()
    service.repo.get_district_context = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.get_district_profile_report("missing", "rice", "json")


@pytest.mark.asyncio
async def test_forecast_service_returns_crop_recommendations(mock_db):
    service = ForecastService(mock_db)
    service.repo = AsyncMock()
    service.recommender = SimpleNamespace(recommend=Mock())
    service.repo.get_district_context = AsyncMock(
        return_value={"district_name": "Patna", "state_name": "Bihar"}
    )

    async def latest_snapshot_side_effect(cdk, crop):
        if crop == "rice":
            return {"yield": 2500.0, "area": 200.0}
        if crop == "wheat":
            return {"yield": 1800.0, "area": 100.0}
        return None

    service.repo.get_latest_crop_snapshot = AsyncMock(side_effect=latest_snapshot_side_effect)
    service.repo.get_recent_variable_history = AsyncMock(
        side_effect=[
            [{"year": 2020, "value": 2000}, {"year": 2015, "value": 1600}],
            [{"year": 2020, "value": 1800}, {"year": 2015, "value": 1500}],
        ]
    )
    service.repo.get_state_average_yield = AsyncMock(
        side_effect=lambda state, crop: {"rice": 2200.0, "wheat": 1700.0}.get(crop)
    )
    service.recommender.recommend.return_value = [
        {
            "crop": "rice",
            "score": 1.2,
            "efficiency": 1.14,
            "current_yield": 2500.0,
            "state_average": 2200.0,
            "current_area": 200.0,
            "trend_pct": 4.56,
            "recommendation": "expand",
        }
    ]

    result = await service.get_crop_recommendations_response("BR_patna_1991", 1)

    assert result.district == "Patna"
    assert result.recommendations[0].crop == "rice"
    service.recommender.recommend.assert_called_once()


@pytest.mark.asyncio
async def test_forecast_service_raises_validation_when_no_crop_data(mock_db):
    service = ForecastService(mock_db)
    service.repo = AsyncMock()
    service.repo.get_district_context = AsyncMock(
        return_value={"district_name": "Patna", "state_name": "Bihar"}
    )
    service.repo.get_latest_crop_snapshot = AsyncMock(return_value=None)

    with pytest.raises(ValidationError):
        await service.get_crop_recommendations_response("BR_patna_1991", 3)


@pytest.mark.asyncio
async def test_forecast_service_returns_yield_forecast(mock_db):
    service = ForecastService(mock_db)
    service.repo = AsyncMock()
    service.forecaster = SimpleNamespace(forecast=Mock())
    service.repo.get_district_context = AsyncMock(
        return_value={"district_name": "Patna", "state_name": "Bihar"}
    )
    service.repo.get_historical_yields = AsyncMock(
        return_value=[
            {"year": 2016, "yield": 1500.0},
            {"year": 2017, "yield": 1650.0},
            {"year": 2018, "yield": 1800.0},
            {"year": 2019, "yield": 2000.0},
            {"year": 2020, "yield": 2200.0},
        ]
    )
    service.forecaster.forecast.return_value = SimpleNamespace(
        to_dict=lambda: {
            "cdk": "BR_patna_1991",
            "crop": "rice",
            "historical_years": 5,
            "method": "linear_fallback",
            "trend_direction": "increasing",
            "forecasts": [
                {
                    "year": 2021,
                    "predicted_yield": 2300.0,
                    "lower_bound": 2200.0,
                    "upper_bound": 2400.0,
                    "confidence": 0.8,
                }
            ],
            "model_stats": {"slope": 200.0},
        }
    )

    result = await service.get_yield_forecast_response("BR_patna_1991", "rice", 1)

    assert result.forecasts[0].year == 2021
    service.forecaster.forecast.assert_called_once()


@pytest.mark.asyncio
async def test_forecast_service_rejects_insufficient_history(mock_db):
    service = ForecastService(mock_db)
    service.repo = AsyncMock()
    service.repo.get_district_context = AsyncMock(
        return_value={"district_name": "Patna", "state_name": "Bihar"}
    )
    service.repo.get_historical_yields = AsyncMock(return_value=[{"year": 2020, "yield": 2200.0}])

    with pytest.raises(ValidationError):
        await service.get_yield_forecast_response("BR_patna_1991", "rice", 2)


@pytest.mark.asyncio
async def test_forecast_service_calculates_cagr_trend(mock_db):
    service = ForecastService(mock_db)
    service.repo = AsyncMock()
    service.repo.get_recent_variable_history = AsyncMock(
        return_value=[
            {"year": 2020, "value": 200.0},
            {"year": 2015, "value": 100.0},
        ]
    )

    trend = await service._calculate_trend("BR_patna_1991", "rice_yield")

    assert trend == pytest.approx(14.87, abs=0.01)


@pytest.mark.asyncio
async def test_anomaly_service_runs_district_scan(mock_db):
    service = AnomalyService(mock_db)
    service.repo = AsyncMock()
    service.detector = AsyncMock()
    service.repo.district_exists = AsyncMock(return_value=True)
    service.detector.scan_district = AsyncMock(
        return_value=SimpleNamespace(
            to_dict=lambda: {
                "cdk": "BR_patna_1991",
                "total_anomalies": 2,
                "anomalies_by_type": {"yield_spike": 1, "rainfall_shock": 1},
                "critical_count": 1,
                "high_count": 1,
                "anomalies": [],
                "risk_alert": {
                    "cdk": "BR_patna_1991",
                    "district_name": "Patna",
                    "risk_level": "high",
                    "risk_score": 42.0,
                    "factors": ["yield volatility"],
                    "recommendation": "Inspect irrigation exposure",
                },
                "scan_timestamp": "2025-01-01T00:00:00Z",
            }
        )
    )

    result = await service.scan_district_response("BR_patna_1991")

    assert result.total_anomalies == 2
    assert result.risk_alert is not None
    assert result.risk_alert.risk_score == 42.0


@pytest.mark.asyncio
async def test_anomaly_service_raises_not_found_for_missing_district(mock_db):
    service = AnomalyService(mock_db)
    service.repo = AsyncMock()
    service.repo.district_exists = AsyncMock(return_value=False)

    with pytest.raises(NotFoundError):
        await service.scan_district_response("missing")


@pytest.mark.asyncio
async def test_anomaly_service_state_scan_and_high_risk_sorting(mock_db):
    service = AnomalyService(mock_db)
    service.repo = AsyncMock()
    service.detector = AsyncMock()
    service.repo.get_active_district_sample = AsyncMock(
        return_value=[
            {"cdk": "A", "state_name": "Bihar"},
            {"cdk": "B", "state_name": "Bihar"},
            {"cdk": "C", "state_name": "Bihar"},
        ]
    )

    service.detector.scan_district = AsyncMock(
        side_effect=[
            SimpleNamespace(
                risk_alert=SimpleNamespace(
                    district_name="Alpha",
                    risk_score=35.0,
                    risk_level=SimpleNamespace(value="medium"),
                    factors=["factor-a"],
                )
            ),
            SimpleNamespace(
                risk_alert=SimpleNamespace(
                    district_name="Beta",
                    risk_score=48.0,
                    risk_level=SimpleNamespace(value="high"),
                    factors=["factor-b"],
                )
            ),
            SimpleNamespace(risk_alert=None),
        ]
    )

    with patch(
        "app.services.anomaly_service.scan_state_anomalies",
        AsyncMock(
            return_value={
                "state": "Bihar",
                "districts_scanned": 3,
                "total_critical_anomalies": 1,
                "total_high_anomalies": 2,
                "high_risk_districts": [],
                "all_districts": [],
            }
        ),
    ):
        state_result = await service.scan_state_response("Bihar", 5)

    high_risk = await service.get_high_risk_districts_response(2)

    assert state_result.state == "Bihar"
    assert high_risk.total_scanned == 6
    assert [item.cdk for item in high_risk.high_risk_districts] == ["B", "A"]


@pytest.mark.asyncio
async def test_anomaly_service_raises_not_found_when_state_scan_fails(mock_db):
    service = AnomalyService(mock_db)

    with patch(
        "app.services.anomaly_service.scan_state_anomalies",
        AsyncMock(return_value={"error": "State not found"}),
    ), pytest.raises(NotFoundError):
        await service.scan_state_response("Missing", 5)


@pytest.mark.asyncio
async def test_climate_service_returns_rainfall_views(mock_db):
    service = ClimateService(mock_db)
    rainfall = SimpleNamespace(
        state="Bihar",
        district="Patna",
        jan=12.0,
        feb=15.0,
        mar=18.0,
        apr=20.0,
        may=35.0,
        jun=110.0,
        jul=220.0,
        aug=240.0,
        sep=180.0,
        oct=65.0,
        nov=20.0,
        dec=10.0,
        winter_jf=27.0,
        pre_monsoon_mam=73.0,
        monsoon_jjas=750.0,
        post_monsoon_ond=95.0,
        annual=945.0,
    )

    with patch(
        "app.services.climate_service.get_rainfall_count",
        AsyncMock(return_value=120),
    ), patch(
        "app.services.climate_service.get_rainfall_by_district",
        AsyncMock(return_value=rainfall),
    ), patch(
        "app.services.climate_service.get_all_rainfall",
        AsyncMock(
            return_value=[
                {
                    "state": "Bihar",
                    "district": "Patna",
                    "annual": 945.0,
                    "monsoon": 750.0,
                }
            ]
        ),
    ), patch(
        "app.services.climate_service.get_state_rainfall_stats",
        AsyncMock(
            return_value={
                "state": "Bihar",
                "district_count": 1,
                "avg_annual_mm": 945.0,
                "min_annual_mm": 945.0,
                "max_annual_mm": 945.0,
                "avg_monsoon_mm": 750.0,
            }
        ),
    ), patch(
        "app.services.climate_service.get_water_stress_index",
        AsyncMock(
            return_value=[
                {
                    "district_name": "Patna",
                    "cdk": "BR_patna_1991",
                    "total_area": 320.0,
                    "water_intensive_area": 180.0,
                    "water_intensive_share": 0.56,
                    "annual_rainfall": 945.0,
                    "mismatch_score": 0.41,
                    "category": "medium",
                    "crop_breakdown": {"rice": 120.0},
                }
            ]
        ),
    ):
        stats = await service.get_rainfall_stats()
        district = await service.get_rainfall("Bihar", "Patna")
        rainfall_map = await service.get_all_rainfall_data("Bihar")
        state_stats = await service.get_state_stats("Bihar")
        stress = await service.get_water_stress("Bihar", 2020)

    assert stats.status == "loaded"
    assert district.monthly.jul == 220.0
    assert rainfall_map[0].district == "Patna"
    assert state_stats.avg_monsoon_mm == 750.0
    assert stress.districts[0].category == "medium"


@pytest.mark.asyncio
async def test_climate_service_handles_empty_or_missing_climate_data(mock_db):
    service = ClimateService(mock_db)

    with patch(
        "app.services.climate_service.get_rainfall_count",
        AsyncMock(return_value=0),
    ):
        stats = await service.get_rainfall_stats()

    assert stats.status == "empty"

    with patch(
        "app.services.climate_service.get_rainfall_by_district",
        AsyncMock(return_value=None),
    ), pytest.raises(NotFoundError):
        await service.get_rainfall("Bihar", "Missing")

    with patch(
        "app.services.climate_service.get_state_rainfall_stats",
        AsyncMock(return_value={"error": "not found"}),
    ), pytest.raises(NotFoundError):
        await service.get_state_stats("Missing")

    with patch(
        "app.services.climate_service.get_water_stress_index",
        AsyncMock(return_value=[]),
    ), pytest.raises(NotFoundError):
        await service.get_water_stress("Bihar", 2020)


@pytest.mark.asyncio
async def test_climate_service_builds_rainfall_yield_correlation_with_seasonal_fallback(mock_db):
    service = ClimateService(mock_db)
    service.repo = AsyncMock()
    service.repo.get_state_yield_rows = AsyncMock(
        side_effect=[
            [
                {"district_name": "A", "yield_val": 1200.0},
                {"district_name": "B", "yield_val": 1300.0},
                {"district_name": "C", "yield_val": 1400.0},
            ],
            [
                {"district_name": "A", "yield_val": 1200.0},
                {"district_name": "B", "yield_val": 1300.0},
                {"district_name": "C", "yield_val": 1400.0},
                {"district_name": "D", "yield_val": 1500.0},
                {"district_name": "E", "yield_val": 1600.0},
            ],
        ]
    )
    analyzer = SimpleNamespace(
        pearson_correlation=Mock(
            side_effect=[
                SimpleNamespace(value=0.62),
                SimpleNamespace(value=-0.31),
            ]
        )
    )

    async def rainfall_side_effect(_conn, _state, district_name):
        index = ord(district_name) - ord("A")
        return SimpleNamespace(
            annual=900.0 + index * 10.0,
            monsoon_jjas=700.0 + index * 5.0,
        )

    with patch(
        "app.services.climate_service.get_rainfall_by_district",
        AsyncMock(side_effect=rainfall_side_effect),
    ), patch("app.services.climate_service.get_analyzer", return_value=analyzer):
        result = await service.get_rainfall_yield_correlation("Bihar", "rice", 2020)

    assert result.sample_size == 5
    assert result.correlations.annual_rainfall.interpretation == "strong"
    assert result.correlations.monsoon_rainfall.direction == "negative"
    assert result.data_points[0].yield_ == 1200.0
    assert service.repo.get_state_yield_rows.await_args_list == [
        call("Bihar", "rice_yield", 2020),
        call("Bihar", "rice_yield_kharif", 2020),
    ]


@pytest.mark.asyncio
async def test_climate_service_rejects_insufficient_yield_or_rainfall_matches(mock_db):
    service = ClimateService(mock_db)
    service.repo = AsyncMock()
    service.repo.get_state_yield_rows = AsyncMock(
        side_effect=[
            [
                {"district_name": "A", "yield_val": 1200.0},
                {"district_name": "B", "yield_val": 1300.0},
                {"district_name": "C", "yield_val": 1400.0},
                {"district_name": "D", "yield_val": 1500.0},
            ],
            [
                {"district_name": "A", "yield_val": 1200.0},
                {"district_name": "B", "yield_val": 1300.0},
                {"district_name": "C", "yield_val": 1400.0},
                {"district_name": "D", "yield_val": 1500.0},
                {"district_name": "E", "yield_val": 1600.0},
            ],
        ]
    )

    with pytest.raises(ValidationError):
        await service.get_rainfall_yield_correlation("Bihar", "millet", 2020)

    with patch(
        "app.services.climate_service.get_rainfall_by_district",
        AsyncMock(
            side_effect=[
                SimpleNamespace(annual=900.0, monsoon_jjas=700.0),
                SimpleNamespace(annual=910.0, monsoon_jjas=705.0),
                SimpleNamespace(annual=920.0, monsoon_jjas=710.0),
                SimpleNamespace(annual=930.0, monsoon_jjas=715.0),
                None,
            ]
        ),
    ), pytest.raises(ValidationError):
        await service.get_rainfall_yield_correlation("Bihar", "wheat", 2020)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.1, "negligible"),
        (0.3, "weak"),
        (0.5, "moderate"),
        (0.7, "strong"),
        (0.9, "very strong"),
    ],
)
def test_climate_service_interprets_correlation_strengths(mock_db, value, expected):
    service = ClimateService(mock_db)

    metric = service._build_correlation_metric(-value)

    assert metric.direction == "negative"
    assert metric.interpretation == expected


@pytest.mark.asyncio
async def test_lineage_service_returns_history_events_tracking_and_coverage(mock_db):
    service = LineageService(mock_db)
    service.district_repo = AsyncMock()
    service.lineage_repo = AsyncMock()
    service.lineage_repo.get_district_history = AsyncMock(
        return_value=[
            DistrictHistoryItem(
                state_name="Bihar",
                split_year=2001,
                parent_district="Patna",
                child_district="Patna",
                source="gazette",
            )
        ]
    )
    service.lineage_repo.get_all_events = AsyncMock(
        return_value=[
            {
                "id": "evt-1",
                "parent_cdk": "BR_patna_1991",
                "parent_name": "Patna",
                "children_cdks": ["BR_patna_2001"],
                "children_names": ["Patna"],
                "children_count": 1,
                "event_year": 2001,
                "event_type": "split",
                "coverage_ratios": {"BR_patna_2001": 1.0},
                "confidence": 1.0,
            }
        ]
    )
    service.lineage_repo.get_tracking_district = AsyncMock(
        return_value=TrackingDistrict(
            cdk="BR_patna_1991",
            district_name="Patna",
            state_name="Bihar",
            start_year=1991,
            end_year=2020,
        )
    )
    service.lineage_repo.get_tracking_coverage = AsyncMock(
        return_value=TrackingCoverage(
            years_with_data=20,
            first_year=2001,
            last_year=2020,
            variables=4,
            total_records=80,
        )
    )
    service.lineage_repo.get_state_coverage = AsyncMock(
        return_value=[
            {
                "cdk": "BR_patna_1991",
                "district_name": "Patna",
                "start_year": 1991,
                "end_year": 2020,
                "years_with_data": 20,
                "record_count": 80,
                "lineage_status": "tracked",
            }
        ]
    )

    history = await service.get_district_history_response("Bihar")
    events = await service.get_lineage_events_response()
    tracking = await service.get_data_tracking_response("BR_patna_1991")
    coverage = await service.get_state_coverage_response("Bihar")

    assert history[0].state_name == "Bihar"
    assert events.total_events == 1
    assert tracking.data_sources[0].record_count == 80
    assert coverage.coverage[0].district_name == "Patna"


@pytest.mark.asyncio
async def test_lineage_service_filters_events_by_state(mock_db):
    service = LineageService(mock_db)
    service.district_repo = AsyncMock()
    service.lineage_repo = AsyncMock()
    service.district_repo.get_cdk_to_meta_map = AsyncMock(
        return_value={
            "BR_patna_1991": {"state": "Bihar"},
            "OR_khordha_1991": {"state": "Odisha"},
        }
    )
    service.lineage_repo.get_events_by_state = AsyncMock(
        return_value=[
            {
                "id": "evt-2",
                "parent_cdk": "BR_patna_1991",
                "parent_name": "Patna",
                "children_cdks": ["BR_patna_2001"],
                "children_names": ["Patna"],
                "children_count": 1,
                "event_year": 2001,
                "event_type": "split",
                "coverage_ratios": {"BR_patna_2001": 1.0},
                "confidence": 1.0,
            }
        ]
    )

    events = await service.get_lineage_events_response("Bihar")

    assert events.total_events == 1
    service.lineage_repo.get_events_by_state.assert_awaited_once_with(
        "Bihar",
        {"BR_patna_1991": "Bihar", "OR_khordha_1991": "Odisha"},
    )


@pytest.mark.asyncio
async def test_lineage_service_raises_not_found_for_missing_tracking_district(mock_db):
    service = LineageService(mock_db)
    service.lineage_repo = AsyncMock()
    service.lineage_repo.get_tracking_district = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.get_data_tracking_response("missing")


@pytest.mark.asyncio
async def test_lineage_service_collects_sorted_unmapped_splits(mock_db):
    service = LineageService(mock_db)
    service.district_repo = AsyncMock()
    service.lineage_repo = AsyncMock()
    service.district_repo.get_lgd_lookup = AsyncMock(
        return_value={
            ("purnia", "bihar"): 101,
            ("patna", "bihar"): 102,
        }
    )
    service.lineage_repo.get_split_name_rows = AsyncMock(
        return_value=[
            {
                "state_name": "Bihar",
                "split_year": "2001",
                "parent_district": "Purnea",
                "child_district": "Patna",
            },
            {
                "state_name": "Bihar",
                "split_year": 2002,
                "parent_district": "Legacy",
                "child_district": "Historical",
            },
            {
                "state_name": "Bihar",
                "split_year": 2002,
                "parent_district": "Legacy",
                "child_district": "Historical",
            },
            {
                "state_name": "Bihar",
                "split_year": 2003,
                "parent_district": "Legacy",
                "child_district": "Unknown Child",
            },
        ]
    )

    with patch(
        "app.services.lineage_service.check_historical_resolution",
        side_effect=lambda _state, district: district == "Historical",
    ):
        result = await service.get_unmapped_splits_response()

    assert [(item.district, item.year, item.role) for item in result] == [
        ("Legacy", 2002, "Parent"),
        ("Legacy", 2003, "Parent"),
        ("Unknown Child", 2003, "Child"),
    ]


def test_lineage_service_resolves_lgd_direct_alias_and_telangana_paths(mock_db):
    service = LineageService(mock_db)
    lgd_lookup = {
        ("purnia", "bihar"): 101,
        ("daman", "the dadra and nagar haveli and daman and diu"): 202,
        ("hyderabad", "telangana"): 303,
    }

    assert service._resolve_lgd("Purnea", "Bihar", lgd_lookup) == 101
    assert service._resolve_lgd("Daman", "Daman and Diu", lgd_lookup) == 202
    assert service._resolve_lgd("Hyderabad", "Andhra Pradesh", lgd_lookup) == 303
    assert service._resolve_lgd("Unknown", "Bihar", lgd_lookup) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("simpson_index", "expected"),
    [
        (0.8, "diverse"),
        (0.5, "moderately diverse"),
        (0.2, "concentrated"),
    ],
)
async def test_advanced_analytics_diversification_interpretation(
    mock_db,
    simpson_index,
    expected,
):
    service = AdvancedAnalyticsFacade(mock_db)
    service.analytics = AsyncMock()
    service.analytics.get_crop_diversification = AsyncMock(
        return_value=SimpleNamespace(
            cdk="BR_patna_1991",
            year=2020,
            simpson_index=simpson_index,
            herfindahl_index=0.4,
            num_crops=3,
            dominant_crop="rice",
            dominant_share=65.0,
            breakdown={"rice": 65.0, "wheat": 20.0, "maize": 15.0},
        )
    )

    response = await service.get_crop_diversification_response("BR_patna_1991", 2020)

    assert response.interpretation == expected
    assert response.dominant_share == pytest.approx(0.65)


@pytest.mark.asyncio
async def test_advanced_analytics_raises_not_found_for_missing_diversification_or_shift(mock_db):
    service = AdvancedAnalyticsFacade(mock_db)
    service.analytics = AsyncMock()
    service.analytics.get_crop_diversification = AsyncMock(return_value=None)
    service.analytics.get_crop_shift = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.get_crop_diversification_response("missing", 2020)

    with pytest.raises(NotFoundError):
        await service.get_crop_shift_response("missing")


@pytest.mark.asyncio
async def test_advanced_analytics_wraps_crop_shift_timeline(mock_db):
    service = AdvancedAnalyticsFacade(mock_db)
    service.analytics = AsyncMock()
    service.analytics.get_crop_shift = AsyncMock(
        return_value=[
            {
                "year": 2020,
                "total_area": 120.0,
                "shannon_index": 1.1,
                "simpson_index": 0.72,
                "dominant_crop": "rice",
                "dominant_share": 62.0,
                "crop_mix": {"rice": 62.0, "wheat": 38.0},
            }
        ]
    )

    response = await service.get_crop_shift_response("BR_patna_1991")

    assert response.timeline[0].dominant_crop == "rice"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("volatility", "expected"),
    [
        (5.0, "low"),
        (18.0, "medium"),
        (35.0, "high"),
    ],
)
async def test_advanced_analytics_builds_yield_trend_risk_assessment(
    mock_db,
    volatility,
    expected,
):
    service = AdvancedAnalyticsFacade(mock_db)
    service.analytics = AsyncMock()
    service.analytics.get_yield_trend = AsyncMock(
        return_value=SimpleNamespace(
            crop="rice",
            start_year=2010,
            end_year=2020,
            start_yield=1800.0,
            end_yield=2400.0,
            cagr=2.9,
            volatility=volatility,
            trend="increasing",
        )
    )

    response = await service.get_yield_trend_response("BR_patna_1991", "rice", 2010, 2020)

    assert response.risk_assessment == expected
    assert response.period == "2010-2020"


@pytest.mark.asyncio
async def test_advanced_analytics_raises_not_found_for_missing_yield_trend(mock_db):
    service = AdvancedAnalyticsFacade(mock_db)
    service.analytics = AsyncMock()
    service.analytics.get_yield_trend = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.get_yield_trend_response("missing", "rice", 2010, 2020)


@pytest.mark.asyncio
async def test_advanced_analytics_wraps_structured_responses(mock_db):
    service = AdvancedAnalyticsFacade(mock_db)
    service.analytics = AsyncMock()
    service.analytics.get_split_impact = AsyncMock(
        return_value={
            "parent_cdk": "BR_parent_1991",
            "child_cdks": ["BR_a_2001", "BR_b_2001"],
            "split_year": 2001,
            "crop": "rice",
            "before": {
                "years": [1999, 2000],
                "yields": [1800.0, 1900.0],
                "average": 1850.0,
            },
            "after": {
                "by_child": {
                    "BR_a_2001": {"yields": [2000.0], "avg": 2000.0},
                    "BR_b_2001": {"yields": [2100.0], "avg": 2100.0},
                },
                "combined_average": 2050.0,
            },
            "impact": {
                "absolute_change": 200.0,
                "percent_change": 10.81,
                "assessment": "positive",
            },
        }
    )
    service.analytics.get_crop_correlations = AsyncMock(
        return_value={
            "state": "Bihar",
            "year": 2020,
            "crops": ["rice", "wheat"],
            "correlations": {"rice": {"wheat": 0.42}, "wheat": {"rice": 0.42}},
        }
    )
    service.analytics.get_district_rankings = AsyncMock(
        return_value=[
            {
                "rank": 1,
                "cdk": "BR_patna_1991",
                "district": "Patna",
                "value": 2450.0,
            }
        ]
    )
    service.analytics.get_seasonal_comparison = AsyncMock(
        return_value={
            "cdk": "BR_patna_1991",
            "crop": "rice",
            "year": 2020,
            "kharif_yield": 2400.0,
            "rabi_yield": 1800.0,
            "dominant_season": "kharif",
        }
    )
    service.analytics.get_post_split_specialization = AsyncMock(
        return_value={
            "split_year": 2001,
            "crops": ["rice", "wheat"],
            "parent": {
                "name": "Patna",
                "cdk": "BR_parent_1991",
                "pre_mix": {"rice": 70.0, "wheat": 30.0},
            },
            "children": {
                "BR_a_2001": {"cdk": "BR_a_2001", "mix": {"rice": 80.0}},
                "BR_b_2001": {"cdk": "BR_b_2001", "mix": {"wheat": 60.0}},
            },
            "divergence_scores": {"BR_a_2001": 0.2, "BR_b_2001": 0.3},
        }
    )

    split_impact = await service.get_split_impact_response(
        "BR_parent_1991",
        ["BR_a_2001", "BR_b_2001"],
        2001,
        "rice",
        2,
        2,
    )
    correlations = await service.get_crop_correlations_response("Bihar", 2020, None)
    rankings = await service.get_district_rankings_response("Bihar", "rice", 2020, "yield")
    seasonal = await service.get_seasonal_comparison_response("BR_patna_1991", "rice", 2020)
    specialization = await service.get_split_specialization_response(
        "BR_parent_1991",
        ["BR_a_2001", "BR_b_2001"],
        2001,
    )

    assert split_impact.after.combined_average == 2050.0
    assert correlations.correlations["rice"]["wheat"] == 0.42
    assert rankings[0].district == "Patna"
    assert seasonal.dominant_season == "kharif"
    assert specialization.parent.name == "Patna"


@pytest.mark.asyncio
async def test_advanced_analytics_builds_yoy_growth_summary(mock_db):
    service = AdvancedAnalyticsFacade(mock_db)
    service.analytics = AsyncMock()
    service.analytics.get_yoy_growth = AsyncMock(
        return_value=[
            {"year": 2018, "yield": 1800.0, "yoy_growth": None},
            {"year": 2019, "yield": 2100.0, "yoy_growth": 16.67},
            {"year": 2020, "yield": 2000.0, "yoy_growth": -4.76},
        ]
    )

    response = await service.get_yoy_growth_response("BR_patna_1991", "rice", 2018, 2020)

    assert response.summary.average_yoy_growth_percent == 5.96
    assert response.summary.positive_growth_years == 1
    assert response.summary.negative_growth_years == 1


@pytest.mark.asyncio
async def test_advanced_analytics_builds_summary_response(mock_db):
    service = AdvancedAnalyticsFacade(mock_db)
    service.analytics = AsyncMock()
    service.analytics.get_crop_diversification = AsyncMock(
        return_value=SimpleNamespace(
            simpson_index=0.71,
            num_crops=4,
            dominant_crop="rice",
        )
    )
    service.analytics.get_yield_trend = AsyncMock(
        side_effect=[
            SimpleNamespace(cagr=2.4, trend="increasing"),
            None,
        ]
    )

    response = await service.get_summary_response("BR_patna_1991", 2020)

    assert response.diversification is not None
    assert response.diversification.num_crops == 4
    assert response.trends.rice is not None
    assert response.trends.rice.cagr == 2.4
    assert response.trends.wheat is None


@pytest.mark.asyncio
async def test_advanced_analytics_handles_yield_forecast_success_and_failure(mock_db):
    service = AdvancedAnalyticsFacade(mock_db)
    service.analytics = AsyncMock()
    service.analytics.get_yield_forecast = AsyncMock(
        side_effect=[
            {
                "cdk": "BR_patna_1991",
                "crop": "rice",
                "historical_trend": "upward",
                "slope": 42.0,
                "forecast": [
                    {
                        "year": 2021,
                        "projected_yield": 2450.0,
                        "confidence_interval_lower": 2300.0,
                        "confidence_interval_upper": 2600.0,
                    }
                ],
            },
            {"error": "insufficient history"},
        ]
    )

    response = await service.get_yield_forecast_response("BR_patna_1991", "rice", 1)

    assert response.forecast[0].projected_yield == 2450.0

    with pytest.raises(ValidationError):
        await service.get_yield_forecast_response("BR_patna_1991", "rice", 2)


@pytest.mark.asyncio
async def test_advanced_analytics_handles_resilience_and_yield_gap(mock_db):
    service = AdvancedAnalyticsFacade(mock_db)
    service.analytics = AsyncMock()
    service.analytics.get_resilience_index = AsyncMock(
        side_effect=[
            [
                {
                    "cdk": "BR_patna_1991",
                    "district_name": "Patna",
                    "data_points": 10,
                    "avg_yield": 2400.0,
                    "avg_shock_drop_pct": 8.0,
                    "avg_recovery_years": 1.2,
                    "resilience_score": 0.82,
                    "rank": 1,
                }
            ],
            [],
        ]
    )
    service.analytics.get_yield_gap = AsyncMock(
        side_effect=[
            {
                "state": "Bihar",
                "crop": "rice",
                "period": "2010-2020",
                "convergence_timeline": [
                    {
                        "year": 2020,
                        "frontier_yield": 3000.0,
                        "state_avg_yield": 2200.0,
                        "avg_gap": 800.0,
                    }
                ],
                "district_rankings": [
                    {
                        "cdk": "BR_patna_1991",
                        "district_name": "Patna",
                        "avg_gap": 500.0,
                        "latest_gap": 450.0,
                        "avg_yield": 2500.0,
                        "gap_trend": -20.0,
                        "status": "improving",
                        "rank": 1,
                    }
                ],
            },
            {"error": "state not found"},
        ]
    )

    resilience = await service.get_resilience_index_response("Bihar", "rice")
    gap = await service.get_yield_gap_response("Bihar", "rice", 2010, 2020)

    assert resilience.total_districts == 1
    assert gap.district_rankings[0].status == "improving"

    with pytest.raises(NotFoundError):
        await service.get_resilience_index_response("Missing", "rice")

    with pytest.raises(NotFoundError):
        await service.get_yield_gap_response("Missing", "rice", 2010, 2020)


@pytest.mark.asyncio
async def test_simulation_service_returns_cached_responses(mock_db):
    service = SimulationService(mock_db)
    cache = SimpleNamespace(
        get=AsyncMock(
            side_effect=[
                {"status": "cached-simulation"},
                {"status": "cached-prediction"},
            ]
        ),
        set=AsyncMock(),
    )

    with patch("app.services.simulation_service.get_cache", return_value=cache):
        simulation = await service.get_simulation_response("Patna", "rice", 2020, "Bihar")
        prediction = await service.get_prediction_v2_response("Patna", "rice", 2020, "Bihar")

    assert simulation == {"status": "cached-simulation"}
    assert prediction == {"status": "cached-prediction"}
    cache.set.assert_not_called()


@pytest.mark.asyncio
async def test_simulation_service_builds_simulation_response_with_fallback_and_cache(mock_db):
    service = SimulationService(mock_db)
    service.repo = AsyncMock()
    service.repo.get_state_yield_rows = AsyncMock(
        side_effect=[
            [
                {"district_name": "A", "yield": 1800.0},
                {"district_name": "B", "yield": 1900.0},
                {"district_name": "C", "yield": 2000.0},
            ],
            [
                {"district_name": "A", "yield": 1800.0},
                {"district_name": "B", "yield": 1900.0},
                {"district_name": "C", "yield": 2000.0},
                {"district_name": "D", "yield": 2100.0},
                {"district_name": "E", "yield": 2200.0},
            ],
        ]
    )
    service.repo.get_state_rainfall_rows = AsyncMock(
        return_value=[
            {"district": "A", "annual": 900.0},
            {"district": "B", "annual": 910.0},
            {"district": "C", "annual": 920.0},
            {"district": "D", "annual": 930.0},
            {"district": "E", "annual": 940.0},
        ]
    )
    cache = SimpleNamespace(get=AsyncMock(return_value=None), set=AsyncMock())
    analyzer = SimpleNamespace(
        calculate_impact_simulation=Mock(
            return_value=SimulationResult(
                baseline_yield=2000.0,
                slope=1.2,
                intercept=850.0,
                r_squared=0.76,
                correlation=0.87,
                confidence_interval=120.0,
                data_points=[{"rainfall": 900.0, "yield": 1800.0}],
                model_equation="yield = 1.2x + 850",
            )
        )
    )

    with patch("app.services.simulation_service.get_cache", return_value=cache), patch(
        "app.services.simulation_service.get_advanced_analyzer",
        return_value=analyzer,
    ):
        response = await service.get_simulation_response("Patna", "rice", 2020, "Bihar")

    assert response.result.baseline_yield == 2000.0
    assert response.validity is not None
    assert service.repo.get_state_yield_rows.await_args_list == [
        call("Bihar", "rice_yield", 2020),
        call("Bihar", "rice_yield_kharif", 2020),
    ]
    cache.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_simulation_service_rejects_insufficient_simulation_inputs(mock_db):
    service = SimulationService(mock_db)
    service.repo = AsyncMock()
    cache = SimpleNamespace(get=AsyncMock(return_value=None), set=AsyncMock())

    service.repo.get_state_yield_rows = AsyncMock(
        return_value=[
            {"district_name": "A", "yield": 1800.0},
            {"district_name": "B", "yield": 1900.0},
            {"district_name": "C", "yield": 2000.0},
            {"district_name": "D", "yield": 2100.0},
        ]
    )

    with patch("app.services.simulation_service.get_cache", return_value=cache), pytest.raises(
        NotFoundError
    ):
        await service.get_simulation_response("Patna", "millet", 2020, "Bihar")

    service.repo.get_state_yield_rows = AsyncMock(
        return_value=[
            {"district_name": "A", "yield": 1800.0},
            {"district_name": "B", "yield": 1900.0},
            {"district_name": "C", "yield": 2000.0},
            {"district_name": "D", "yield": 2100.0},
            {"district_name": "E", "yield": 2200.0},
        ]
    )
    service.repo.get_state_rainfall_rows = AsyncMock(
        return_value=[
            {"district": "A", "annual": 900.0},
            {"district": "B", "annual": 910.0},
            {"district": "C", "annual": 920.0},
            {"district": "D", "annual": 0.0},
            {"district": "E", "annual": None},
        ]
    )

    with patch("app.services.simulation_service.get_cache", return_value=cache), pytest.raises(
        NotFoundError
    ):
        await service.get_simulation_response("Patna", "rice", 2020, "Bihar")


def test_simulation_service_builds_prediction_district_data(mock_db):
    service = SimulationService(mock_db)

    district_data = service._build_prediction_district_data(
        yield_rows=[
            {"district_name": "A", "yield": 1800.0},
            {"district_name": "B", "yield": 1900.0},
        ],
        rain_map={
            "A": {"annual": 900.0, "monsoon_jjas": 700.0},
            "B": {"annual": 0.0, "monsoon_jjas": 0.0},
        },
        hist_map={
            "A": [
                (2016, 1500.0),
                (2017, 1600.0),
                (2018, 1700.0),
                (2019, 1800.0),
                (2020, 1900.0),
            ]
        },
        area_map={"A": 120.0},
    )

    assert len(district_data) == 1
    assert district_data[0]["district"] == "A"
    assert district_data[0]["yield_trend"] > 0
    assert district_data[0]["yield_cv"] > 0
    assert district_data[0]["crop_area"] == 120.0


@pytest.mark.asyncio
async def test_simulation_service_builds_prediction_v2_response_and_caches(mock_db):
    service = SimulationService(mock_db)
    service.repo = AsyncMock()
    service.repo.get_state_yield_rows = AsyncMock(
        return_value=[
            {"district_name": "A", "yield": 1800.0},
            {"district_name": "B", "yield": 1900.0},
            {"district_name": "C", "yield": 2000.0},
            {"district_name": "D", "yield": 2100.0},
            {"district_name": "E", "yield": 2200.0},
        ]
    )
    service.repo.get_state_rainfall_rows = AsyncMock(
        return_value=[
            {"district": "A", "annual": 900.0, "jjas": 700.0},
            {"district": "B", "annual": 910.0, "jjas": 705.0},
            {"district": "C", "annual": 920.0, "jjas": 710.0},
            {"district": "D", "annual": 930.0, "jjas": 715.0},
            {"district": "E", "annual": 940.0, "jjas": 720.0},
        ]
    )
    service.repo.get_state_historical_yields = AsyncMock(
        return_value=[
            {"district_name": district, "year": year, "value": value}
            for district, offset in zip(["A", "B", "C", "D", "E"], range(5), strict=True)
            for year, value in [
                (2016, 1500.0 + offset * 50),
                (2017, 1600.0 + offset * 50),
                (2018, 1700.0 + offset * 50),
                (2019, 1800.0 + offset * 50),
                (2020, 1900.0 + offset * 50),
            ]
        ]
    )
    service.repo.get_state_area_rows = AsyncMock(
        return_value=[
            {"district_name": "A", "area": 100.0},
            {"district_name": "B", "area": 110.0},
            {"district_name": "C", "area": 120.0},
            {"district_name": "D", "area": 130.0},
            {"district_name": "E", "area": 140.0},
        ]
    )
    cache = SimpleNamespace(get=AsyncMock(return_value=None), set=AsyncMock())
    engine = SimpleNamespace(
        predict=Mock(
            return_value=SimpleNamespace(
                to_dict=lambda: {
                    "predicted_yield": 2350.0,
                    "baseline_yield": 2100.0,
                    "confidence_lower": 2200.0,
                    "confidence_upper": 2500.0,
                    "slope_rain": 1.5,
                    "mean_rain": 920.0,
                    "r_squared": 0.82,
                    "adjusted_r_squared": 0.76,
                    "rmse": 115.0,
                    "sample_size": 5,
                    "feature_count": 5,
                    "method": "multi_factor_ridge",
                    "factors": [
                        {
                            "name": "Rainfall",
                            "key": "rainfall",
                            "importance": 0.52,
                            "coefficient": 1.5,
                            "contribution": 120.0,
                            "direction": "positive",
                            "description": "Annual rainfall normal (mm)",
                        }
                    ],
                    "model_equation": "yield = 1.5 * rain + b",
                    "methodology": "Cross-sectional ridge regression",
                    "data_quality_notes": ["Uses climate normals"],
                    "data_points": [{"rain": 900.0, "yield": 1800.0, "district": "A"}],
                    "regression_line": [{"x": 900.0, "y": 1800.0}],
                }
            )
        )
    )

    with patch("app.services.simulation_service.get_cache", return_value=cache), patch(
        "app.services.simulation_service.PredictionEngine",
        return_value=engine,
    ):
        response = await service.get_prediction_v2_response("Patna", "rice", 2020, "Bihar")

    assert response.prediction.predicted_yield == 2350.0
    assert response.prediction.factors[0].key == "rainfall"
    cache.set.assert_awaited_once()
    engine.predict.assert_called_once()


@pytest.mark.asyncio
async def test_simulation_service_rejects_invalid_prediction_inputs(mock_db):
    service = SimulationService(mock_db)
    service.repo = AsyncMock()
    cache = SimpleNamespace(get=AsyncMock(return_value=None), set=AsyncMock())

    service.repo.get_state_yield_rows = AsyncMock(
        return_value=[
            {"district_name": "A", "yield": 1800.0},
            {"district_name": "B", "yield": 1900.0},
            {"district_name": "C", "yield": 2000.0},
            {"district_name": "D", "yield": 2100.0},
        ]
    )

    with patch("app.services.simulation_service.get_cache", return_value=cache), pytest.raises(
        NotFoundError
    ):
        await service.get_prediction_v2_response("Patna", "millet", 2020, "Bihar")

    service.repo.get_state_yield_rows = AsyncMock(
        return_value=[
            {"district_name": "A", "yield": 1800.0},
            {"district_name": "B", "yield": 1900.0},
            {"district_name": "C", "yield": 2000.0},
            {"district_name": "D", "yield": 2100.0},
            {"district_name": "E", "yield": 2200.0},
        ]
    )
    service.repo.get_state_rainfall_rows = AsyncMock(return_value=[])
    service.repo.get_state_historical_yields = AsyncMock(return_value=[])
    service.repo.get_state_area_rows = AsyncMock(return_value=[])

    with patch("app.services.simulation_service.get_cache", return_value=cache), pytest.raises(
        NotFoundError
    ):
        await service.get_prediction_v2_response("Patna", "rice", 2020, "Bihar")

    with patch(
        "app.services.simulation_service.get_cache",
        return_value=cache,
    ), patch.object(
        service,
        "_resolve_yield_rows",
        AsyncMock(
            return_value=(
                "rice_yield",
                [
                    {"district_name": "A", "yield": 1800.0},
                    {"district_name": "B", "yield": 1900.0},
                    {"district_name": "C", "yield": 2000.0},
                    {"district_name": "D", "yield": 2100.0},
                    {"district_name": "E", "yield": 2200.0},
                ],
            )
        ),
    ), patch.object(
        service,
        "_build_prediction_district_data",
        return_value=[
            {"district": "A", "yield_value": 1800.0, "rainfall": 900.0, "monsoon_jjas": 700.0}
            for _ in range(5)
        ],
    ), patch(
        "app.services.simulation_service.PredictionEngine",
        return_value=SimpleNamespace(predict=Mock(return_value=None)),
    ), pytest.raises(ValidationError):
        await service.get_prediction_v2_response("Patna", "rice", 2020, "Bihar")


def test_spatial_service_requires_database_connection():
    service = SpatialService()

    with pytest.raises(RuntimeError):
        service._require_db()

    with pytest.raises(RuntimeError):
        service._require_repo()


@pytest.mark.asyncio
async def test_spatial_service_get_neighbors_and_cagr(mock_db):
    service = SpatialService(mock_db)
    service.repo = AsyncMock()
    service.repo.get_neighbors = AsyncMock(return_value=[{"neighbor_cdk": 1}])
    service.repo.get_crop_yield_series = AsyncMock(
        side_effect=[
            [{"year": 2019, "value": 100.0}],
            [
                {"year": 2018, "value": 100.0},
                {"year": 2020, "value": 121.0},
            ],
            [
                {"year": 2020, "value": 0.0},
                {"year": 2020, "value": 50.0},
            ],
        ]
    )

    neighbors = await service.get_neighbors("BR_patna_1991")
    short_series_cagr = await service.get_cagr("BR_patna_1991", "rice", 2019, 2019)
    growth_cagr = await service.get_cagr("BR_patna_1991", "rice", 2018, 2020)
    zero_cagr = await service.get_cagr("BR_patna_1991", "rice", 2020, 2020)

    assert neighbors == [{"neighbor_cdk": 1}]
    assert short_series_cagr == 0.0
    assert growth_cagr == pytest.approx(0.1)
    assert zero_cagr == 0.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("target_cagr", "neighbor_cagrs", "expected"),
    [
        (0.2, [0.1, 0.08], "Outperformer"),
        (0.12, [0.09, 0.1], "Clustered Growth"),
        (-0.2, [-0.1, -0.08], "Underperformer"),
        (-0.12, [-0.1, -0.08], "Clustered Decline"),
        (0.12, [-0.1, -0.05], "Divergent"),
    ],
)
async def test_spatial_service_builds_contagion_categories(
    mock_db,
    target_cagr,
    neighbor_cagrs,
    expected,
):
    service = SpatialService(mock_db)
    service.repo = AsyncMock()
    service.repo.district_exists = AsyncMock(return_value=True)
    service.repo.get_target_meta = AsyncMock(return_value={"district_name": "Patna"})
    service.get_neighbors = AsyncMock(
        return_value=[
            {"neighbor_cdk": 2, "neighbor_name": "Nalanda", "neighbor_state": "Bihar"},
            {"neighbor_cdk": 3, "neighbor_name": "Gaya", "neighbor_state": "Bihar"},
        ]
    )
    service.get_cagr = AsyncMock(side_effect=[target_cagr, *neighbor_cagrs])

    result = await service.get_spatial_contagion("BR_patna_1991", "rice", 2018, 2020)

    assert result["spillover_category"] == expected
    assert result["neighbors"][0]["cagr"] >= result["neighbors"][1]["cagr"]


@pytest.mark.asyncio
async def test_spatial_service_raises_not_found_for_missing_contagion_district(mock_db):
    service = SpatialService(mock_db)
    service.repo = AsyncMock()
    service.repo.district_exists = AsyncMock(return_value=False)

    with pytest.raises(NotFoundError):
        await service.get_spatial_contagion("missing", "rice", 2018, 2020)


def test_spatial_service_calculates_split_areas_and_validates_input():
    service = SpatialService()
    service.geometry_service = Mock()
    service.geometry_service.calculate_split_areas = Mock(
        return_value={
            "transferred_area_sqkm": 12.5,
            "remaining_area_sqkm": 7.5,
        }
    )

    response = service.calculate_split_areas(
        b'{"type":"FeatureCollection","features":[]}',
        b'{"type":"FeatureCollection","features":[]}',
    )

    assert response.transferred_area_sqkm == 12.5

    with pytest.raises(ValidationError):
        service.calculate_split_areas(b"not-json", b"{}")

    service.geometry_service.calculate_split_areas.side_effect = ValueError("bad geometry")

    with pytest.raises(ValidationError):
        service.calculate_split_areas(b"{}", b"{}")


@pytest.mark.asyncio
async def test_spatial_service_calculates_diff_and_returns_lineage(mock_db):
    service = SpatialService(mock_db)
    service.repo = AsyncMock()
    service.repo.get_split_events_for_district = AsyncMock(return_value=[{"id": 1}])
    service.repo.get_area_transfers_for_district = AsyncMock(return_value=[{"from": "A"}])
    harmonizer = SimpleNamespace(compute_split_diff=AsyncMock())

    with patch(
        "app.analytics.harmonizer.BoundaryHarmonizer",
        return_value=harmonizer,
    ):
        status = await service.calculate_spatial_diff(7)

    lineage = await service.get_district_lineage("BR_patna_1991")

    assert status.status == "success"
    harmonizer.compute_split_diff.assert_awaited_once_with(mock_db, 7)
    assert lineage.area_transfers[0]["from"] == "A"


@pytest.mark.asyncio
async def test_spatial_service_uploads_manual_geojson_across_formats(mock_db):
    service = SpatialService(mock_db)
    service.repo = AsyncMock()
    service.repo.get_district_name = AsyncMock(return_value="Patna")
    service.repo.upsert_manual_geojson = AsyncMock()

    response = await service.upload_manual_geojson(
        "BR_patna_1991",
        2020,
        b'{"features":[{"geometry":{"type":"Point","coordinates":[1,2]}}]}',
    )

    first_upload = service.repo.upsert_manual_geojson.await_args.kwargs
    assert response.status == "success"
    assert json.loads(first_upload["geometry_geojson"]) == {
        "type": "Point",
        "coordinates": [1, 2],
    }

    await service.upload_manual_geojson(
        "BR_patna_1991",
        2021,
        b'{"geometry":{"type":"Point","coordinates":[3,4]}}',
    )
    second_upload = service.repo.upsert_manual_geojson.await_args.kwargs
    assert json.loads(second_upload["geometry_geojson"]) == {
        "type": "Point",
        "coordinates": [3, 4],
    }

    await service.upload_manual_geojson(
        "BR_patna_1991",
        2022,
        b'{"type":"Point","coordinates":[5,6]}',
    )
    third_upload = service.repo.upsert_manual_geojson.await_args.kwargs
    assert json.loads(third_upload["geometry_geojson"]) == {
        "type": "Point",
        "coordinates": [5, 6],
    }

    with pytest.raises(ValidationError):
        await service.upload_manual_geojson("BR_patna_1991", 2023, b"not-json")
