"""
Lineage Reconstructor API — reconstructs historical district timelines
across split events using epoch-based aggregation.
v3: DAG-based LineageGraph with ancestor/descendant queries.
"""
import logging

import asyncpg  # type: ignore
from fastapi import APIRouter, Depends, HTTPException, Query  # type: ignore

from app.api.deps import get_db  # type: ignore
from app.core.lineage_graph import LineageGraph  # type: ignore
from app.services.reconstructor_service import ReconstructorService  # type: ignore

logger = logging.getLogger("app.api.v1.lineage_reconstructor")

router = APIRouter()


# ------------------------------------------------------------------
# Helper: build LineageGraph from DB
# ------------------------------------------------------------------

async def _build_graph(db: asyncpg.Connection) -> LineageGraph:
    """Fetch split_events and construct a LineageGraph."""
    rows = await db.fetch(
        "SELECT parent_cdk, child_cdks, split_year FROM split_events"
    )
    return LineageGraph.from_split_events([dict(r) for r in rows])


# ------------------------------------------------------------------
# Search
# ------------------------------------------------------------------

@router.get("/search")
async def search_districts(
    q: str = Query(..., min_length=2),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Fuzzy search for districts in the split_events graph.
    """
    try:
        results = await db.fetch("""
            WITH all_cdks AS (
                SELECT DISTINCT parent_cdk AS cdk FROM split_events
                UNION
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


# ------------------------------------------------------------------
# Tree / Lineage
# ------------------------------------------------------------------

@router.get("/{cdk}/lineage")
async def get_lineage(cdk: str, db: asyncpg.Connection = Depends(get_db)):
    """Returns the tree structure for the frontend."""
    try:
        svc = ReconstructorService(db)
        return await svc.get_lineage_tree(cdk)
    except Exception as e:
        logger.error(f"Lineage tree failed for {cdk}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Lineage tree failed: {str(e)}"
        )


# ------------------------------------------------------------------
# Ancestors / Descendants (new DAG-based endpoints)
# ------------------------------------------------------------------

@router.get("/{cdk}/ancestors")
async def get_ancestors(
    cdk: str,
    year: int = Query(None, description="Stop at this year"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    All historical districts that contributed area to this modern district.
    Traverses the inverse DAG from child → parents.
    """
    try:
        graph = await _build_graph(db)
        ancestors = graph.get_canonical_ancestors(cdk, target_year=year)
        return {
            "cdk": cdk,
            "target_year": year,
            "ancestors": ancestors,
            "count": len(ancestors),
        }
    except Exception as e:
        logger.error(f"Ancestors query failed for {cdk}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{cdk}/descendants")
async def get_descendants(
    cdk: str,
    from_year: int = Query(None, description="Only events after this year"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    All modern districts that inherited area from this historical district.
    Traverses the forward DAG from parent → children.
    """
    try:
        graph = await _build_graph(db)
        descendants = graph.get_canonical_descendants(cdk, from_year=from_year)
        leaf_descendants = graph.get_leaf_descendants(cdk)
        return {
            "cdk": cdk,
            "from_year": from_year,
            "all_descendants": descendants,
            "leaf_descendants": leaf_descendants,
            "count": len(descendants),
        }
    except Exception as e:
        logger.error(f"Descendants query failed for {cdk}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Graph summary
# ------------------------------------------------------------------

@router.get("/graph/summary")
async def graph_summary(db: asyncpg.Connection = Depends(get_db)):
    """Returns DAG statistics: node/event counts, root/leaf counts, event types."""
    try:
        graph = await _build_graph(db)
        return graph.summary()
    except Exception as e:
        logger.error(f"Graph summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Full reconstruction
# ------------------------------------------------------------------

@router.get("/{cdk}")
async def reconstruct_lineage(
    cdk: str,
    crop: str = "rice",
    min_year: int = 1966,
    db: asyncpg.Connection = Depends(get_db),
):
    """Returns full epoch array with yield aggregation for a root CDK."""
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
