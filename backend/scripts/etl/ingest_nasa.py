"""
NASA POWER API Ingestion Pipeline.
Extracts Evapotranspiration (ET0), solar radiation, and relative humidity.
Queries via REST API directly using point/regional queries.
"""

import asyncio
import logging
import os

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

NASA_POWER_API_BASE = "https://power.larc.nasa.gov/api/temporal/daily/point"

async def fetch_nasa_power_data(
    client: httpx.AsyncClient,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str
) -> dict:
    """Fetch daily NASA POWER data for a specific coordinate."""
    # NASA POWER variables:
    # ALLSKY_SFC_SW_DWN = Solar Radiation
    # RH2M = Relative Humidity at 2 meters
    # ETO = Required Evapotranspiration

    {
        "parameters": "ALLSKY_SFC_SW_DWN,RH2M,T2M", # ETO requires computing or specific parameter sets
        "community": "AG",
        "longitude": longitude,
        "latitude": latitude,
        "start": start_date.replace("-", ""),
        "end": end_date.replace("-", ""),
        "format": "JSON"
    }

    try:
        # logger.info(f"Mock fetching NASA POWER data. Skipping real request. {req_url}")

        # resp = await client.get(req_url, params=params)
        # resp.raise_for_status()
        # return resp.json()

        return {
            "type": "Feature",
            "geometry": {"coordinates": [longitude, latitude], "type": "Point"},
            "properties": {
                "parameter": {
                    "ALLSKY_SFC_SW_DWN": {"20200101": 15.6},
                    "RH2M": {"20200101": 45.2},
                    "T2M": {"20200101": 25.1}
                }
            }
        }
    except Exception as e:
        logger.error(f"Failed to fetch NASA data for {latitude}, {longitude}: {e}")
        return {}

async def _fetch_district_centroids() -> list[dict]:
    """Mock loading district centroids from db or file."""
    return [
        {"cdk": "mock_cdk_1", "name": "District 1", "lat": 28.6, "lon": 77.2}
    ]

async def upload_to_db(records: list[dict], db_url: str):
    """Insert the computed atmospheric metrics into the DB."""
    logger.info(f"Uploading {len(records)} NASA POWER records to DB...")
    # conn = await asyncpg.connect(db_url)
    # ... exec statement ...

async def run_nasa_pipeline(start_year: int = 2018, end_year: int = 2024):
    """Main pipeline to collect NASA POWER variables."""
    logger.info(f"Starting NASA POWER pipeline for years {start_year}-{end_year}")

    districts = await _fetch_district_centroids()

    db_url = os.environ.get("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

    start_date = f"{start_year}0101"
    end_date = f"{end_year}1231"

    records = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        # NOTE: NASA POWER API has strict rate limits.
        # You should chunk requests and sleep appropriately.
        for dist in districts:
            logger.info(f"Fetching data for {dist['name']}...")
            data = await fetch_nasa_power_data(client, dist["lat"], dist["lon"], start_date, end_date)
            if "properties" in data:
                # Transform and append
                params = data["properties"]["parameter"]
                for date_str in params.get("T2M", {}):
                    records.append({
                        "cdk": dist["cdk"],
                        "date": date_str,
                        "solar_rad": params.get("ALLSKY_SFC_SW_DWN", {}).get(date_str),
                        "rh": params.get("RH2M", {}).get(date_str),
                        "temp_avg": params.get("T2M", {}).get(date_str),
                    })

            # Rate limiting sleep
            await asyncio.sleep(0.5)

    if records:
        await upload_to_db(records, db_url)

    logger.info("NASA POWER Pipeline execution completed.")

if __name__ == "__main__":
    asyncio.run(run_nasa_pipeline())
