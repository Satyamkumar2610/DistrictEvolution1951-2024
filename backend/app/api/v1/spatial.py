import asyncpg
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.api.deps import get_db
from app.schemas.spatial import (
    DistrictLineageResponse,
    GenericStatusResponse,
    SpatialContagionResponse,
    SplitAreaCalculationResponse,
)
from app.services.spatial_service import SpatialService
from app.validators import validate_cdk, validate_crop, validate_year, validate_year_range

router = APIRouter(prefix="/spatial", tags=["Spatial Data"])


@router.get("/contagion", response_model=SpatialContagionResponse)
async def get_spatial_contagion(
    cdk: str = Query(..., description="Target district LGD code (as text)"),
    crop: str = Query("wheat", description="Crop name to analyze"),
    start_year: int = Query(2000, description="Start year of analysis window"),
    end_year: int = Query(2020, description="End year of analysis window"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Calculate agricultural growth spillovers using geographic adjacency (PostGIS).
    Compiles a target district's yield CAGR vs the average of its neighbors.
    """
    cdk = validate_cdk(cdk)
    crop = validate_crop(crop)
    start_year, end_year = validate_year_range(start_year, end_year)
    service = SpatialService(db)
    result = await service.get_spatial_contagion(cdk, crop, start_year, end_year)
    return result


@router.post("/calculate-split", response_model=SplitAreaCalculationResponse)
async def calculate_split(
    parent_geojson: UploadFile = File(..., description="Parent district GeoJSON"),
    child_geojson: UploadFile = File(..., description="Child district GeoJSON"),
):
    """
    Calculate the accurate Transferred Area and Remaining Area in square kilometers
    using Indian Equal Area projection (EPSG:7755) and GeoPandas.
    """
    service = SpatialService()
    parent_content = await parent_geojson.read()
    child_content = await child_geojson.read()
    return service.calculate_split_areas(parent_content, child_content)


@router.post("/diff", response_model=GenericStatusResponse)
async def calculate_spatial_diff(split_event_id: int, db: asyncpg.Connection = Depends(get_db)):
    """Calculate and write spatial difference and transferred areas for a split event."""
    service = SpatialService(db)
    return await service.calculate_spatial_diff(split_event_id)


@router.get("/lineage/{district_id}", response_model=DistrictLineageResponse)
async def get_district_lineage(district_id: str, db: asyncpg.Connection = Depends(get_db)):
    """Fetch all lineage split events and area transfers for a specific district."""
    district_id = validate_cdk(district_id)
    service = SpatialService(db)
    return await service.get_district_lineage(district_id)


@router.post("/upload-geojson", response_model=GenericStatusResponse)
async def upload_manual_geojson(
    district_id: str = Form(...),
    snapshot_year: int = Form(...),
    geojson_file: UploadFile = File(...),
    db: asyncpg.Connection = Depends(get_db),
):
    """Parses GeoJSON and saves as manual_upload to district_snapshots."""
    district_id = validate_cdk(district_id)
    snapshot_year = validate_year(snapshot_year, "snapshot_year")
    content = await geojson_file.read()
    service = SpatialService(db)
    return await service.upload_manual_geojson(district_id, snapshot_year, content)
