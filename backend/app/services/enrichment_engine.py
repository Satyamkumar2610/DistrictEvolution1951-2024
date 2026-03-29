"""
Enrichment Engine — background workers that populate split_enrichment
after a diff is computed.

Three enrichment sources (no new infra required):
  1. Overpass API (OSM) — settlements, roads, schools, hospitals
  2. Internal I-ASCAP DB  — crop yield, area metrics for transferred regions
  3. Area-proportional estimation — population, land use from district totals

All enrichment results are stored in the `split_enrichment` table.
"""

import logging
from typing import Any

import asyncpg
import httpx

logger = logging.getLogger("app.services.enrichment_engine")

# ─── Overpass API Client ──────────────────────────────────────────────────

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Overpass queries for common feature types
OVERPASS_QUERIES = {
    "settlements": """
        [out:json][timeout:30];
        (
          node["place"~"village|town|city|hamlet"](poly:"{poly}");
        );
        out count;
    """,
    "schools": """
        [out:json][timeout:30];
        (
          nwr["amenity"="school"](poly:"{poly}");
        );
        out count;
    """,
    "hospitals": """
        [out:json][timeout:30];
        (
          nwr["amenity"~"hospital|clinic|doctors"](poly:"{poly}");
        );
        out count;
    """,
    "roads_km": """
        [out:json][timeout:60];
        (
          way["highway"~"primary|secondary|tertiary|trunk"](poly:"{poly}");
        );
        out geom;
    """,
}


def geojson_to_overpass_poly(geojson: dict) -> str:
    """
    Convert a GeoJSON geometry to Overpass poly filter string.
    Overpass expects: "lat1 lon1 lat2 lon2 ..."
    """
    geom_type = geojson.get("type", "")
    coords = geojson.get("coordinates", [])

    if geom_type == "Polygon":
        ring = coords[0]  # outer ring
    elif geom_type == "MultiPolygon":
        ring = coords[0][0]  # first polygon's outer ring
    else:
        return ""

    # Overpass: lat lon pairs space-separated
    parts = []
    for lon, lat in ring:
        parts.append(f"{lat} {lon}")
    return " ".join(parts)


async def query_overpass(poly_str: str, query_template: str) -> dict | None:
    """Execute an Overpass API query with the given polygon."""
    if not poly_str:
        return None

    query = query_template.replace("{poly}", poly_str)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(OVERPASS_URL, data={"data": query})
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPStatusError, httpx.TimeoutException, Exception) as e:
        logger.warning(f"Overpass query failed: {e}")
        return None


# ─── Enrichment Workers ──────────────────────────────────────────────────

async def enrich_transfer_osm(
    db: asyncpg.Connection,
    transfer_id: int,
    geometry_geojson: dict,
) -> int:
    """
    Enrich a single area_transfer with OSM data via Overpass.
    Returns the count of enrichment rows inserted.
    """
    poly_str = geojson_to_overpass_poly(geometry_geojson)
    if not poly_str:
        logger.warning(f"Cannot create Overpass poly for transfer {transfer_id}")
        return 0

    inserted = 0

    # 1. Settlements count
    result = await query_overpass(poly_str, OVERPASS_QUERIES["settlements"])
    if result and "elements" in result:
        count = (
            result["elements"][0].get("tags", {}).get("total", 0)
            if result["elements"] else len(result["elements"])
        )
        await _upsert_enrichment(
            db, transfer_id, "osm_overpass", "settlement_count",
            float(count), "count", None,
            "https://overpass-api.de"
        )
        inserted += 1

    # 2. Schools count
    result = await query_overpass(poly_str, OVERPASS_QUERIES["schools"])
    if result and "elements" in result:
        count = (
            result["elements"][0].get("tags", {}).get("total", 0)
            if result["elements"] else len(result["elements"])
        )
        await _upsert_enrichment(
            db, transfer_id, "osm_overpass", "school_count",
            float(count), "count", None,
            "https://overpass-api.de"
        )
        inserted += 1

    # 3. Hospitals count
    result = await query_overpass(poly_str, OVERPASS_QUERIES["hospitals"])
    if result and "elements" in result:
        count = (
            result["elements"][0].get("tags", {}).get("total", 0)
            if result["elements"] else len(result["elements"])
        )
        await _upsert_enrichment(
            db, transfer_id, "osm_overpass", "hospital_clinic_count",
            float(count), "count", None,
            "https://overpass-api.de"
        )
        inserted += 1

    return inserted


