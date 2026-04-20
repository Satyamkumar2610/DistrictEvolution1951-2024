"""Services package - Business logic orchestration."""

from importlib import import_module
from typing import Any

__all__ = [
    "AdvancedAnalyticsFacade",
    "AnomalyService",
    "AnalysisService",
    "ForecastService",
    "LineageService",
    "ReportService",
    "SearchService",
    "SimulationService",
    "StateService",
]

_MODULE_MAP = {
    "AdvancedAnalyticsFacade": "app.services.advanced_analytics_service",
    "AnalysisService": "app.services.analysis_service",
    "AnomalyService": "app.services.anomaly_service",
    "ForecastService": "app.services.forecast_service",
    "LineageService": "app.services.lineage_service",
    "ReportService": "app.services.report_service",
    "SearchService": "app.services.search_service",
    "SimulationService": "app.services.simulation_service",
    "StateService": "app.services.state_service",
}


def __getattr__(name: str) -> Any:
    """Lazy-load service exports so light scripts avoid heavy app imports."""
    module_name = _MODULE_MAP.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name)
    return getattr(module, name)
