"""
Search API: Full-text search across districts and states.
"""

from typing import Literal

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.schemas.search import SearchResponse
from app.services import SearchService

router = APIRouter(prefix="/search", tags=["Search"])

SearchType = Literal["all", "district", "state"]


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=2, description="Search query"),
    type: SearchType = Query("all", description="Filter: all, district, state"),
    limit: int = Query(20, ge=1, le=50, description="Max results"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Search districts and states by name.

    Returns matching districts with their LGD code, name, state, and type.
    """
    service = SearchService(db)
    return await service.search_response(q, type, limit)
