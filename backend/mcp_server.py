"""
I-ASCAP Custom MCP Server
Drop this file in your /backend folder.

Install deps: pip install mcp httpx
Register:     claude mcp add i-ascap -- python backend/mcp_server.py

This exposes your FastAPI + PostGIS data as tools Claude can call
directly from Claude Code while you develop.
"""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Change this if your backend runs on a different port ──────────────────────
BASE_URL = "http://localhost:8000"
# ─────────────────────────────────────────────────────────────────────────────

server = Server("i-ascap")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_all_districts",
            description=(
                "Fetch the full list of districts available in the I-ASCAP database. "
                "Use this first when you don't know which districts are available."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_crop_data",
            description=(
                "Get crop yield / production / area data for a specific district "
                "across a year range. Returns time-series data."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "district": {
                        "type": "string",
                        "description": "District name (e.g. 'Adilabad')",
                    },
                    "start_year": {
                        "type": "integer",
                        "description": "Start year (1966–2024)",
                    },
                    "end_year": {
                        "type": "integer",
                        "description": "End year (1966–2024)",
                    },
                    "crop": {
                        "type": "string",
                        "description": "Optional: specific crop name (e.g. 'wheat', 'rice')",
                    },
                    "metric": {
                        "type": "string",
                        "enum": ["yield", "production", "area"],
                        "description": "Which metric to return (default: yield)",
                    },
                },
                "required": ["district", "start_year", "end_year"],
            },
        ),
        Tool(
            name="get_district_lineage",
            description=(
                "Get the boundary split/merge lineage of a district. "
                "For example: Adilabad was split into Nirmal, Mancherial etc. "
                "Use this to understand how historical data maps to modern boundaries."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "district": {
                        "type": "string",
                        "description": "Modern district name to trace ancestry of",
                    }
                },
                "required": ["district"],
            },
        ),
        Tool(
            name="compare_districts",
            description=(
                "Compare agricultural performance between 2 or more districts "
                "for a given metric and year or year range. Returns side-by-side data."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "districts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of district names to compare",
                    },
                    "metric": {
                        "type": "string",
                        "enum": ["yield", "production", "area"],
                        "description": "Metric to compare",
                    },
                    "start_year": {"type": "integer"},
                    "end_year": {"type": "integer"},
                    "crop": {"type": "string", "description": "Optional crop filter"},
                },
                "required": ["districts", "metric", "start_year", "end_year"],
            },
        ),
        Tool(
            name="get_climate_data",
            description=(
                "Get climate data (rainfall, temperature) for a district and year. "
                "Useful to correlate climate events with yield changes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "district": {"type": "string"},
                    "start_year": {"type": "integer"},
                    "end_year": {"type": "integer"},
                },
                "required": ["district", "start_year", "end_year"],
            },
        ),
        Tool(
            name="run_harmonization",
            description=(
                "Trigger the DistrictHarmonizer for a specific district pair "
                "to apportion historical data to modern boundaries. "
                "Use when you need to reconcile pre-split and post-split data."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "source_district": {
                        "type": "string",
                        "description": "Original (pre-split) district name",
                    },
                    "target_districts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Modern district names that were carved out",
                    },
                    "year": {
                        "type": "integer",
                        "description": "Year of the boundary change",
                    },
                },
                "required": ["source_district", "target_districts", "year"],
            },
        ),
        Tool(
            name="get_state_summary",
            description=(
                "Get an aggregated summary of agricultural data for an entire state "
                "across all its districts for a given year range."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "state": {"type": "string", "description": "State name"},
                    "start_year": {"type": "integer"},
                    "end_year": {"type": "integer"},
                    "metric": {"type": "string", "enum": ["yield", "production", "area"]},
                },
                "required": ["state", "start_year", "end_year"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "get_all_districts":
                r = await client.get(f"{BASE_URL}/api/districts")
                r.raise_for_status()
                return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]

            elif name == "get_crop_data":
                r = await client.get(f"{BASE_URL}/api/crop-data", params=arguments)
                r.raise_for_status()
                return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]

            elif name == "get_district_lineage":
                district = arguments["district"]
                r = await client.get(f"{BASE_URL}/api/lineage/{district}")
                r.raise_for_status()
                return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]

            elif name == "compare_districts":
                r = await client.post(f"{BASE_URL}/api/compare", json=arguments)
                r.raise_for_status()
                return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]

            elif name == "get_climate_data":
                r = await client.get(f"{BASE_URL}/api/climate", params=arguments)
                r.raise_for_status()
                return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]

            elif name == "run_harmonization":
                r = await client.post(f"{BASE_URL}/api/harmonize", json=arguments)
                r.raise_for_status()
                return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]

            elif name == "get_state_summary":
                r = await client.get(f"{BASE_URL}/api/state-summary", params=arguments)
                r.raise_for_status()
                return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except httpx.HTTPStatusError as e:
            return [TextContent(type="text", text=f"API Error {e.response.status_code}: {e.response.text}")]
        except httpx.ConnectError:
            return [TextContent(
                type="text",
                text=(
                    f"Cannot connect to backend at {BASE_URL}. "
                    "Make sure your FastAPI server is running: "
                    "cd backend && uvicorn app.main:app --reload"
                ),
            )]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]


if __name__ == "__main__":
    asyncio.run(stdio_server(server))
