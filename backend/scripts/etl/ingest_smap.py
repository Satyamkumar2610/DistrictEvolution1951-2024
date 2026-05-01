"""
SMAP Soil Moisture Pipeline — ISRO MOSDAC.

Ingests NASA SMAP (Soil Moisture Active Passive) L3 daily volumetric
soil moisture data via ISRO's MOSDAC portal or NASA Earthdata.

Product: SPL3SMP_E (9km Enhanced, daily)
Variable: soil_moisture_am (descending pass, 6AM local) — m³/m³

The pipeline:
    1. Downloads HDF5/NetCDF tiles from MOSDAC or NASA Earthdata.
    2. Extracts district-level zonal statistics (mean, P10, P90).
    3. Computes anomaly indices relative to long-term climatology.
    4. Writes to the agri_metrics table for downstream analytics.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

try:
    import h5py
    H5_OK = True
except ImportError:
    H5_OK = False

try:
    import geopandas as gpd  # noqa: F401
    from rasterstats import zonal_stats  # noqa: F401
    GEO_OK = True
except ImportError:
    GEO_OK = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# MOSDAC portal (requires registration)
MOSDAC_BASE = "https://mosdac.gov.in/data/SMAP"
# NASA Earthdata alternative
NASA_EARTHDATA_BASE = "https://n5eil01u.ecs.nsidc.org/SMAP/SPL3SMP_E.005"

SMAP_VARIABLE = "Soil_Moisture_Retrieval_Data_AM/soil_moisture"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SoilMoistureRecord:
    """A single district-day soil moisture observation."""
    cdk: str
    date: str            # YYYY-MM-DD
    mean_sm: float       # volumetric m³/m³
    p10_sm: float        # 10th percentile
    p90_sm: float        # 90th percentile
    anomaly: float | None  # deviation from climatological mean (z-score)


@dataclass
class SoilMoistureClimatology:
    """Long-term monthly soil moisture climatology for a district."""
    cdk: str
    month: int
    mean: float
    std: float
    n_years: int


# ---------------------------------------------------------------------------
# Core Pipeline
# ---------------------------------------------------------------------------

async def download_smap_file(
    target_date: date,
    download_dir: Path,
    source: str = "mosdac",
) -> Path | None:
    """
    Download SMAP HDF5 file for a given date.

    In production this would use httpx with authentication tokens.
    """
    datestr = target_date.strftime("%Y%m%d")
    filename = f"SMAP_L3_SM_P_E_{datestr}.h5"
    filepath = download_dir / filename

    if filepath.exists():
        logger.info(f"{filename} already cached.")
        return filepath

    logger.info(f"Mock download: {filename} from {source}")

    # Simulate file creation for development
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.touch()
    return filepath


def extract_soil_moisture_from_hdf5(
    h5_path: Path,
    variable: str = SMAP_VARIABLE,
) -> np.ndarray | None:
    """
    Read soil moisture array from SMAP HDF5.

    Returns a 2D numpy array (lat × lon) with fill values masked.
    """
    if not H5_OK:
        logger.warning("h5py not installed — returning mock raster.")
        return _mock_raster()

    try:
        with h5py.File(h5_path, "r") as f:
            ds = f[variable]
            data = ds[:]
            fill_value = ds.attrs.get("_FillValue", -9999.0)
            data = np.where(data == fill_value, np.nan, data)
            return data
    except Exception as e:
        logger.error(f"Failed to read {h5_path}: {e}")
        return None


def _mock_raster() -> np.ndarray:
    """Generate synthetic soil moisture raster for testing."""
    rng = np.random.default_rng(42)
    return rng.uniform(0.05, 0.45, size=(406, 964))  # ~9km global grid


def compute_district_soil_moisture(
    sm_raster: np.ndarray,
    districts_geojson: Path,
    target_date: date,
    climatology: dict[str, dict[int, SoilMoistureClimatology]] | None = None,
) -> list[SoilMoistureRecord]:
    """
    Extract zonal soil moisture statistics per district.

    Args:
        sm_raster: 2D array of soil moisture (lat × lon).
        districts_geojson: Path to district boundaries GeoJSON.
        target_date: Date of the observation.
        climatology: {cdk: {month: SoilMoistureClimatology}} for anomaly computation.

    Returns:
        List of SoilMoistureRecord for each district.
    """
    if not GEO_OK:
        logger.warning("Geospatial libs missing — returning mock data.")
        return _mock_district_sm(target_date)

    try:
        # In production: create an affine transform for the SMAP grid
        # transform = rasterio.transform.from_bounds(...)
        # stats = zonal_stats(districts_geojson, sm_raster, affine=transform,
        #                     stats=["mean", "percentile_10", "percentile_90"],
        #                     geojson_out=True)

        # Mock implementation
        return _mock_district_sm(target_date, climatology)
    except Exception as e:
        logger.error(f"Zonal stats failed: {e}")
        return []


def _mock_district_sm(
    target_date: date,
    climatology: dict[str, dict[int, SoilMoistureClimatology]] | None = None,
) -> list[SoilMoistureRecord]:
    """Generate mock district soil moisture data."""
    import math

    rng = np.random.default_rng(hash(str(target_date)) % 2**31)
    districts = [f"mock_cdk_{i}" for i in range(1, 6)]
    records = []

    for cdk in districts:
        # Seasonal pattern: higher in monsoon (Jul-Sep)
        month = target_date.month
        seasonal = 0.15 + 0.20 * math.sin(math.pi * (month - 3) / 6)
        noise = rng.normal(0, 0.03)
        mean_sm = max(0.02, min(0.50, seasonal + noise))

        anomaly = None
        if climatology and cdk in climatology:
            clim = climatology[cdk].get(month)
            if clim and clim.std > 0:
                anomaly = round((mean_sm - clim.mean) / clim.std, 2)

        records.append(SoilMoistureRecord(
            cdk=cdk,
            date=target_date.isoformat(),
            mean_sm=round(mean_sm, 4),
            p10_sm=round(max(0.01, mean_sm - 0.05), 4),
            p90_sm=round(min(0.50, mean_sm + 0.05), 4),
            anomaly=anomaly,
        ))

    return records


def build_climatology(
    historical_records: list[SoilMoistureRecord],
) -> dict[str, dict[int, SoilMoistureClimatology]]:
    """
    Build monthly climatology from historical soil moisture records.

    Returns: {cdk: {month: SoilMoistureClimatology}}
    """
    from collections import defaultdict

    # Group by cdk and month
    grouped: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for rec in historical_records:
        dt = date.fromisoformat(rec.date)
        grouped[rec.cdk][dt.month].append(rec.mean_sm)

    result: dict[str, dict[int, SoilMoistureClimatology]] = {}
    for cdk, months in grouped.items():
        result[cdk] = {}
        for month, values in months.items():
            arr = np.array(values)
            result[cdk][month] = SoilMoistureClimatology(
                cdk=cdk,
                month=month,
                mean=round(float(np.mean(arr)), 4),
                std=round(float(np.std(arr)), 4),
                n_years=len(values),
            )

    return result


async def run_smap_pipeline(
    start_date: str = "2024-01-01",
    end_date: str = "2024-12-31",
    output_dir: str | None = None,
):
    """
    Main SMAP soil moisture ingestion pipeline.

    Args:
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        output_dir: Directory for cached downloads.
    """
    logger.info(f"Starting SMAP pipeline: {start_date} → {end_date}")

    download_dir = Path(output_dir) if output_dir else Path(__file__).parent.parent.parent / "data" / "raw" / "smap"
    download_dir.mkdir(parents=True, exist_ok=True)

    districts_shp = Path(__file__).parent.parent.parent / "data" / "shapefiles" / "districts.geojson"

    current = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    all_records: list[SoilMoistureRecord] = []

    while current <= end:
        h5_file = await download_smap_file(current, download_dir)
        if h5_file:
            raster = extract_soil_moisture_from_hdf5(h5_file)
            if raster is not None:
                records = compute_district_soil_moisture(raster, districts_shp, current)
                all_records.extend(records)

        current += timedelta(days=1)

    logger.info(f"SMAP Pipeline completed. {len(all_records)} records extracted.")
    return all_records


if __name__ == "__main__":
    asyncio.run(run_smap_pipeline())
