"""
Search application service for API-facing entity search.
"""

from typing import Literal

import asyncpg

from app.repositories.search_repo import SearchRepository
from app.schemas.search import SearchResponse

SearchType = Literal["all", "district", "state"]


class SearchService:
    """Service layer for cross-entity search APIs."""

    def __init__(self, conn: asyncpg.Connection):
        self.repo = SearchRepository(conn)

    async def search_response(
        self,
        query: str,
        search_type: SearchType,
        limit: int,
    ) -> SearchResponse:
        """Search districts and/or states and return a typed response."""
        results: list[dict[str, object]] = []

        if search_type in ("all", "district"):
            results.extend(await self.repo.search_districts(query, limit))

        if search_type in ("all", "state"):
            results.extend(await self.repo.search_states(query, limit))

        return SearchResponse.model_validate(
            {
                "query": query,
                "total": len(results),
                "results": results[:limit],
            }
        )
