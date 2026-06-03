import pytest
from app.analytics.split_impact_insights import SplitImpactInsightsAnalyzer

def test_calculate_zoning_sensitivity():
    analyzer = SplitImpactInsightsAnalyzer()
    
    # Case 1: Identical reconstructions (divergence 0)
    area_vals = [100.0, 110.0, 120.0]
    equal_vals = [100.0, 110.0, 120.0]
    res = analyzer.calculate_zoning_sensitivity(area_vals, equal_vals)
    assert res.divergence_score == 0.0
    assert not res.is_sensitive
    assert "Robust" in res.interpretation
    
    # Case 2: Small divergence (< 10%)
    area_vals = [100.0, 100.0]
    equal_vals = [105.0, 105.0]
    res = analyzer.calculate_zoning_sensitivity(area_vals, equal_vals)
    assert res.divergence_score == 5.0
    assert not res.is_sensitive
    assert "Moderate" in res.interpretation
    
    # Case 3: High divergence (> 10%)
    area_vals = [100.0, 100.0]
    equal_vals = [120.0, 120.0]
    res = analyzer.calculate_zoning_sensitivity(area_vals, equal_vals)
    assert res.divergence_score == 20.0
    assert res.is_sensitive
    assert "High MAUP zoning risk" in res.interpretation

def test_calculate_scale_effect():
    analyzer = SplitImpactInsightsAnalyzer()
    
    # Case 1: Stable variance
    res = analyzer.calculate_scale_effect(100.0, 110.0)
    assert res.variance_difference == 10.0
    assert not res.is_smoothing
    
    # Case 2: High scale effect (smoothing)
    res = analyzer.calculate_scale_effect(100.0, 150.0)
    assert res.variance_difference == 50.0
    assert res.is_smoothing
    assert "Parent district suppressed local variance" in res.interpretation
    
    # Case 3: Inverse scale effect
    res = analyzer.calculate_scale_effect(100.0, 50.0)
    assert res.variance_difference == -50.0
    assert not res.is_smoothing
    assert "Inverse scale effect" in res.interpretation
