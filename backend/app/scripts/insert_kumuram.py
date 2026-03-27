import asyncio
import json
import os

import asyncpg


async def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set.")

    print("Loading GeoJSON...")
    with open("/Users/satyamkumar/Desktop/DistrictEvolution/data/raw/INDIA_DISTRICTS.geojson") as f:
        geojson = json.load(f)

    kumuram_geom_json = None
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        district = props.get("district")
        if district and "KOMARRAM" in district:
            kumuram_geom_json = json.dumps(feature.get("geometry"))
            break

    if not kumuram_geom_json:
        print("Kumuram Bheem not found in GeoJSON")
        return

    print("Connecting to DB...")
    conn = await asyncpg.connect(db_url)
    try:
        print("Inserting Kumuram Bheem...")
        await conn.execute("""
            INSERT INTO district_snapshots
                (district_cdk, snapshot_year, district_name, geometry_source, geometry_confidence, geometry)
            VALUES
                ('699', 2024, 'KUMURAM BHEEM ASIFABAD', 'manual_upload', 0.8, ST_GeomFromGeoJSON($1))
            ON CONFLICT (district_cdk, snapshot_year) DO UPDATE SET
                geometry = EXCLUDED.geometry,
                geometry_source = EXCLUDED.geometry_source,
                geometry_confidence = EXCLUDED.geometry_confidence;
        """, kumuram_geom_json)

        await conn.execute("""
            UPDATE district_snapshots
            SET area_sqkm = ST_Area(geometry::geography) / 1000000.0
            WHERE district_cdk = '699' AND snapshot_year = 2024;
        """)
        print("Kumuram Bheem inserted.")

        print("Reconstructing parent Adilabad (2011)...")
        await conn.execute("""
            INSERT INTO district_snapshots
                (district_cdk, snapshot_year, district_name, geometry_source, geometry_confidence, geometry, area_sqkm)
            SELECT
                'TG_adilab_2011', 2011, 'ADILABAD (PRE-SPLIT)', 'manual_upload', 0.9,
                ST_Union(geometry), SUM(area_sqkm)
            FROM district_snapshots
            WHERE district_cdk IN ('501', '680', '684', '699')
              AND snapshot_year = 2024
              AND geometry IS NOT NULL
            ON CONFLICT (district_cdk, snapshot_year) DO UPDATE SET
                geometry = EXCLUDED.geometry,
                area_sqkm = EXCLUDED.area_sqkm,
                geometry_source = 'manual_upload';
        """)
        print("Parent Adilabad reconstructed.")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
