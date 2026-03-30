"""
I-ASCAP MCP server.

This is a project-specific, client-agnostic MCP server for the current
I-ASCAP API surface. It works with Codex, Claude Code, Cursor, or any MCP
client that can launch a local stdio server.

Setup:
    pip install mcp httpx

Run directly:
    python backend/mcp_server.py

Register in Codex:
    codex mcp add i-ascap -- python /absolute/path/to/backend/mcp_server.py

The FastAPI backend must be reachable. By default this server targets:
    http://localhost:8000/api/v1

Override with a local or deployed API base URL:
    IASCAP_API_BASE_URL=http://localhost:8000/api/v1
    IASCAP_API_BASE_URL=https://i-ascap.onrender.com/api/v1
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("IASCAP_API_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")
REQUEST_TIMEOUT = float(os.environ.get("IASCAP_MCP_TIMEOUT", "30"))

mcp = FastMCP("i-ascap")


def _backend_reachability_hint() -> str:
    if "localhost" in BASE_URL or "127.0.0.1" in BASE_URL:
        return "Start the API first, for example: cd backend && uvicorn app.main:app --reload"
    return "Ensure the deployed API is reachable and that IASCAP_API_BASE_URL points to /api/v1"


async def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    url = f"{BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            response = await client.request(method, url, params=params, json=json_body)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot connect to I-ASCAP backend at {BASE_URL}. "
                f"{_backend_reachability_hint()}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            raise RuntimeError(
                f"I-ASCAP API error {exc.response.status_code} for {path}: {detail}"
            ) from exc

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return response.json()
    return response.text


def _compact_query(path: str, params: dict[str, Any] | None = None) -> str:
    if not params:
        return path
    filtered = {k: v for k, v in params.items() if v is not None}
    query = urlencode(filtered, doseq=True)
    return f"{path}?{query}" if query else path


@mcp.resource("iascap://project/overview")
def project_overview() -> str:
    return (
        "I-ASCAP is an Indian agri-spatial analytics platform built on a "
        "FastAPI backend and Next.js frontend. Core domains include district "
        "lineage, split-impact analysis, rainfall and water-stress analytics, "
        "yield trends, forecasting, and historical reconstruction."
    )


@mcp.resource("iascap://api/routes")
def api_routes() -> dict[str, Any]:
    return {
        "base_url": BASE_URL,
        "high_value_routes": [
            "/states/list",
            "/districts",
            "/districts/{cdk}",
            "/metrics/history",
            "/search",
            "/analysis/split-impact/summary",
            "/analysis/split-impact/districts",
            "/analysis/split-impact/analysis",
            "/lineage/history",
            "/lineage/tracking",
            "/analytics/diversification",
            "/analytics/yield-trend",
            "/analytics/yield-gap",
            "/climate/rainfall",
            "/climate/water-stress",
            "/spatial/contagion",
            "/forecast/{cdk}/{crop}",
            "/forecast/{cdk}/recommend",
            "/quality/district/{cdk}",
            "/reconstruct/{cdk}",
        ],
    }


@mcp.tool()
async def api_health() -> Any:
    """Check whether the local I-ASCAP backend is up."""
    return await _request("GET", "/health/live")


@mcp.tool()
async def list_states() -> Any:
    """List all states available in the current dataset."""
    return await _request("GET", "/states/list")


@mcp.tool()
async def list_districts(state: str | None = None, search: str | None = None) -> Any:
    """List districts, optionally filtered by state or district-name search."""
    params = {"state": state, "search": search}
    return await _request("GET", "/districts", params=params)


@mcp.tool()
async def get_district(cdk: str) -> Any:
    """Fetch a single district by its LGD/CDK string."""
    return await _request("GET", f"/districts/{cdk}")


@mcp.tool()
async def search_entities(q: str, type: str = "all", limit: int = 20) -> Any:
    """Search districts and states by name."""
    return await _request("GET", "/search", params={"q": q, "type": type, "limit": limit})


@mcp.tool()
async def get_state_overview(state_name: str, crop: str = "wheat", year: int | None = None) -> Any:
    """Get high-level agricultural overview metrics for a state."""
    params = {"crop": crop, "year": year}
    return await _request("GET", f"/states/{state_name}/overview", params=params)


@mcp.tool()
async def get_metric_history(
    crop: str = "wheat",
    cdk: str | None = None,
    district: str | None = None,
    state: str | None = None,
) -> Any:
    """
    Get district-level metric history.

    Provide either `cdk`, or `district` and optionally `state`.
    """
    params = {"cdk": cdk, "district": district, "state": state, "crop": crop}
    return await _request("GET", "/metrics/history", params=params)


@mcp.tool()
async def get_split_summary() -> Any:
    """Get split-impact summary statistics across states."""
    return await _request("GET", "/analysis/split-impact/summary")


@mcp.tool()
async def get_split_events_for_state(state: str) -> Any:
    """Get resolved district split events for a specific state."""
    return await _request("GET", "/analysis/split-impact/districts", params={"state": state})


@mcp.tool()
async def analyze_split_impact(
    parent_cdk: str,
    child_cdks: list[str],
    split_year: int,
    crop: str = "wheat",
    metric: str = "yield",
    mode: str = "before_after",
) -> Any:
    """Run the harmonized split-impact analysis for a parent/children event."""
    params = {
        "parent": parent_cdk,
        "children": ",".join(child_cdks),
        "splitYear": split_year,
        "crop": crop,
        "metric": metric,
        "mode": mode,
    }
    return await _request("GET", "/analysis/split-impact/analysis", params=params)


@mcp.tool()
async def get_lineage_history(state: str | None = None) -> Any:
    """Fetch split history records, optionally filtered by state."""
    return await _request("GET", "/lineage/history", params={"state": state})


@mcp.tool()
async def get_lineage_tracking(cdk: str) -> Any:
    """Inspect data coverage and lineage provenance for a district."""
    return await _request("GET", "/lineage/tracking", params={"cdk": cdk})


@mcp.tool()
async def get_reconstruction(cdk: str, crop: str = "rice", min_year: int = 1966) -> Any:
    """Run the lineage reconstructor for a root district CDK."""
    return await _request("GET", f"/reconstruct/{cdk}", params={"crop": crop, "min_year": min_year})


@mcp.tool()
async def get_crop_diversification(cdk: str, year: int = 2020) -> Any:
    """Get diversification metrics for a district-year."""
    return await _request("GET", "/analytics/diversification", params={"cdk": cdk, "year": year})


@mcp.tool()
async def get_yield_trend(
    cdk: str,
    crop: str = "rice",
    start_year: int = 1990,
    end_year: int = 2020,
) -> Any:
    """Get CAGR/volatility yield trend analysis for a district and crop."""
    params = {"cdk": cdk, "crop": crop, "start_year": start_year, "end_year": end_year}
    return await _request("GET", "/analytics/yield-trend", params=params)


@mcp.tool()
async def get_yield_gap(
    state: str,
    crop: str = "rice",
    start_year: int = 2000,
    end_year: int = 2020,
) -> Any:
    """Get state-wide yield gap rankings and convergence timeline."""
    params = {"state": state, "crop": crop, "start_year": start_year, "end_year": end_year}
    return await _request("GET", "/analytics/yield-gap", params=params)


@mcp.tool()
async def get_rainfall(state: str, district: str) -> Any:
    """Get rainfall normals for a district."""
    return await _request("GET", "/climate/rainfall", params={"state": state, "district": district})


@mcp.tool()
async def get_water_stress(state: str, year: int = 2020) -> Any:
    """Get water-stress mismatch analysis for all districts in a state."""
    return await _request("GET", "/climate/water-stress", params={"state": state, "year": year})


@mcp.tool()
async def get_spatial_contagion(
    cdk: str,
    crop: str = "wheat",
    start_year: int = 2000,
    end_year: int = 2020,
) -> Any:
    """Compare a district's CAGR with its geographic neighbors."""
    params = {"cdk": cdk, "crop": crop, "start_year": start_year, "end_year": end_year}
    return await _request("GET", "/spatial/contagion", params=params)


