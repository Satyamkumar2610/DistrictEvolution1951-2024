from fastapi import APIRouter, Depends, Query, HTTPException  # type: ignore

import asyncpg  # type: ignore
from app.db.database import get_db  # type: ignore
from app.services.reconstructor_service import ReconstructorService  # type: ignore

router = APIRouter()

@router.get("/search")
async def search_districts(q: str = Query(..., min_length=2), db: asyncpg.Connection = Depends(get_db)):
    """Fuzzy search across all CDKs"""
    results = await db.fetch("""
        SELECT cdk, district_name as display_name, state, census_year as era
        FROM datasets.districts
        WHERE district_name ILIKE $1 OR cdk ILIKE $1
        LIMIT 10
    """, f"%{q}%")
    
    out = []
    for r in results:
        is_root = await db.fetchval("SELECT 1 FROM datasets.split_events WHERE parent_cdk = $1 LIMIT 1", r["cdk"])
        out.append({
            "cdk": r["cdk"],
            "display_name": r["display_name"],
            "state": r["state"],
            "era": r["era"],
            "is_root": bool(is_root)
        })
    return out

@router.get("/{cdk}/lineage")
async def get_lineage(cdk: str, db: asyncpg.Connection = Depends(get_db)):
    """Returns only the tree structure, cheaply."""
    svc = ReconstructorService(db)
    return await svc.get_lineage_tree(cdk)

@router.get("/{cdk}")
async def reconstruct_lineage(
    cdk: str, 
    crop: str = "rice", 
    min_year: int = 1966,
    db: asyncpg.Connection = Depends(get_db)
):
    """Returns full epoch array for a root CDK."""
    svc = ReconstructorService(db)
    result = await svc.reconstruct(cdk, crop, min_year)
    if not result["epochs"]:
        raise HTTPException(status_code=404, detail="Lineage epochs could not be generated.")
    return result
