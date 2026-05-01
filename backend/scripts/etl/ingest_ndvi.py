"""
MODIS NDVI Pipeline — Google Earth Engine Python API.

Pulls MODIS MOD13Q1 (250m, 16-day) NDVI composites and extracts
district-level monthly vegetation profiles using GEE's reduceRegions.

Requires:
  - google-auth + earthengine-api (`pip install earthengine-api`)
  - An authenticated service account or `ee.Authenticate()` prior to use.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

try:
    import ee
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    logger.warning("earthengine-api not installed — NDVI pipeline disabled.")


def _init_ee():
    """Initialize Earth Engine with service account or interactive auth."""
    if not EE_AVAILABLE:
        raise RuntimeError("earthengine-api is not installed.")

    try:
        # Attempt service account auth (CI / server)
        sa_key = os.environ.get("EE_SERVICE_ACCOUNT_KEY")
        if sa_key:
            credentials = ee.ServiceAccountCredentials(
                email=os.environ.get("EE_SERVICE_ACCOUNT_EMAIL", ""),
                key_file=sa_key,
            )
            ee.Initialize(credentials)
        else:
            # Interactive / cached auth
            ee.Initialize()
        logger.info("Earth Engine initialized successfully.")
    except Exception as e:
        logger.error(f"Earth Engine initialization failed: {e}")
        raise


def extract_district_ndvi(
    district_geometry: dict[str, Any],
    cdk: str,
    start_year: int,
    end_year: int,
) -> list[dict[str, Any]]:
    """
    Extract monthly mean NDVI for a single district polygon.

    Args:
        district_geometry: GeoJSON geometry dict for the district boundary.
        cdk: District CDK identifier.
        start_year: Start of the time window.
        end_year: End of the time window (inclusive).

    Returns:
        List of {cdk, year, month, mean_ndvi, max_ndvi, min_ndvi} dicts.
    """
    if not EE_AVAILABLE:
        logger.warning("Returning mock data — earthengine-api not available.")
        return _mock_ndvi(cdk, start_year, end_year)

    _init_ee()

    roi = ee.Geometry(district_geometry)

    results = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            start_date = f"{year}-{month:02d}-01"
            # Handle end-of-month
            end_date = f"{year + 1}-01-01" if month == 12 else f"{year}-{month + 1:02d}-01"

            try:
                # MODIS MOD13Q1 — 250m 16-day NDVI
                collection = (
                    ee.ImageCollection("MODIS/061/MOD13Q1")
                    .filterDate(start_date, end_date)
                    .filterBounds(roi)
                    .select("NDVI")
                )

                # Scale factor: MODIS NDVI is stored as int × 10000
                composite = collection.mean().multiply(0.0001)

                stats = composite.reduceRegion(
                    reducer=ee.Reducer.mean()
                    .combine(ee.Reducer.max(), sharedInputs=True)
                    .combine(ee.Reducer.min(), sharedInputs=True),
                    geometry=roi,
                    scale=250,
                    maxPixels=1e9,
                ).getInfo()

                results.append({
                    "cdk": cdk,
                    "year": year,
                    "month": month,
                    "mean_ndvi": round(stats.get("NDVI_mean", 0) or 0, 4),
                    "max_ndvi": round(stats.get("NDVI_max", 0) or 0, 4),
                    "min_ndvi": round(stats.get("NDVI_min", 0) or 0, 4),
                })

            except Exception as e:
                logger.warning(f"GEE query failed for {cdk} {year}-{month:02d}: {e}")

    return results


def _mock_ndvi(cdk: str, start_year: int, end_year: int) -> list[dict[str, Any]]:
    """Generate synthetic NDVI data for testing when GEE is unavailable."""
    import math
    results = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            # Simulate seasonal NDVI curve peaking during monsoon (Jul-Sep)
            base = 0.35
            seasonal = 0.25 * math.sin(math.pi * (month - 3) / 6)
            ndvi = max(0.1, base + seasonal)
            results.append({
                "cdk": cdk,
                "year": year,
                "month": month,
                "mean_ndvi": round(ndvi, 4),
                "max_ndvi": round(ndvi + 0.08, 4),
                "min_ndvi": round(ndvi - 0.08, 4),
            })
    return results


async def run_ndvi_pipeline(
    districts_geojson_path: str,
    start_year: int = 2015,
    end_year: int = 2024,
    output_dir: str | None = None,
):
    """
    Batch NDVI extraction for all districts in a GeoJSON file.

    Args:
        districts_geojson_path: Path to a FeatureCollection GeoJSON
            where each feature has a 'cdk' property.
        start_year: Start year.
        end_year: End year.
        output_dir: Optional path to write per-district JSON results.
    """
    logger.info(f"Starting NDVI pipeline for {start_year}-{end_year}")

    with open(districts_geojson_path) as f:
        fc = json.load(f)

    features = fc.get("features", [])
    logger.info(f"Processing {len(features)} districts...")

    out_path = Path(output_dir) if output_dir else Path(__file__).parent.parent.parent / "data" / "ndvi"
    out_path.mkdir(parents=True, exist_ok=True)

    for i, feature in enumerate(features):
        cdk = feature["properties"].get("cdk", f"unknown_{i}")
        geometry = feature["geometry"]

        logger.info(f"[{i + 1}/{len(features)}] Extracting NDVI for {cdk}...")
        records = extract_district_ndvi(geometry, cdk, start_year, end_year)

        outfile = out_path / f"{cdk}_ndvi.json"
        with open(outfile, "w") as f:
            json.dump(records, f, indent=2)

    logger.info("NDVI Pipeline completed.")


if __name__ == "__main__":
    import sys
    geojson_path = sys.argv[1] if len(sys.argv) > 1 else "data/shapefiles/districts.geojson"
    asyncio.run(run_ndvi_pipeline(geojson_path))
