"""
Climate Web Scraper: Open-Meteo API Integration
Fetches historical temperature and soil moisture records for Indian districts
to augment the Crop Yield ML Prediction Engine.
"""

import asyncio
import logging
import os
import sys

import asyncpg
import httpx
from dotenv import load_dotenv

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("scrape_climate")

# Add backend to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../backend")))

load_dotenv(os.path.join(os.path.dirname(__file__), "../../backend/.env"))

# Open-Meteo APIs (Free, no keys required)
GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_API = "https://archive-api.open-meteo.com/v1/archive"


async def setup_database(conn: asyncpg.Connection):
    """Ensure the rainfall_normals table has the climate feature columns."""
    logger.info("Migrating rainfall_normals table schema...")
    await conn.execute("""
        ALTER TABLE rainfall_normals 
        ADD COLUMN IF NOT EXISTS temperature_c NUMERIC(5,2),
        ADD COLUMN IF NOT EXISTS soil_moisture_index NUMERIC(5,2);
    """)


async def fetch_coordinates(client: httpx.AsyncClient, district: str, state: str) -> tuple[float, float] | None:
    """Fetch Lat/Long for a given district name in India."""
    # Sometimes district names carry prefixes. Let's send a clean query.
    query = f"{district}, {state}, India"
    logger.debug(f"Geocoding: {query}")
    try:
        resp = await client.get(GEOCODING_API, params={"name": query, "count": 1, "language": "en", "format": "json"})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("results"):
                res = data["results"][0]
                return res["latitude"], res["longitude"]
    except Exception as e:
        logger.warning(f"Geocoding failed for {district}: {e}")
    return None


async def fetch_climate_normals(client: httpx.AsyncClient, lat: float, lon: float) -> tuple[float, float] | None:
    """
    Fetch annual temperature average and soil moisture index across 5 baseline years.
    Open-Meteo provides soil moisture as m³/m³ (0.0 to 1.0). We scale to an index 0-100.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": "2018-01-01",  # 5-year standardized climate normal
        "end_date": "2023-12-31",
        "daily": "temperature_2m_mean,soil_moisture_0_to_7cm_mean",
        "timezone": "auto"
    }

    try:
        resp = await client.get(ARCHIVE_API, params=params, timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            daily = data.get("daily", {})
            temps = [t for t in daily.get("temperature_2m_mean", []) if t is not None]
            moistures = [m for m in daily.get("soil_moisture_0_to_7cm_mean", []) if m is not None]

            if not temps or not moistures:
                return None

            avg_temp = sum(temps) / len(temps)
            
            # Average soil moisture across the years * 100 to get a 0-100 index
            avg_moist = (sum(moistures) / len(moistures)) * 100.0

            return round(avg_temp, 2), round(avg_moist, 2)
    except Exception as e:
        logger.warning(f"Climate API failed at {lat},{lon}: {e}")
        
    return None


async def run_scraper():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not found in .env")
        return

    conn = await asyncpg.connect(db_url)
    try:
        await setup_database(conn)

        # Get districts that need processing
        districts = await conn.fetch("""
            SELECT id, district, state_ut 
            FROM rainfall_normals 
            WHERE temperature_c IS NULL 
            LIMIT 50;  -- Limit to 50 for quick API testing iteration
        """)

        if not districts:
            logger.info("No districts require climate processing at this time.")
            return

        logger.info(f"Loaded {len(districts)} districts requiring temperature and moisture variables.")

        update_query = """
            UPDATE rainfall_normals 
            SET temperature_c = $1, soil_moisture_index = $2
            WHERE id = $3
        """

        async with httpx.AsyncClient() as client:
            success_count = 0
            for row in districts:
                d_id = row["id"]
                dist_name = row["district"]
                state_name = row["state_ut"]

                coords = await fetch_coordinates(client, dist_name, state_name)
                if not coords:
                    # Fallback to random realistic ranges based on geo if API fails to find it
                    continue

                lat, lon = coords
                climate = await fetch_climate_normals(client, lat, lon)

                if climate:
                    temp, moisture = climate
                    await conn.execute(update_query, temp, moisture, d_id)
                    success_count += 1
                    logger.info(f"✅ {dist_name} ({state_name}) -> Temp: {temp}°C | Moisture: {moisture}")
                else:
                    logger.warning(f"❌ {dist_name} ({state_name}) -> No data.")

                # Small delay to respect Open-Meteo free tier limits
                await asyncio.sleep(0.5)

        logger.info(f"Climate enrichment complete. Processed {success_count}/{len(districts)} records.")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_scraper())
