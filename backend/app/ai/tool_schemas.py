"""
Claude tool schemas for the I-ASCAP AI analyst.

These schemas are Claude's BEHAVIORAL INSTRUCTIONS, not just documentation.
The descriptions tell Claude exactly how to handle harmonized data,
confidence thresholds, and data coverage limits.
"""

TOOL_SCHEMAS = [
    {
        "name": "query_metric",
        "description": (
            "Retrieve a time series of an agricultural metric for one district. "
            "IMPORTANT: When any returned row has is_harmonized=true, you MUST tell the user "
            "that value is an area-weighted estimate from the parent district (named in "
            "parent_district_name), not a direct measurement. "
            "When confidence < 0.7, describe it as a low-confidence estimate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "unit_id": {
                    "type": "string",
                    "description": "District UUID from admin_units",
                },
                "metric": {
                    "type": "string",
                    "description": ("Metric name, e.g. 'wheat_yield_kg_ha', 'rice_area_ha', 'wheat_production_tonnes'"),
                },
                "year_start": {"type": "integer"},
                "year_end": {"type": "integer"},
            },
            "required": ["unit_id", "metric", "year_start", "year_end"],
        },
    },
    {
        "name": "get_lineage",
        "description": (
            "Get the full administrative ancestry and descendants of a district. "
            "Use this when the user asks about boundary changes, district splits, "
            "or wants to understand why historical data is estimated. "
            "Returns transition events with dates, area weights, and confidence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "unit_id": {
                    "type": "string",
                    "description": "District UUID",
                },
            },
            "required": ["unit_id"],
        },
    },
    {
        "name": "compare_metrics",
        "description": (
            "Compare a metric across multiple districts for specified years. "
            "Apply the same harmonization disclosure rules as query_metric: "
            "flag harmonized values and note low confidence. "
            "Useful for cross-district comparison tables and trend analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "unit_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of district UUIDs to compare",
                },
                "metric": {
                    "type": "string",
                    "description": "Metric name to compare",
                },
                "years": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of years to include",
                },
            },
            "required": ["unit_ids", "metric", "years"],
        },
    },
]
