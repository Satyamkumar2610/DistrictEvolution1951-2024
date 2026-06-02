import pandas as pd
import numpy as np
import pytest
import pytest
from app.ml.xgboost_forecaster import PanelForecaster, XGB_AVAILABLE

@pytest.mark.skipif(not XGB_AVAILABLE, reason="XGBoost is not installed or missing libomp")
def test_panel_forecaster():
    forecaster = PanelForecaster()
    
    # Create mock dataset
    np.random.seed(42)
    years = list(range(2000, 2020))
    data = []
    for y in years:
        data.append({
            'cdk': 'D1', 'year': y,
            'yield_value': 100 + y%10 + np.random.randn()*5,
            'yield_lag_1': 100 + (y-1)%10,
            'yield_lag_2': 100 + (y-2)%10,
            'yield_ma_3': 100,
            'rainfall': 500 + np.random.randn()*50,
            'temperature': 25, 'soil_moisture': 0.5,
            'rainfall_anomaly': 0.1, 'temp_anomaly': -0.1, 'soil_moisture_anomaly': 0.0,
            'crop_area': 1000
        })
    df = pd.DataFrame(data)
    
    forecaster.fit(df)
    assert forecaster._is_fitted
    assert len(forecaster.cv_scores) > 0
    
    # Predict
    preds = forecaster.predict(df.tail(2))
    assert len(preds) == 2
