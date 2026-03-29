"""
API routes for District Split Area Transfer Detection.

Routes:
    POST /api/v1/spatial/diff              — Run split diff
    GET  /api/v1/spatial/lineage/{cdk}     — Get lineage tree
    POST /api/v1/spatial/upload-geojson    — Upload district boundary
    GET  /api/v1/spatial/enrichment/{id}   — Get enrichment data
    POST /api/v1/spatial/enrichment/trigger — Trigger enrichment
    POST /api/v1/spatial/gazette/parse     — Parse gazette text
    POST /api/v1/spatial/lineage/batch-import  — Batch import lineage CSV
    GET  /api/v1/spatial/drift/{cdk}       — Boundary drift detection
    GET  /api/v1/spatial/quality/overview   — Data quality overview
"""

import logging

import asyncpg  # type: ignore
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query  # type: ignore
from pydantic import BaseModel, Field  # type: ignore

from app.api.deps import get_db  # type: ignore
from app.core.geometry_resolver import GeometryResolver  # type: ignore
from app.schemas.split_schemas import (  # type: ignore
    GeoJsonUploadRequest,
    LineageNode,
    LineageResponse,
    SplitDiffRequest,
    SplitDiffResponse,
    TransferDetail,
    UploadResponse,
)
from app.services.drift_detector import DriftDetector  # type: ignore
from app.services.enrichment_engine import enrich_split_event  # type: ignore
from app.services.gazette_parser import parse_gazette_text  # type: ignore
from app.services.lineage_loader import load_changes_csv, load_lineage_csv  # type: ignore
from app.services.split_engine import SplitEngine  # type: ignore

logger = logging.getLogger("app.api.splits")

router = APIRouter(prefix="/spatial", tags=["Spatial - Split Analyzer"])


