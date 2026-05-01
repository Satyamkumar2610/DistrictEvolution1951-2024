"""
Pre-compute district dashboard snapshots for high-traffic districts.
Dumps API output for the top 50 districts into static JSON files for Edge caching.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

API_BASE = "http://localhost:8000/api/v1"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "snapshots"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

async def fetch_district_data(client: httpx.AsyncClient, cdk: str) -> dict[str, Any] | None:
    """Fetch complete dashboard data for a district."""
    try:
        # Fetch base info
        info_resp = await client.get(f"{API_BASE}/districts/{cdk}")
        info_resp.raise_for_status()

        # Parallel fetch for other necessary dashboard chunks
        # e.g., yield forecast, anomalies, etc.
        # This mirrors what the frontend requests on page load
        analysis_resp, anomaly_resp = await asyncio.gather(
            client.get(f"{API_BASE}/analysis/district/{cdk}"),
            client.get(f"{API_BASE}/anomalies/district/{cdk}"),
            return_exceptions=True
        )

        data = {
            "info": info_resp.json(),
            "analysis": analysis_resp.json() if isinstance(analysis_resp, httpx.Response) and analysis_resp.status_code == 200 else None,
            "anomalies": anomaly_resp.json() if isinstance(anomaly_resp, httpx.Response) and anomaly_resp.status_code == 200 else None,
        }
        return data

    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch data for {cdk}: {e}")
        return None

async def main():
    """Main execution function."""
    logger.info("Starting dashboard pre-computation...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Fetch top districts (for this script, we'll just grab the first 50 returned)
        # In a real environment, you might sort by agricultural importance or area
        try:
            resp = await client.get(f"{API_BASE}/districts")
            resp.raise_for_status()
            all_districts = resp.json().get("items", [])
            top_districts = all_districts[:50]
        except httpx.HTTPError as e:
            logger.error(f"Could not fetch district list: {e}")
            return

        logger.info(f"Pre-computing snapshots for {len(top_districts)} districts...")

        # 2. Iterate and fetch full snapshots
        success_count = 0
        for idx, district in enumerate(top_districts):
            cdk = district["cdk"]
            logger.info(f"[{idx+1}/{len(top_districts)}] Processing {cdk}...")

            data = await fetch_district_data(client, cdk)

            if data:
                # Save to JSON
                outfile = OUTPUT_DIR / f"{cdk}_snapshot.json"
                with open(outfile, "w") as f:
                    json.dump(data, f, indent=2)
                success_count += 1

    logger.info(f"Completed. Generated {success_count} pre-computed snapshots.")

if __name__ == "__main__":
    asyncio.run(main())