@mcp.tool()
async def get_district_quality(cdk: str) -> Any:
    """Get the data-quality report for a district."""
    return await _request("GET", f"/quality/district/{cdk}")


@mcp.tool()
async def get_yield_forecast(cdk: str, crop: str, horizon: int = 3) -> Any:
    """Get district crop yield forecast."""
    return await _request("GET", f"/forecast/{cdk}/{crop}", params={"horizon": horizon})


@mcp.tool()
async def get_crop_recommendations(cdk: str, top_n: int = 5) -> Any:
    """Get crop recommendations for a district."""
    return await _request("GET", f"/forecast/{cdk}/recommend", params={"top_n": top_n})


@mcp.tool()
async def get_district_profile_report(cdk: str, crop: str = "wheat", format: str = "json") -> Any:
    """Generate the district profile report exposed by the API."""
    params = {"cdk": cdk, "crop": crop, "format": format}
    return await _request("GET", "/reports/district-profile", params=params)


@mcp.tool()
async def get_request_examples() -> dict[str, str]:
    """Return a few concrete examples of useful calls for this project."""
    return {
        "search_districts": _compact_query("/search", {"q": "Patna", "type": "district", "limit": 5}),
        "state_overview": _compact_query("/states/Bihar/overview", {"crop": "wheat", "year": 2020}),
        "split_events": _compact_query("/analysis/split-impact/districts", {"state": "Bihar"}),
        "yield_trend": _compact_query(
            "/analytics/yield-trend",
            {"cdk": "101", "crop": "wheat", "start_year": 1990, "end_year": 2020},
        ),
        "forecast": _compact_query("/forecast/101/wheat", {"horizon": 3}),
    }


if __name__ == "__main__":
    mcp.run()
