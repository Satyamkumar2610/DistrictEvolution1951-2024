import logging

from fastapi import APIRouter, Depends, Query, HTTPException  # type: ignore

import asyncpg  # type: ignore
from app.api.deps import get_db  # type: ignore
from app.services.reconstructor_service import ReconstructorService  # type: ignore

logger = logging.getLogger("app.api.v1.lineage_reconstructor")

router = APIRouter()

@router.get("/search")
async def search_districts(q: str = Query(..., min_length=2), db: asyncpg.Connection = Depends(get_db)):
    """Fuzzy search across all CDKs"""
    try:
        results = await db.fetch("""
            SELECT cdk, district_name, state_name, start_year
            FROM districts
            WHERE district_name ILIKE $1 OR cdk ILIKE $1
            LIMIT 10
        """, f"%{q}%")
        
        out = []
        for r in results:
            is_root = await db.fetchval("SELECT 1 FROM split_events WHERE parent_cdk = $1 LIMIT 1", r["cdk"])
            out.append({
                "cdk": r["cdk"],
                "display_name": r["district_name"],
                "state": r["state_name"],
                "era": r["start_year"],
                "is_root": bool(is_root)
            })
        return out
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/{cdk}/lineage")
async def get_lineage(cdk: str, db: asyncpg.Connection = Depends(get_db)):
    """Returns only the tree structure, cheaply."""
    try:
        svc = ReconstructorService(db)
        return await svc.get_lineage_tree(cdk)
    except Exception as e:
        logger.error(f"Lineage tree failed for {cdk}: {e}")
        raise HTTPException(status_code=500, detail=f"Lineage tree failed: {str(e)}")

@router.get("/{cdk}")
async def reconstruct_lineage(
    cdk: str, 
    crop: str = "rice", 
    min_year: int = 1966,
    db: asyncpg.Connection = Depends(get_db)
):
    """Returns full epoch array for a root CDK."""
    try:
        svc = ReconstructorService(db)
        result = await svc.reconstruct(cdk, crop, min_year)
        if not result["epochs"]:
            raise HTTPException(status_code=404, detail="Lineage epochs could not be generated.")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reconstruction failed for {cdk}: {e}")
        raise HTTPException(status_code=500, detail=f"Reconstruction failed: {str(e)}")