async def enrich_transfer_area_proportion(
    db: asyncpg.Connection,
    transfer_id: int,
    transfer_area_sqkm: float,
    parent_cdk: str,
    split_year: int,
) -> int:
    """
    Estimate population and agricultural metrics for the transferred area
    by proportional scaling from the parent district's known values.

    ratio = transfer_area / parent_area
    estimated_metric = parent_metric × ratio
    """
    inserted = 0

    # Get parent area
    parent_area = await db.fetchval("""
        SELECT area_sqkm FROM district_snapshots
        WHERE district_cdk = $1 AND geometry IS NOT NULL
        ORDER BY ABS(snapshot_year - $2) LIMIT 1
    """, parent_cdk, split_year)

    if not parent_area or parent_area <= 0:
        return 0

    ratio = transfer_area_sqkm / parent_area

    # Try to get crop metrics from our own database
    metrics = await db.fetch("""
        SELECT crop, metric, value
        FROM district_metrics
        WHERE cdk = $1
          AND year = (SELECT MAX(year) FROM district_metrics WHERE cdk = $1 AND year <= $2)
        LIMIT 20
    """, parent_cdk, split_year)

    for row in metrics:
        metric_name = f"{row['crop']}_{row['metric']}"
        estimated = float(row["value"]) * ratio
        await _upsert_enrichment(
            db, transfer_id, "i_ascap_proportional", metric_name,
            round(estimated, 4),
            "estimated_proportional",
            split_year,
            f"Proportional estimate: {ratio:.4f} of parent {parent_cdk}"
        )
        inserted += 1

    # Estimate total agricultural area (if available)
    total_ag_area = await db.fetchval("""
        SELECT SUM(value) FROM district_metrics
        WHERE cdk = $1 AND metric = 'area'
          AND year = (SELECT MAX(year) FROM district_metrics WHERE cdk = $1 AND year <= $2)
    """, parent_cdk, split_year)

    if total_ag_area and total_ag_area > 0:
        estimated_ag = float(total_ag_area) * ratio
        await _upsert_enrichment(
            db, transfer_id, "i_ascap_proportional", "total_agricultural_area",
            round(estimated_ag, 2), "hectares",
            split_year,
            f"Proportional estimate: {ratio:.4f} of parent {parent_cdk}"
        )
        inserted += 1

    return inserted


async def enrich_transfer_land_stats(
    db: asyncpg.Connection,
    transfer_id: int,
    transfer_area_sqkm: float,
    geometry_geojson: dict,
) -> int:
    """
    Compute basic land statistics from the geometry itself.
    These are geometry-derived metrics that don't need external data.
    """
    inserted = 0

    # Store the transfer area itself
    await _upsert_enrichment(
        db, transfer_id, "geometry_derived", "area_sqkm",
        transfer_area_sqkm, "sq_km", None, None
    )
    inserted += 1

    # Compute bounding box area ratio (compactness proxy)
    geom_type = geometry_geojson.get("type", "")
    coords = geometry_geojson.get("coordinates", [])

    if geom_type in ("Polygon", "MultiPolygon"):
        try:
            all_coords = coords[0] if geom_type == "Polygon" else coords[0][0]

            lons = [c[0] for c in all_coords]
            lats = [c[1] for c in all_coords]
            bbox_width = max(lons) - min(lons)
            bbox_height = max(lats) - min(lats)

            # Rough bbox area in sq degrees → approx sq km at 20°N
            km_per_deg_lon = 111.32 * 0.9397  # cos(20°)
            km_per_deg_lat = 110.57
            bbox_area_sqkm = (bbox_width * km_per_deg_lon) * (bbox_height * km_per_deg_lat)

            if bbox_area_sqkm > 0:
                compactness = transfer_area_sqkm / bbox_area_sqkm
                await _upsert_enrichment(
                    db, transfer_id, "geometry_derived", "compactness_ratio",
                    round(compactness, 4), "ratio", None, None
                )
                inserted += 1

            # Centroid
            avg_lon = sum(lons) / len(lons)
            avg_lat = sum(lats) / len(lats)
            await _upsert_enrichment(
                db, transfer_id, "geometry_derived", "centroid_lon",
                round(avg_lon, 6), "degrees", None, None
            )
            await _upsert_enrichment(
                db, transfer_id, "geometry_derived", "centroid_lat",
                round(avg_lat, 6), "degrees", None, None
            )
            inserted += 2

        except (IndexError, TypeError, ValueError) as e:
            logger.warning(f"Land stats computation failed for transfer {transfer_id}: {e}")

    return inserted


