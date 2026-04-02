"""
Base Repository: Abstract patterns for data access.
"""

from typing import Generic, TypeVar

import asyncpg

from app.db_compat import execute_with_schema_fallback

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """
    Base repository with common database operations.
    Subclasses implement entity-specific queries.
    """

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def fetch_one(self, query: str, *args) -> asyncpg.Record | None:
        """Execute query and return single record or None."""
        return await execute_with_schema_fallback(self.conn, "fetchrow", query, *args)

    async def fetch_all(self, query: str, *args) -> list[asyncpg.Record]:
        """Execute query and return all records."""
        return await execute_with_schema_fallback(self.conn, "fetch", query, *args)

    async def fetch_val(self, query: str, *args):
        """Execute query and return a scalar value."""
        return await execute_with_schema_fallback(self.conn, "fetchval", query, *args)

    async def execute(self, query: str, *args) -> str:
        """Execute a command (INSERT, UPDATE, DELETE)."""
        return await self.conn.execute(query, *args)
