"""
Lineage Reconstructor API — reconstructs historical district timelines
across split events using epoch-based aggregation.
v2: CDK→LGD bridge architecture for cross-schema yield lookup.
"""
import logging

from fastapi import APIRouter, Depends, Query, HTTPException  # type: ignore
import asyncpg  # type: ignore

from app.api.deps import get_db  # type: ignore
from app.services.reconstructor_service import ReconstructorService  # type: ignore

logger = logging.getLogger("app.api.v1.lineage_reconstructor")

router = APIRouter()


@router.get("/search")
async def search_districts(
    q: str = Query(..., min_length=2),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Fuzzy search for districts that are roots in the split_events graph.
    Searches parent_cdk values and flattened child_cdks from split_events,
    matching against district names from the districts table via a
    CDK-to-name mapping built from district_snapshots.
    """
    try:
        # Search across split_events parent CDKs and district_snapshots names
        results = await db.fetch("""
            WITH all_cdks AS (
                -- All unique parent CDKs
                SELECT DISTINCT parent_cdk AS cdk FROM split_events
                UNION
                -- All unique child CDKs (unnest arrays)
                SELECT DISTINCT unnest(child_cdks) AS cdk FROM split_events
            ),
            cdk_names AS (
                SELECT
                    ac.cdk,
                    COALESCE(ds.district_name, ac.cdk) AS display_name,
                    ds.snapshot_year
                FROM all_cdks ac
                LEFT JOIN district_snapshots ds ON ds.district_cdk = ac.cdk
            )
            SELECT DISTINCT ON (cn.cdk)
                cn.cdk,
                cn.display_name,
                cn.snapshot_year AS era,
                EXISTS(
                    SELECT 1 FROM split_events se WHERE se.parent_cdk = cn.cdk
                ) AS is_root
            FROM cdk_names cn
            WHERE cn.display_name ILIKE $1 OR cn.cdk ILIKE $1
            ORDER BY cn.cdk, cn.snapshot_year
            LIMIT 15
        """, f"%{q}%")

        out = []
        for r in results:
            # Extract state prefix from CDK (e.g., 'DL' from 'DL_delhi_1991')
            cdk_str = r["cdk"]
            parts = cdk_str.split("_")
            state_prefix = parts[0] if parts else ""

            out.append({
                "cdk": cdk_str,
                "display_name": r["display_name"],
                "state": state_prefix,
                "era": r["era"],
                "is_root": r["is_root"],
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
        raise HTTPException(
            status_code=500, detail=f"Lineage tree failed: {str(e)}"
        )


@router.get("/{cdk}")
async def reconstruct_lineage(
    cdk: str,
    crop: str = "rice",
    min_year: int = 1966,
    db: asyncpg.Connection = Depends(get_db),
):
    """Returns full epoch array for a root CDK."""
    try:
        svc = ReconstructorService(db)
        result = await svc.reconstruct(cdk, crop, min_year)
        if not result["epochs"]:
            raise HTTPException(
                status_code=404,
                detail="No split events found for this CDK. "
                       "It may not be a root district.",
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reconstruction failed for {cdk}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Reconstruction failed: {str(e)}"
        )
