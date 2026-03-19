from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, Form
import asyncpg
import json

from app.api.deps import get_db
from app.services.spatial_service import SpatialService
from app.services.geometry_service import GeometryService
from app.exceptions import NotFoundError

router = APIRouter(prefix="/spatial", tags=["Spatial Data"])


@router.get("/contagion")
async def get_spatial_contagion(
    cdk: str = Query(..., description="Target district LGD code (as text)"),
    crop: str = Query("wheat", description="Crop name to analyze"),
    start_year: int = Query(2000, description="Start year of analysis window"),
    end_year: int = Query(2020, description="End year of analysis window"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Calculate agricultural growth spillovers using geographic adjacency (PostGIS).
    Compiles a target district's yield CAGR vs the average of its neighbors.
    """
    service = SpatialService(db)

    # Validation logic to ensure district exists
    check = await db.fetchval("SELECT lgd_code FROM districts WHERE lgd_code::text = $1", cdk)
    if not check:
        raise NotFoundError(detail=f"District {cdk} not found.")

    result = await service.get_spatial_contagion(cdk, crop, start_year, end_year)
    return result


@router.post("/calculate-split")
async def calculate_split(
    parent_geojson: UploadFile = File(..., description="Parent district GeoJSON"),
    child_geojson: UploadFile = File(..., description="Child district GeoJSON")
):
    """
    Calculate the accurate Transferred Area and Remaining Area in square kilometers
    using Indian Equal Area projection (EPSG:7755) and GeoPandas.
    """
    try:
        parent_content = await parent_geojson.read()
        child_content = await child_geojson.read()

        parent_dict = json.loads(parent_content.decode("utf-8"))
        child_dict = json.loads(child_content.decode("utf-8"))

        geom_service = GeometryService()
        result = geom_service.calculate_split_areas(parent_dict, child_dict)
        return result
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400,
                            detail="Invalid JSON format uploaded.")
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"Geo-processing failed: {str(e)}")

@router.post("/diff")
async def calculate_spatial_diff(split_event_id: int, db: asyncpg.Connection = Depends(get_db)):
    """Calculate and write spatial difference and transferred areas for a split event."""
    from app.analytics.harmonizer import BoundaryHarmonizer
    harmonizer = BoundaryHarmonizer()
    await harmonizer.compute_split_diff(db, split_event_id)
    return {"status": "success", "message": f"Calculated split diff for event {split_event_id}"}

@router.get("/lineage/{district_id}")
async def get_district_lineage(district_id: str, db: asyncpg.Connection = Depends(get_db)):
    """Fetch all lineage split events and area transfers for a specific district."""
    events = await db.fetch("SELECT * FROM split_events WHERE parent_cdk = $1 OR $1 = ANY(child_cdks)", district_id)
    transfers = await db.fetch("SELECT * FROM area_transfers WHERE source_cdk = $1 OR dest_cdk = $1", district_id)
    
    return {
        "district_id": district_id,
        "split_events": [dict(e) for e in events],
        "area_transfers": [
           {k: v for k, v in dict(t).items() if k != 'geometry'} 
           for t in transfers
        ]
    }

@router.post("/upload-geojson")
async def upload_manual_geojson(
    district_id: str = Form(...),
    snapshot_year: int = Form(...),
    geojson_file: UploadFile = File(...),
    db: asyncpg.Connection = Depends(get_db)
):
    """Parses GeoJSON and saves as manual_upload to district_snapshots."""
    content = await geojson_file.read()
    parsed = json.loads(content.decode("utf-8"))
    
    if "features" in parsed and len(parsed["features"]) > 0:
        geom = parsed["features"][0].get("geometry")
    elif "geometry" in parsed:
        geom = parsed["geometry"]
    else:
        geom = parsed
        
    geom_str = json.dumps(geom)
    name = await db.fetchval("SELECT district_name FROM districts WHERE lgd_code::text = $1 LIMIT 1", district_id)
    
    await db.execute("""
        INSERT INTO district_snapshots
            (district_cdk, snapshot_year, district_name, geometry_source, geometry_confidence, geometry)
        VALUES
            ($1, $2, $3, 'manual_upload', 0.8, ST_SetSRID(ST_GeomFromGeoJSON($4), 4326))
        ON CONFLICT (district_cdk, snapshot_year) DO UPDATE SET
            geometry = EXCLUDED.geometry,
            geometry_source = EXCLUDED.geometry_source,
            geometry_confidence = EXCLUDED.geometry_confidence
    """, district_id, snapshot_year, name or district_id, geom_str)
    
    return {"status": "success", "message": f"Uploaded manual GeoJSON for {district_id} ({snapshot_year})"}

