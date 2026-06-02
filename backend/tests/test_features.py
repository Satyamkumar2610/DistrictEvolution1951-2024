import pandas as pd
import numpy as np
from app.ml.features import FeatureAggregator

def test_feature_aggregator_enrich_panel():
    data = {
        'cdk': ['D1', 'D1', 'D1', 'D2', 'D2'],
        'year': [2000, 2001, 2002, 2000, 2001],
        'yield_value': [100, 110, 120, 200, 210],
        'rainfall': [500, 600, 400, 1000, 1100],
    }
    df = pd.DataFrame(data)
    result = FeatureAggregator.enrich_panel_data(df)
    
    # Check if lags are created
    assert 'yield_lag_1' in result.columns
    assert 'yield_lag_2' in result.columns
    assert 'yield_ma_3' in result.columns
    
    # Check D1 lag 1 for 2001 is 100
    d1_2001 = result[(result['cdk'] == 'D1') & (result['year'] == 2001)].iloc[0]
    assert d1_2001['yield_lag_1'] == 100.0

    # Check anomalies
    assert 'rainfall_anomaly' in result.columns
    assert not result['rainfall_anomaly'].isna().any()

def test_compute_ndvi_anomalies():
    records = [
        {'year': 2000, 'mean_ndvi': 0.5},
        {'year': 2001, 'mean_ndvi': 0.6},
        {'year': 2002, 'mean_ndvi': 0.4},
    ]
    anomalies = FeatureAggregator.compute_ndvi_anomalies(records)
    assert anomalies[2000] == 0.0  # mean is 0.5
    assert anomalies[2001] > 0
    assert anomalies[2002] < 0
