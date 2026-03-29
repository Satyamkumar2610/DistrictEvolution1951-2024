"""
Search API: Full-text search across districts and states.
"""
import asyncpg
from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.schemas.search import SearchResponse

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=2, description="Search query"),
    type: str = Query("all", description="Filter: all, district, state"),
    limit: int = Query(20, ge=1, le=50, description="Max results"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Search districts and states by name.

    Returns matching districts with their LGD code, name, state, and type.
    """
    search_pattern = f"%{q}%"
    results = []

    if type in ("all", "district"):
        districts = await db.fetch("""
            SELECT
                lgd_code::text as cdk,
                district_name as name,
                state_name as state,
                start_year,
                end_year,
                'district' as result_type,
                CASE WHEN district_name ILIKE $2 THEN 0 ELSE 1 END as sort_order
            FROM districts
            WHERE district_name ILIKE $1 OR lgd_code::text ILIKE $1
            ORDER BY sort_order, district_name
            LIMIT $3
        """, search_pattern, f"{q}%", limit)
        results.extend(
            [{k: v for k, v in dict(r).items() if k != 'sort_order'} for r in districts])

    if type in ("all", "state"):
        states = await db.fetch("""
            SELECT
                state_name as name,
                state_name as state,
                COUNT(*) as district_count,
                'state' as result_type
            FROM districts
            WHERE state_name ILIKE $1
            GROUP BY state_name
            ORDER BY
                CASE WHEN state_name ILIKE $2 THEN 0 ELSE 1 END,
                state_name
            LIMIT $3
        """, search_pattern, f"{q}%", limit)
        results.extend([dict(r) for r in states])

    return {
        "query": q,
        "total": len(results),
        "results": results[:limit],
    }
