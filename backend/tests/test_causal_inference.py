import pytest

from app.analytics.causal_inference import CausalInferenceEngine, CausalImpactResult


def test_causal_inference_engine_insufficient_data():
    engine = CausalInferenceEngine()
    
    # Less than 10 points
    result = engine.estimate_shock_impact(
        crop="wheat",
        shock_type="drought",
        yields=[1000, 1100, 950],
        treatments=[0, 1, 0],
        covariates=[[10], [12], [11]]
    )
    
    assert result is None


def test_causal_inference_engine_basic_effect():
    engine = CausalInferenceEngine()
    
    # Synthetic data: 
    # Base yield = 2000
    # Shock (T=1) causes -500 yield
    # Trend covariate adds +50 per year
    
    yields = []
    treatments = []
    covariates = []
    
    for i in range(20):
        t = 1 if i % 4 == 0 else 0  # 1 in 4 years is a shock
        trend = i * 50
        noise = (i % 3) * 10 - 10
        y = 2000 + trend - (500 * t) + noise
        
        yields.append(y)
        treatments.append(t)
        covariates.append([i])  # Area/Trend proxy
        
    result = engine.estimate_shock_impact(
        crop="rice",
        shock_type="flood",
        yields=yields,
        treatments=treatments,
        covariates=covariates
    )
    
    assert result is not None
    assert isinstance(result, CausalImpactResult)
    assert result.shock_type == "flood"
    assert result.target_crop == "rice"
    
    # The estimated treatment effect should be close to -500
    assert -550 <= result.average_treatment_effect <= -450
    assert result.p_value < 0.05
    assert result.is_significant is True
    assert result.treated_count == 5
    assert result.control_count == 15
