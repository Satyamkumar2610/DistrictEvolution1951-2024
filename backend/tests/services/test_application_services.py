from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call, patch

import pytest
from fastapi import Response

from app.exceptions import NotFoundError, ValidationError
from app.schemas.lineage import DistrictHistoryItem, TrackingCoverage, TrackingDistrict
from app.services.advanced_analytics_service import AdvancedAnalyticsFacade
from app.services.anomaly_service import AnomalyService
from app.services.climate_service import ClimateService
from app.services.forecast_service import ForecastService
from app.services.lineage_service import LineageService
from app.services.report_service import ReportService
from app.services.search_service import SearchService
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
