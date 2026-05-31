from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.api.deps import get_db
from app.main import app
from app.ml.backcast_data_pipeline import BackcastTrainingData


def _override_db(mock_db):
    async def _override():
        yield mock_db

    return _override


@pytest.fixture
def mock_training_data():
    # Provide 6 years of overlap to trigger the ML (GradientBoosting) path
    return BackcastTrainingData(
        child_yields={
            1994: 460.0,
            1995: 520.0,
            1996: 500.0,
            1997: 560.0,
            1998: 540.0,
            1999: 600.0,
            2000: 620.0,
            2001: 650.0,
        },
        parent_yields={
            1990: 1000.0,
            1991: 1100.0,
            1992: 1050.0,
            1993: 1200.0,
            1994: 1150.0,
            1995: 1300.0,
            1996: 1250.0,
            1997: 1400.0,
            1998: 1350.0,
            1999: 1500.0,
        },
        sibling_yields={},
        parent_areas={},
        climate={},
        area_ratio=0.4,
    )


@pytest.mark.asyncio
async def test_backcast_pipeline_integration(client: AsyncClient, mock_training_data):
    """
    Test the full backcast pipeline: API -> AdvancedAnalyticsFacade -> YieldBackcaster.
    We mock fetch_training_data to avoid DB dependency, but run the actual ML engine.
    """
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = _override_db(mock_db)

    # Mock the LLM service to avoid real API calls
    with patch("app.services.advanced_analytics_service.LLMService") as MockLLM:
        mock_llm_instance = MockLLM.return_value
        mock_llm_instance.generate_backcast_narrative = AsyncMock(return_value="AI says the model is good.")
        
        with patch("app.ml.yield_backcaster.BackcastDataPipeline.fetch_training_data", return_value=mock_training_data):
            response = await client.get(
                "/api/v1/analytics/backcast?parent_cdk=PARENT_1&child_cdks=CHILD_1&split_year=2000&crop=rice&start_year=1990"
            )

    assert response.status_code == 200
    data = response.json()
    
    # Assert top-level schema
    assert data["parent_cdk"] == "PARENT_1"
    assert data["method"] == "ml_gradient_boosting"
    assert data["ai_narrative"] == "AI says the model is good."
    
    # Assert child results
    assert "CHILD_1" in data["children"]
    child_res = data["children"]["CHILD_1"]
    assert "parent_yield" in child_res["features_used"]
    assert len(child_res["backcasted_yields"]) > 0
    
    # Assert conservation check
    assert "is_valid" in data["conservation_check"]
    
    del app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_backcast_validation_endpoint(client: AsyncClient, mock_training_data):
    """
    Test the LOO validation endpoint. Runs the ML engine multiple times (LOO) and computes MAPE.
    """
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = _override_db(mock_db)

    with patch("app.ml.yield_backcaster.BackcastDataPipeline.fetch_training_data", return_value=mock_training_data):
        response = await client.get(
            "/api/v1/analytics/backcast/validate?parent_cdk=PARENT_1&child_cdk=CHILD_1&split_year=2000&crop=rice"
        )

    assert response.status_code == 200
    data = response.json()
    
    assert data["method"] == "ml_gradient_boosting"
    assert "mape" in data
    assert "rmse" in data
    assert "trustworthiness_grade" in data
    assert len(data["steps"]) == 6  # We provided 6 overlapping years (1994-1999)
    
    # Verify step contents
    first_step = data["steps"][0]
    assert "actual_yield" in first_step
    assert "predicted_yield" in first_step
    assert "error_pct" in first_step

    del app.dependency_overrides[get_db]
