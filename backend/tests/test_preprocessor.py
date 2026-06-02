import pytest
import pandas as pd
from unittest.mock import AsyncMock
from app.ml.preprocessor import HarmonizationPreprocessor
from app.schemas.lineage import DistrictHistoryItem

@pytest.mark.asyncio
async def test_harmonization_preprocessor():
    mock_repo = AsyncMock()
    mock_repo.get_district_history.return_value = [
        DistrictHistoryItem(
            state_name="State",
            split_year=2002,
            parent_district="Parent",
            child_district="Child",
            parent_cdk="P1",
            child_cdk="C1",
            source="Test"
        )
    ]
    
    preprocessor = HarmonizationPreprocessor(lineage_repo=mock_repo)
    
    data = {
        'cdk': ['P1', 'P1', 'P1', 'P1', 'C1', 'C1'],
        'year': [2000, 2001, 2002, 2003, 2002, 2003],
        'yield_value': [100, 110, 105, 108, 105, 108],
        'crop_area': [1000, 1100, 700, 710, 300, 310]  # P1 split into 70% P1 and 30% C1 in 2002
    }
    df = pd.DataFrame(data)
    
    result = await preprocessor.harmonize_panel(df)
    
    # C1 should now have synthetic records for 2000 and 2001
    c1_records = result[result['cdk'] == 'C1']
    assert len(c1_records) == 4  # 2000, 2001, 2002, 2003
    
    c1_2000 = c1_records[c1_records['year'] == 2000].iloc[0]
    assert c1_2000['yield_value'] == 100
    # Ratio is approx 300 / (700+300) = 0.3. So area should be 1000 * 0.3 = 300
    assert abs(c1_2000['crop_area'] - 300) < 10
