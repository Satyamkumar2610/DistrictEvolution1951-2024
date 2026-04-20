"""API v1 Router - aggregates all endpoint routers."""

from fastapi import APIRouter

from app.api.v1 import (
    advanced_analytics,
    analysis,
    anomalies,
    climate,
    disaggregation,
    districts,
    forecast,
    health,
    intelligence,
    lineage,
    lineage_reconstructor,
    metrics,
    quality,
    reports,
    search,
    simulation,
    spatial,
    splits,
    states,
)

api_router = APIRouter()

# --- System ---
api_router.include_router(health.router)
api_router.include_router(quality.router)

# --- Core Data ---
api_router.include_router(districts.router, prefix="/districts", tags=["Districts"])
api_router.include_router(lineage.router, prefix="/lineage", tags=["Lineage"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])

# --- Analysis & Analytics ---
api_router.include_router(analysis.router, prefix="/analysis", tags=["Analysis"])
# self-prefixed /analytics
api_router.include_router(advanced_analytics.router)
api_router.include_router(disaggregation.router)
api_router.include_router(climate.router, prefix="/climate", tags=["Climate"])
api_router.include_router(simulation.router, prefix="/simulation", tags=["Simulation"])
api_router.include_router(spatial.router)  # self-prefixed /spatial
api_router.include_router(splits.router)  # self-prefixed /spatial (split analyzer)
api_router.include_router(forecast.router)  # self-prefixed /forecast
api_router.include_router(anomalies.router)  # self-prefixed /anomalies
api_router.include_router(intelligence.router)  # self-prefixed /intelligence (Phase 2-3)

# --- Discovery & Reports ---
api_router.include_router(states.router)  # self-prefixed /states
api_router.include_router(search.router)  # self-prefixed /search
api_router.include_router(reports.router)  # self-prefixed /reports
api_router.include_router(lineage_reconstructor.router, prefix="/reconstruct", tags=["Lineage"])