# ─── Master Enrichment Orchestrator ───────────────────────────────────────

async def enrich_split_event(
    db: asyncpg.Connection,
    event_id: int,
) -> dict:
    """
    Run all enrichment workers for all transfers in a split event.
    Called as a FastAPI BackgroundTask.

    Returns a summary dict of what was enriched.
    """
    logger.info(f"Starting enrichment for split event {event_id}")

    # Get event details
    event = await db.fetchrow("""
        SELECT parent_cdk, child_cdks, split_year
        FROM split_events WHERE id = $1
    """, event_id)

    if not event:
        logger.error(f"Split event {event_id} not found")
        return {"error": f"Event {event_id} not found"}

    parent_cdk = event["parent_cdk"]
    split_year = event["split_year"]

    # Get all transfers for this event
    transfers = await db.fetch("""
        SELECT id, from_district, to_district, area_sqkm,
               transfer_type::text,
               ST_AsGeoJSON(geometry)::json AS geojson
        FROM area_transfers
        WHERE event_id = $1
    """, event_id)

    summary: dict[str, Any] = {
        "event_id": event_id,
        "total_transfers": len(transfers),
        "enrichments": {},
    }

    for transfer in transfers:
        tid = transfer["id"]
        geojson = transfer["geojson"]
        area = float(transfer["area_sqkm"])

        enriched_counts: dict[str, int] = {}

        # 1. Geometry-derived stats (always available)
        count = await enrich_transfer_land_stats(db, tid, area, geojson)
        enriched_counts["geometry_derived"] = count

        # 2. Area-proportional estimates from I-ASCAP DB
        count = await enrich_transfer_area_proportion(
            db, tid, area, parent_cdk, split_year
        )
        enriched_counts["i_ascap_proportional"] = count

        # 3. OSM/Overpass enrichment (may timeout on large polygons)
        try:
            count = await enrich_transfer_osm(db, tid, geojson)
            enriched_counts["osm_overpass"] = count
        except Exception as e:
            logger.warning(f"OSM enrichment failed for transfer {tid}: {e}")
            enriched_counts["osm_overpass"] = 0

        summary["enrichments"][tid] = enriched_counts

    enrichments: dict[int, dict[str, int]] = summary["enrichments"]
    total_rows = sum(
        sum(v.values()) for v in enrichments.values()
    )
    summary["total_enrichment_rows"] = total_rows

    logger.info(
        f"Enrichment complete for event {event_id}: "
        f"{total_rows} rows across {len(transfers)} transfers"
    )

    return summary


# ─── Helpers ──────────────────────────────────────────────────────────────

async def _upsert_enrichment(
    db: asyncpg.Connection,
    transfer_id: int,
    dataset_name: str,
    metric_name: str,
    value: float,
    unit: str | None,
    reference_year: int | None,
    source_url: str | None,
) -> None:
    """Insert or update a single enrichment row."""
    await db.execute("""
        INSERT INTO split_enrichment
            (transfer_id, dataset_name, metric_name, value, unit,
             reference_year, source_url)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (transfer_id, dataset_name, metric_name) DO UPDATE SET
            value = EXCLUDED.value,
            unit = EXCLUDED.unit,
            reference_year = EXCLUDED.reference_year,
            source_url = EXCLUDED.source_url,
            created_at = NOW()
    """, transfer_id, dataset_name, metric_name, value, unit,
        reference_year, source_url)
