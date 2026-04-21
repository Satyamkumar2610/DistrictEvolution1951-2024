"""
Fallback tests for Phase 2-3 intelligence analytics.

These tests ensure analytics still return usable outputs when optional
scientific dependencies are unavailable at runtime.
"""

from app.analytics.pca_resilience import PCAResilienceAnalyzer
from app.analytics.stochastic_frontier import StochasticFrontierAnalyzer


def _resilience_input(n: int = 6) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for i in range(n):
        rows.append(
            {
                "cdk": f"{1000 + i}",
                "name": f"District {i + 1}",
                "yield_cv": 12.0 + i * 2.1,
                "retention_ratio": 0.45 + i * 0.06,
                "cdi": 0.25 + i * 0.05,
                "soil_quality": 0.30 + i * 0.04,
                "yield_depletion_rate": -1.2 + i * 0.35,
                "irrigation_pct": 25.0 + i * 7.0,
                "recovery_speed": 4.5 - i * 0.25,
                "input_efficiency": 3.5 + i * 0.6,
            }
        )
    return rows


def _sfa_input(n: int = 12) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for i in range(n):
        rows.append(
            {
                "cdk": f"{2000 + i}",
                "name": f"SFA District {i + 1}",
                "yield": 1700.0 + i * 110.0,
            }
        )
    return rows


def test_pca_resilience_numpy_fallback_without_sklearn(monkeypatch):
    import app.analytics.pca_resilience as pca_module

    monkeypatch.setattr(pca_module, "SKLEARN_OK", False)

    analyzer = PCAResilienceAnalyzer()
    report = analyzer.analyze(_resilience_input(), region="Fallback State")

    assert report is not None
    assert report.n_districts == 6
    assert len(report.district_results) == 6
    assert report.total_variance_explained > 0
    assert any("NumPy SVD PCA fallback" in warning for warning in report.warnings)


def test_sfa_quantile_fallback_without_scipy(monkeypatch):
    import app.analytics.stochastic_frontier as sfa_module

    monkeypatch.setattr(sfa_module, "SCIPY_OK", False)

    analyzer = StochasticFrontierAnalyzer()
    report = analyzer.analyze(_sfa_input(), crop="rice", year=2015)

    assert report is not None
    assert report.model_stats.n_districts == 12
    assert len(report.district_results) == 12
    assert all(0 < d.technical_efficiency <= 1 for d in report.district_results)
    assert report.district_results[0].technical_efficiency >= report.district_results[-1].technical_efficiency
    assert any("quantile frontier fallback" in warning for warning in report.warnings)
