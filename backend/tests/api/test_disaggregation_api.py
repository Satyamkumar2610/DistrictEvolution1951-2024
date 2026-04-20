from unittest.mock import AsyncMock, patch

import pytest

from app.api.deps import get_db
from app.schemas.disaggregation import (
    ChildSeriesEstimate,
    DisaggregationEventDetail,
    DisaggregationEventListResponse,
    DisaggregationEventSummary,
    DisaggregationSeriesResponse,
    EstimatePoint,
    ParentSeries,
)


def _override_db(mock_db):
    async def _override():
        yield mock_db

    return _override


@pytest.mark.asyncio
async def test_disaggregation_routes_return_expected_shapes(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.list_events.return_value = DisaggregationEventListResponse(
        total=1,
        items=[
            DisaggregationEventSummary(
                event_id="PARENT:2000",
                parent_cdk="PARENT",
                parent_name="Parent",
                child_cdks=["CHILD_A"],
                child_names=["Child A"],
                state="State X",
                split_year=2000,
                effective_date=None,
                event_type="SPLIT",
                readiness_tier="Tier B",
                source_quality="official_compiled",
                geometry_status="unknown",
                weight_status="proxy_ready",
                warnings=[],
            )
        ],
    )
    service.get_event_detail.return_value = DisaggregationEventDetail(
        event_id="PARENT:2000",
        parent_cdk="PARENT",
        parent_name="Parent",
        child_cdks=["CHILD_A"],
        child_names=["Child A"],
        state="State X",
        split_year=2000,
        effective_date=None,
        event_type="SPLIT",
        readiness_tier="Tier B",
        source_quality="official_compiled",
        geometry_status="unknown",
        weight_status="proxy_ready",
        warnings=[],
        split_event_id=None,
        source_urls=[],
        source_text_path=None,
        aliases=["Parent", "Child A"],
        notes="packet",
        sources=[],
        weights=[],
        methodology_note="note",
    )
    service.get_event_series.return_value = DisaggregationSeriesResponse(
        event_id="PARENT:2000",
        crop="rice",
        metric="yield",
        readiness_tier="Tier B",
        readiness_status="ready",
        parent_series=ParentSeries(
            cdk="PARENT",
            name="Parent",
            metric="yield",
            points=[
                EstimatePoint(
                    year=1999,
                    value=3000.0,
                    is_estimated=False,
                    method="Raw",
                    confidence=1.0,
                    lower_bound=2850.0,
                    upper_bound=3150.0,
                    provenance_ref="panel:PARENT:1999",
                )
            ],
        ),
        child_series=[
            ChildSeriesEstimate(
                child_cdk="CHILD_A",
                child_name="Child A",
                metric="yield",
                weight_method="post_split_crop_area_proxy",
                weight_confidence=0.7,
                points=[],
            )
        ],
        warnings=[],
        methodology_note="note",
    )

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.disaggregation.DisaggregationService", return_value=service):
            list_response = await client.get("/api/v1/disaggregation/events?state=State%20X")
            detail_response = await client.get("/api/v1/disaggregation/events/PARENT:2000")
            series_response = await client.get(
                "/api/v1/disaggregation/events/PARENT:2000/series?crop=rice&metric=yield&start_year=1999&end_year=1999"
            )

        assert list_response.status_code == 200
        assert list_response.json()["items"][0]["event_id"] == "PARENT:2000"
        assert detail_response.status_code == 200
        assert detail_response.json()["aliases"] == ["Parent", "Child A"]
        assert series_response.status_code == 200
        assert series_response.json()["readiness_status"] == "ready"
        service.list_events.assert_awaited_once()
        service.get_event_detail.assert_awaited_once_with("PARENT:2000")
        service.get_event_series.assert_awaited_once_with("PARENT:2000", "rice", "yield", 1999, 1999)
    finally:
        del client._transport.app.dependency_overrides[get_db]