# ─────────────────────────────────────────────────────────────────────────────
# POST /diff — Run split diff computation
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/diff",
    response_model=SplitDiffResponse,
    summary="Compute district split diff",
    description=(
        "Computes the geometric diff between a parent district and its child "
        "districts. Returns classified transfer polygons (inherited, "
        "transferred_in, gap, overlap) as a GeoJSON FeatureCollection."
    ),
)
async def compute_split_diff(
    request: SplitDiffRequest,
    background_tasks: BackgroundTasks,
    db: asyncpg.Connection = Depends(get_db),
):
    engine = SplitEngine(db)

    result = await engine.compute_split_diff(
        parent_cdk=request.parent_cdk,
        child_cdks=request.child_cdks,
        split_year=request.split_year,
    )

    # Trigger async enrichment in the background
    event_id = None
    if result.transfers:
        # Find the event_id from the most recent split_events row
        event_id = await db.fetchval("""
            SELECT id FROM split_events
            WHERE parent_cdk = $1 AND split_year = $2
            ORDER BY created_at DESC LIMIT 1
        """, request.parent_cdk, request.split_year)
        if event_id:
            background_tasks.add_task(_run_enrichment, event_id)

    return SplitDiffResponse(
        event_id=event_id,
        parent_cdk=result.parent_cdk,
        child_cdks=result.child_cdks,
        split_year=result.split_year,
        parent_area_sqkm=round(result.parent_area_sqkm, 4),
        total_child_area_sqkm=round(result.total_child_area_sqkm, 4),
        area_conservation_error=round(result.area_conservation_error, 6),
        composite_confidence=round(result.composite_confidence, 4),
        geometry_status=result.geometry_status,
        transfers=[
            TransferDetail(
                from_district=t.from_district,
                to_district=t.to_district,
                transfer_type=t.transfer_type,
                area_sqkm=round(t.area_sqkm, 4),
                confidence_score=round(t.confidence_score, 4),
            )
            for t in result.transfers
        ],
        warnings=result.warnings,
        geojson=result.geojson_fc or {"type": "FeatureCollection", "features": []},
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /upload-geojson — Upload a district boundary
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/upload-geojson",
    response_model=UploadResponse,
    summary="Upload district boundary GeoJSON",
    description=(
        "Upload a GeoJSON boundary for a district. The geometry is stored in "
        "district_snapshots and becomes available for split diff computations."
    ),
)
async def upload_geojson(
    request: GeoJsonUploadRequest,
    db: asyncpg.Connection = Depends(get_db),
):
    resolver = GeometryResolver(db)

    # Extract the actual geometry from the GeoJSON
    geojson = request.geojson
    geometry_dict = None

    if geojson.get("type") == "FeatureCollection":
        features = geojson.get("features", [])
        if not features:
            raise HTTPException(400, "FeatureCollection has no features")
        geometry_dict = features[0].get("geometry")
    elif geojson.get("type") == "Feature":
        geometry_dict = geojson.get("geometry")
    elif geojson.get("type") in ("Polygon", "MultiPolygon"):
        geometry_dict = geojson
    else:
        raise HTTPException(
            400,
            "Invalid GeoJSON. Must be a Polygon, MultiPolygon, Feature, "
            "or FeatureCollection."
        )

    if not geometry_dict:
        raise HTTPException(400, "No valid geometry found in GeoJSON")

    import json as _json
    geom_str = _json.dumps(geometry_dict)

    # Insert or update the geometry in district_snapshots
    await db.execute("""
        INSERT INTO district_snapshots
            (district_cdk, snapshot_year, district_name, geometry_source, geometry_confidence, geometry)
        VALUES
            ($1, $2, $1, 'manual_upload', 0.8, ST_SetSRID(ST_GeomFromGeoJSON($3), 4326))
        ON CONFLICT (district_cdk, snapshot_year) DO UPDATE SET
            geometry = EXCLUDED.geometry,
            geometry_source = EXCLUDED.geometry_source,
            geometry_confidence = EXCLUDED.geometry_confidence
    """, request.district_cdk, request.snapshot_year, geom_str)

    # Resolve to get the full metadata
    result = await resolver.resolve(request.district_cdk, request.snapshot_year)

    return UploadResponse(
        district_cdk=result.district_cdk,
        snapshot_year=result.snapshot_year,
        geometry_source=result.geometry_source,
        geometry_confidence=result.geometry_confidence,
        area_sqkm=round(result.area_sqkm, 4) if result.area_sqkm else None,
        message=(
            f"Geometry for '{result.district_cdk}' at year "
            f"{result.snapshot_year} stored successfully "
            f"(source={result.geometry_source}, "
            f"confidence={result.geometry_confidence})"
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /lineage/{district_cdk} — Get lineage tree (recursive)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/lineage/{district_cdk}",
    response_model=LineageResponse,
    summary="Get district split lineage tree",
    description=(
        "Returns the full parent→child lineage tree for a district, "
        "traversing split_events recursively up to a specified depth."
    ),
)
async def get_lineage(
    district_cdk: str,
    depth: int = Query(5, ge=1, le=10, description="Max tree depth"),
    db: asyncpg.Connection = Depends(get_db),
):
    # First check if the district exists
    district = await db.fetchrow("""
        SELECT cdk, district_name, start_year, end_year
        FROM districts WHERE cdk = $1
    """, district_cdk)

    if not district:
        raise HTTPException(404, f"District '{district_cdk}' not found")

    # Get geometry info if available
    _snapshot = await db.fetchrow("""
        SELECT area_sqkm, geometry_source::text, geometry_confidence
        FROM district_snapshots
        WHERE district_cdk = $1 AND geometry IS NOT NULL
        ORDER BY snapshot_year DESC LIMIT 1
    """, district_cdk)

    # Build tree recursively
    counters: dict[str, int] = {"nodes": 0, "events": 0}

    async def build_tree(cdk: str, current_depth: int) -> LineageNode:

        # Get district info
        dist = await db.fetchrow("""
            SELECT cdk, district_name, start_year, end_year
            FROM districts WHERE cdk = $1
        """, cdk)

        if not dist:
            counters["nodes"] += 1
            return LineageNode(
                district_cdk=cdk,
                district_name=cdk,  # fallback
            )

        # Get geometry snapshot
        snap = await db.fetchrow("""
            SELECT area_sqkm, geometry_source::text, geometry_confidence
            FROM district_snapshots
            WHERE district_cdk = $1 AND geometry IS NOT NULL
            ORDER BY snapshot_year DESC LIMIT 1
        """, cdk)

        node = LineageNode(
            district_cdk=dist["cdk"],
            district_name=dist["district_name"],
            year_created=dist["start_year"],
            year_dissolved=dist["end_year"],
            area_sqkm=snap["area_sqkm"] if snap else None,
            geometry_source=snap["geometry_source"] if snap else "unknown",
            geometry_confidence=snap["geometry_confidence"] if snap else 0.0,
        )
        counters["nodes"] += 1

        # Get children from split_events
        if current_depth < depth:
            events = await db.fetch("""
                SELECT id, child_cdks, split_year
                FROM split_events
                WHERE parent_cdk = $1
                ORDER BY split_year ASC
            """, cdk)

            # Also check lineage CSV data (district_splits table)
            legacy_children = await db.fetch("""
                SELECT child_district, split_year
                FROM district_splits
                WHERE parent_district = $1
                  OR parent_lgd::text = $1
                ORDER BY split_year ASC
            """, dist["district_name"])

            children_cdks = set()

            for evt in events:
                counters["events"] += 1
                for child_cdk in evt["child_cdks"]:
                    child_cdk_str = str(child_cdk)
                    if child_cdk_str not in children_cdks:
                        children_cdks.add(child_cdk_str)
                        child_node = await build_tree(
                            child_cdk_str, current_depth + 1
                        )
                        node.children.append(child_node)

            # Fallback to legacy lineage data
            if not events and legacy_children:
                for lc in legacy_children:
                    # Try to find CDK for the child district name
                    child_dist = await db.fetchrow("""
                        SELECT cdk FROM districts
                        WHERE district_name ILIKE $1
                        LIMIT 1
                    """, lc["child_district"])
                    if child_dist and str(child_dist["cdk"]) not in children_cdks:
                        children_cdks.add(str(child_dist["cdk"]))
                        counters["events"] += 1
                        child_node = await build_tree(
                            str(child_dist["cdk"]), current_depth + 1
                        )
                        node.children.append(child_node)

        return node

    root = await build_tree(district_cdk, 0)

    return LineageResponse(
        root=root,
        total_nodes=counters["nodes"],
        total_split_events=counters["events"],
    )

# ─────────────────────────────────────────────────────────────────────────────
# GET /enrichment/{event_id} — Get enrichment data for a split event
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/enrichment/{event_id}",
    summary="Get enrichment data for a split event",
    description="Returns all enrichment metrics for the transfers in a split event.",
)
async def get_enrichment(
    event_id: int,
    db: asyncpg.Connection = Depends(get_db),
):
    # Verify event exists
    event = await db.fetchrow("""
        SELECT id, parent_cdk, child_cdks, split_year,
               parent_area_sqkm, total_child_area_sqkm
        FROM split_events WHERE id = $1
    """, event_id)

    if not event:
        raise HTTPException(404, f"Split event {event_id} not found")

    # Get all enrichment data grouped by transfer
    rows = await db.fetch("""
        SELECT
            e.transfer_id,
            t.from_district,
            t.to_district,
            t.transfer_type::text,
            t.area_sqkm AS transfer_area,
            e.dataset_name,
            e.metric_name,
            e.value,
            e.unit,
            e.reference_year,
            e.source_url
        FROM split_enrichment e
        JOIN area_transfers t ON e.transfer_id = t.id
        WHERE t.event_id = $1
        ORDER BY e.transfer_id, e.dataset_name, e.metric_name
    """, event_id)

    # Group by transfer
    transfers_enrichment = {}
    for row in rows:
        tid = row["transfer_id"]
        if tid not in transfers_enrichment:
            transfers_enrichment[tid] = {
                "transfer_id": tid,
                "from_district": row["from_district"],
                "to_district": row["to_district"],
                "transfer_type": row["transfer_type"],
                "transfer_area_sqkm": float(row["transfer_area"]),
                "metrics": [],
            }
        transfers_enrichment[tid]["metrics"].append({
            "dataset": row["dataset_name"],
            "metric": row["metric_name"],
            "value": float(row["value"]) if row["value"] else None,
            "unit": row["unit"],
            "reference_year": row["reference_year"],
            "source_url": row["source_url"],
        })

    return {
        "success": True,
        "event_id": event_id,
        "parent_cdk": event["parent_cdk"],
        "split_year": event["split_year"],
        "total_enrichment_rows": len(rows),
        "transfers": list(transfers_enrichment.values()),
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /enrichment/trigger — Manually trigger enrichment for an event
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/enrichment/trigger",
    summary="Trigger enrichment for a split event",
    description="Manually trigger enrichment workers for a previously computed split.",
)
async def trigger_enrichment(
    event_id: int = Query(..., description="Split event ID to enrich"),
    background_tasks: BackgroundTasks | None = None,
    db: asyncpg.Connection = Depends(get_db),
):
    event = await db.fetchrow(
        "SELECT id FROM split_events WHERE id = $1", event_id
    )
    if not event:
        raise HTTPException(404, f"Split event {event_id} not found")

    if background_tasks:
        background_tasks.add_task(_run_enrichment, event_id)
        return {
            "success": True,
            "message": f"Enrichment triggered for event {event_id} (running in background)",
        }
    else:
        # Run synchronously if no background tasks available
        from app.database import get_connection  # type: ignore
        async with get_connection() as conn:
            result = await enrich_split_event(conn, event_id)
        return {"success": True, "result": result}


