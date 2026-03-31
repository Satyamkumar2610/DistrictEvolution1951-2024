"""
Database query compatibility helpers.

These helpers let the API run against either:
- the newer LGD-based schema (`districts.lgd_code`, `agri_metrics.district_lgd`)
- the older text-CDK schema (`districts.cdk`, `agri_metrics.cdk`)
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from typing import Any, Literal

import asyncpg

logger = logging.getLogger(__name__)

_JOIN_REPLACEMENTS = (
    ("m.district_lgd = d.lgd_code", "m.cdk = d.cdk"),
    ("am.district_lgd = d.lgd_code", "am.cdk = d.cdk"),
    ("ds.child_lgd = d.lgd_code", "ds.child_cdk = d.cdk"),
    ("ds.parent_lgd = d.lgd_code", "ds.parent_cdk = d.cdk"),
    ("pd.lgd_code = ds.parent_lgd", "pd.cdk = ds.parent_cdk"),
)

_COLUMN_REPLACEMENTS = (
    ("district_lgd::text", "cdk"),
    ("lgd_code::text", "cdk"),
    ("district_lgd", "cdk"),
    ("lgd_code", "cdk"),
)

_ARRAY_CAST_PATTERN = re.compile(
    r"((?:\w+\.)?cdk)\s*=\s*ANY\(\$(\d+)::(?:int|float)\[\]\)",
    re.IGNORECASE,
)
_SCALAR_CDK_PATTERN = re.compile(
    r"(?:\w+\.)?(?:lgd_code(?:::text)?|district_lgd(?:::text)?)\s*=\s*\$(\d+)",
    re.IGNORECASE,
)
_ARRAY_CDK_PATTERN = re.compile(
    r"(?:\w+\.)?(?:lgd_code|district_lgd)\s*=\s*ANY\(\$(\d+)::(?:int|float)\[\]\)",
    re.IGNORECASE,
)


def uses_lgd_schema(query: str) -> bool:
    """Return whether the SQL references the newer LGD-based columns."""
    return "lgd_code" in query or "district_lgd" in query


def to_legacy_query(query: str) -> str:
    """Translate a LGD-based query into its legacy text-CDK equivalent."""
    transformed = query

    for old, new in _JOIN_REPLACEMENTS:
        transformed = transformed.replace(old, new)

    for old, new in _COLUMN_REPLACEMENTS:
        transformed = transformed.replace(old, new)

    transformed = _ARRAY_CAST_PATTERN.sub(r"\1 = ANY($\2::text[])", transformed)
    return transformed


def _normalize_legacy_scalar(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return value


def adapt_legacy_args(query: str, args: tuple[Any, ...]) -> tuple[Any, ...]:
    """Normalize args for legacy CDK-based queries."""
    legacy_query = to_legacy_query(query)
    if legacy_query == query:
        return args

    scalar_indexes = {int(match.group(1)) - 1 for match in _SCALAR_CDK_PATTERN.finditer(query)}
    array_indexes = {int(match.group(1)) - 1 for match in _ARRAY_CDK_PATTERN.finditer(query)}

    normalized: list[Any] = []
    for index, value in enumerate(args):
        if index in array_indexes and isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            normalized.append([_normalize_legacy_scalar(item) for item in value])
            continue

        if index in scalar_indexes:
            normalized.append(_normalize_legacy_scalar(value))
            continue

        if isinstance(value, (str, bytes, bytearray)):
            normalized.append(value)
            continue

        if isinstance(value, Sequence):
            normalized.append(list(value))
            continue

        normalized.append(value)

    return tuple(normalized)


async def execute_with_schema_fallback(
    conn: asyncpg.Connection,
    operation: Literal["fetch", "fetchrow", "fetchval"],
    query: str,
    *args: Any,
) -> Any:
    """
    Execute a query and transparently retry with legacy CDK columns when the
    deployed database does not expose the LGD-based schema.
    """
    executor = getattr(conn, operation)

    try:
        return await executor(query, *args)
    except asyncpg.UndefinedColumnError:
        if not uses_lgd_schema(query):
            raise

        legacy_query = to_legacy_query(query)
        if legacy_query == query:
            raise

        legacy_args = adapt_legacy_args(query, args)
        logger.warning("Retrying %s with legacy district schema compatibility", operation)
        return await executor(legacy_query, *legacy_args)


async def fetch(conn: asyncpg.Connection, query: str, *args: Any) -> list[asyncpg.Record]:
    return await execute_with_schema_fallback(conn, "fetch", query, *args)


async def fetchrow(conn: asyncpg.Connection, query: str, *args: Any) -> asyncpg.Record | None:
    return await execute_with_schema_fallback(conn, "fetchrow", query, *args)


async def fetchval(conn: asyncpg.Connection, query: str, *args: Any) -> Any:
    return await execute_with_schema_fallback(conn, "fetchval", query, *args)
