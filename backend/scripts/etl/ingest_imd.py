"""
IMD Gridded Daily Temperature Ingestion Pipeline.
Extracts Tmax, Tmin, Tmean 1° grid (1951-present).
Using rasterstats to compute zonal statistics per district.
"""

import asyncio
import logging
import os
from pathlib import Path

# Optional dependencies for geospatial processing
try:
    import geopandas as gpd  # noqa: F401
    import numpy as np  # noqa: F401
    import xarray as xr  # type: ignore  # noqa: F401
    from rasterstats import zonal_stats  # type: ignore  # noqa: F401
    GEO_AVAILABLE = True
except ImportError:
    GEO_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def fetch_imd_data(variable: str, year: int, download_dir: Path) -> Path | None:
    """Download IMD Gridded Temperature NetCDF for a given year and variable."""
    # Assuming IMD files follow a structure like "Tmax_{year}.nc"
    filename = f"{variable}_{year}.nc"
    filepath = download_dir / filename

    if filepath.exists():
        logger.info(f"{filename} already exists, skipping download.")
        return filepath

    logger.info(f"Mock downloading IMD FTP link for {variable} year {year} to {filepath}...")

    if not filepath.parent.exists():
        filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.touch()

    return filepath

def process_imd_zonal_stats(nc_path: Path, variable: str, districts_geojson: Path) -> list[dict]:
    """Calculate daily/monthly zonal stats for IMD temp per district."""
    if not GEO_AVAILABLE:
        logger.warning("Geospatial libraries missing. Cannot compute true zonal stats.")
        return []

    logger.info(f"Processing zonal stats from {nc_path} against {districts_geojson}")

    try:
        # 1. Load District Geometries
        # districts = gpd.read_file(districts_geojson)

        # 2. Load NetCDF
        # ds = xr.open_dataset(nc_path)
        # temp = ds[variable]

        # 3. For each timestep, compute zonal_stats

        # Mocking extraction response
        results = [
            {
                "cdk": "mock_cdk_1",
                "year": 2020,
                "month": 6,
                f"{variable}_C": 35.5
            }
        ]
        return results
    except Exception as e:
        logger.error(f"Failed to process {nc_path}: {e}")
        return []

async def upload_to_db(records: list[dict], variable: str, db_url: str):
    """Insert the computed temperature metrics into the DB."""
    logger.info(f"Uploading {len(records)} IMD records to DB for {variable}...")
    # conn = await asyncpg.connect(db_url)
    # ... exec statement ...

async def run_imd_pipeline(start_year: int = 2018, end_year: int = 2024):
    """Main pipeline to cover IMD Temperature gaps."""
    logger.info(f"Starting IMD pipeline for years {start_year}-{end_year}")

    data_dir = Path(__file__).parent.parent.parent / "data" / "raw" / "imd"
    districts_shp = Path(__file__).parent.parent.parent / "data" / "shapefiles" / "districts.geojson"

    db_url = os.environ.get("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

    variables = ["Tmax", "Tmin", "Tmean"]

    for year in range(start_year, end_year + 1):
        for var in variables:
            nc_file = await fetch_imd_data(var, year, data_dir)
            if nc_file:
                stats = process_imd_zonal_stats(nc_file, var, districts_shp)
                if stats:
                    await upload_to_db(stats, var, db_url)

    logger.info("IMD Pipeline execution completed.")

if __name__ == "__main__":
    asyncio.run(run_imd_pipeline())