# ─────────────────────────────────────────────────────────────────────────────
# Background task helper
# ─────────────────────────────────────────────────────────────────────────────

async def _run_enrichment(event_id: int) -> None:
    """Background task that runs enrichment in a fresh DB connection."""
    from app.database import get_connection  # type: ignore
    try:
        async with get_connection() as conn:
            result = await enrich_split_event(conn, event_id)
            logger.info(f"Background enrichment complete for event {event_id}: {result}")
    except Exception as e:
        logger.error(f"Background enrichment failed for event {event_id}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────


class GazetteParseRequest(BaseModel):
    """Request body for POST /gazette/parse"""
    text: str = Field(..., description="Gazette notification text to parse")


@router.post(
    "/gazette/parse",
    summary="Parse gazette/notification text for split events",
    description=(
        "Extracts district split events from gazette text using regex NLP. "
        "Returns structured parent→children records with confidence scores."
    ),
)
async def parse_gazette(
    request: GazetteParseRequest,
):
    events = parse_gazette_text(request.text)
    return {
        "success": True,
        "parsed_events": [
            {
                "parent_district": e.parent_district,
                "child_districts": e.child_districts,
                "year": e.year,
                "state": e.state,
                "confidence": e.confidence,
                "raw_text": e.raw_text,
            }
            for e in events
        ],
        "total": len(events),
    }


@router.post(
    "/lineage/batch-import",
    summary="Batch import lineage from CSV files",
    description=(
        "Imports district lineage data from CSV files into split_events. "
        "Supports district_lineage_cleaned.csv (CDK-based) and "
        "district_changes.csv (name-based with CDK resolution)."
    ),
)
async def batch_import_lineage(
    source: str = Query(
        "lineage",
        description="Source CSV: 'lineage' or 'changes'"
    ),
    dry_run: bool = Query(
        True,
        description="Preview without writing to DB"
    ),
    db: asyncpg.Connection = Depends(get_db),
):
    if source == "lineage":
        result = await load_lineage_csv(db, dry_run=dry_run)
    elif source == "changes":
        result = await load_changes_csv(db, dry_run=dry_run)
    else:
        raise HTTPException(400, "source must be 'lineage' or 'changes'")

    return {"success": True, **result}


@router.get(
    "/drift/{district_cdk}",
    summary="Detect boundary drift for a district",
    description=(
        "Computes boundary drift metrics (Hausdorff distance, Jaccard index, "
        "centroid shift, area change) between geometry snapshots of a district."
    ),
)
async def get_drift(
    district_cdk: str,
    year_a: int | None = Query(None, description="Earlier snapshot year"),
    year_b: int | None = Query(None, description="Later snapshot year"),
    timeline: bool = Query(False, description="Return full timeline"),
    db: asyncpg.Connection = Depends(get_db),
):
    detector = DriftDetector(db)

    if timeline:
        results = await detector.get_drift_timeline(district_cdk)
        return {
            "success": True,
            "district_cdk": district_cdk,
            "timeline": [
                {
                    "year_a": r.year_a,
                    "year_b": r.year_b,
                    "hausdorff_km": r.hausdorff_km,
                    "area_a_sqkm": r.area_a_sqkm,
                    "area_b_sqkm": r.area_b_sqkm,
                    "area_change_pct": r.area_change_pct,
                    "jaccard_index": r.jaccard_index,
                    "centroid_shift_km": r.centroid_shift_km,
                    "shape_similarity": r.shape_similarity,
                }
                for r in results
            ],
            "total_comparisons": len(results),
        }

    result = await detector.detect_drift(district_cdk, year_a, year_b)
    if not result:
        raise HTTPException(
            404,
            f"Insufficient snapshots for drift detection on '{district_cdk}'"
        )

    return {
        "success": True,
        "district_cdk": result.district_cdk,
        "year_a": result.year_a,
        "year_b": result.year_b,
        "hausdorff_km": result.hausdorff_km,
        "area_a_sqkm": result.area_a_sqkm,
        "area_b_sqkm": result.area_b_sqkm,
        "area_change_pct": result.area_change_pct,
        "overlap_area_sqkm": result.overlap_area_sqkm,
        "jaccard_index": result.jaccard_index,
        "centroid_shift_km": result.centroid_shift_km,
        "shape_similarity": result.shape_similarity,
        "source_a": result.source_a,
        "source_b": result.source_b,
    }


@router.get(
    "/quality/overview",
    summary="Data quality overview for the split analyzer",
    description=(
        "Returns aggregate quality metrics: geometry coverage, split event counts, "
        "enrichment coverage, and confidence distribution."
    ),
)
async def quality_overview(
    db: asyncpg.Connection = Depends(get_db),
):
    # Total districts
    total_districts = await db.fetchval(
        "SELECT COUNT(*) FROM districts"
    ) or 0

    # Districts with geometry
    districts_with_geom = await db.fetchval(
        "SELECT COUNT(DISTINCT district_cdk) FROM district_snapshots WHERE geometry IS NOT NULL"
    ) or 0

    # Total split events
    total_events = await db.fetchval(
        "SELECT COUNT(*) FROM split_events"
    ) or 0

    # Events by geometry status
    status_counts = await db.fetch("""
        SELECT geometry_status::text, COUNT(*) AS count
        FROM split_events
        GROUP BY geometry_status
    """)

    # Confidence distribution
    confidence_dist = await db.fetch("""
        SELECT
            CASE
                WHEN composite_confidence >= 0.85 THEN 'high'
                WHEN composite_confidence >= 0.6 THEN 'medium'
                WHEN composite_confidence > 0 THEN 'low'
                ELSE 'none'
            END AS bucket,
            COUNT(*) AS count
        FROM split_events
        GROUP BY bucket
    """)

    # Total enrichment rows
    total_enrichment = await db.fetchval(
        "SELECT COUNT(*) FROM split_enrichment"
    ) or 0

    # Events with enrichment
    enriched_events = await db.fetchval("""
        SELECT COUNT(DISTINCT t.event_id)
        FROM split_enrichment e
        JOIN area_transfers t ON e.transfer_id = t.id
    """) or 0

    # Total area transfers
    total_transfers = await db.fetchval(
        "SELECT COUNT(*) FROM area_transfers"
    ) or 0

    # Transfer type breakdown
    transfer_types = await db.fetch("""
        SELECT transfer_type::text, COUNT(*) AS count,
               ROUND(SUM(area_sqkm)::numeric, 2) AS total_area_sqkm
        FROM area_transfers
        GROUP BY transfer_type
    """)

    # Geometry source breakdown
    source_counts = await db.fetch("""
        SELECT geometry_source::text, COUNT(*) AS count
        FROM district_snapshots
        WHERE geometry IS NOT NULL
        GROUP BY geometry_source
    """)

    return {
        "success": True,
        "districts": {
            "total": total_districts,
            "with_geometry": districts_with_geom,
            "geometry_coverage_pct": round(
                float(districts_with_geom) / float(total_districts) * 100, 1
            ) if total_districts > 0 else 0,
        },
        "split_events": {
            "total": total_events,
            "by_status": {r["geometry_status"]: r["count"] for r in status_counts},
            "confidence_distribution": {
                r["bucket"]: r["count"] for r in confidence_dist
            },
        },
        "transfers": {
            "total": total_transfers,
            "by_type": [
                {
                    "type": r["transfer_type"],
                    "count": r["count"],
                    "total_area_sqkm": float(r["total_area_sqkm"]) if r["total_area_sqkm"] else 0,
                }
                for r in transfer_types
            ],
        },
        "enrichment": {
            "total_rows": total_enrichment,
            "events_enriched": enriched_events,
        },
        "geometry_sources": {
            r["geometry_source"]: r["count"] for r in source_counts
        },
    }
