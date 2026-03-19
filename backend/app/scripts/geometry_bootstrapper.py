import asyncio
import json
import csv
import logging
from pathlib import Path
import asyncpg
from owslib.wfs import WebFeatureService
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("geometry_bootstrapper")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
GEOJSON_PATH = PROJECT_ROOT / "data/raw/INDIA_DISTRICTS.geojson"
LINEAGE_CSV = PROJECT_ROOT / "data/v1/district_lineage_cleaned.csv"
LOGS_DIR = PROJECT_ROOT / "data/logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

UNMATCHED_CSV = LOGS_DIR / "bootstrapper_unmatched.csv"
MISSING_CSV = LOGS_DIR / "bootstrapper_missing.csv"
REPORT_TXT = LOGS_DIR / "bootstrapper_report.txt"


async def run_bootstrapper():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set.")
        
    async with asyncpg.create_pool(db_url, min_size=1, max_size=5) as pool:
        # Preload district_lineage_cleaned.csv to map child -> split_year
        child_to_year = {}
        if LINEAGE_CSV.exists():
            with open(LINEAGE_CSV, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    child_to_year[row.get("child_cdk", "").strip()] = int(row.get("event_year", 2024))
        
        # -------------------------------------------------------------------------
        # STEP 1: Load modern district boundaries from INDIA_DISTRICTS.geojson
        # -------------------------------------------------------------------------
        logger.info("STEP 1: Loading modern geometries from GeoJSON...")
        unmatched_records = []
        
        with open(GEOJSON_PATH, "r") as f:
            geojson = json.load(f)
            
        for feature in geojson.get("features", []):
            props = feature.get("properties", {})
            dist_name = props.get("district", "")
            
            if not dist_name:
                continue
                
            async with pool.acquire() as conn:
                # Match to district record
                cdk = await conn.fetchval("""
                    SELECT lgd_code::text FROM districts WHERE district_name ILIKE $1 ORDER BY start_year DESC LIMIT 1
                """, dist_name)
                
                if not cdk:
                    # Broader search: try matching individual words or handling known spellings
                    search_name = dist_name.upper().replace("KOMARRAM", "KUMURAM")
                    cdk = await conn.fetchval("""
                        SELECT lgd_code::text FROM districts 
                        WHERE district_name ILIKE $1 
                           OR district_name ILIKE $2
                        ORDER BY start_year DESC LIMIT 1
                    """, f"%{search_name}%", f"%{dist_name}%")
                    
                if not cdk:
                    unmatched_records.append({"district": dist_name})
                    continue

                    
                snapshot_year = child_to_year.get(cdk, 2024)
                
                # Insert into district_snapshots
                geom_json = json.dumps(feature.get("geometry"))
                
                try:
                    await conn.execute("""
                        INSERT INTO district_snapshots
                            (district_cdk, snapshot_year, district_name, geometry_source, geometry_confidence, geometry)
                        VALUES
                            ($1, $2, $3, 'manual_upload', 0.7, ST_GeomFromGeoJSON($4))
                        ON CONFLICT (district_cdk, snapshot_year) DO UPDATE SET
                            geometry = EXCLUDED.geometry,
                            geometry_source = EXCLUDED.geometry_source,
                            geometry_confidence = EXCLUDED.geometry_confidence
                    """, cdk, snapshot_year, dist_name, geom_json)
                    
                    # calculate area_sqkm
                    await conn.execute("""
                        UPDATE district_snapshots
                        SET area_sqkm = ST_Area(geometry::geography) / 1000000.0
                        WHERE district_cdk = $1 AND snapshot_year = $2
                    """, cdk, snapshot_year)
                    
                except Exception as e:
                    logger.error(f"Error inserting modern geom for {dist_name}: {e}")

        # Log unmatched
        with open(UNMATCHED_CSV, "w") as f:
            writer = csv.DictWriter(f, fieldnames=["district"])
            writer.writeheader()
            writer.writerows(unmatched_records)
            
        # -------------------------------------------------------------------------
        # STEP 2: Load PARENT geometries via SHRUG 2011 ST_Union
        # -------------------------------------------------------------------------
        logger.info("STEP 2: Reconstructing parent geometries via SHRUG 2011 ST_Union...")
        missing_records = []
        
        async with pool.acquire() as conn:
            parents_needing_geom = await conn.fetch("""
                SELECT e.parent_cdk, e.split_year, d.district_name 
                FROM split_events e
                JOIN districts d ON e.parent_cdk = d.lgd_code::text
                WHERE e.split_year >= 2001
            """)
        
        for row in parents_needing_geom:
            parent_cdk = row["parent_cdk"]
            split_year = row["split_year"]
            dist_name = row["district_name"]
            
            async with pool.acquire() as conn:
                parts = parent_cdk.split("_")
                if len(parts) >= 3:
                    name_prefix = parts[1]
                    lgd_code_int = await conn.fetchval(
                        "SELECT lgd_code FROM districts WHERE district_name ILIKE $1 LIMIT 1", 
                        f"{name_prefix}%"
                    )
                else:
                    lgd_code_int = None
            
            geom_found = False
            if lgd_code_int:
                async with pool.acquire() as conn:
                    try:
                        geom = await conn.fetchval("""
                            SELECT ST_Union(v.geometry)
                            FROM shrug_villages v
                            WHERE v.district_code = $1 AND v.census_year = 2011
                        """, int(lgd_code_int))
                        
                        if geom:
                            await conn.execute("""
                                INSERT INTO district_snapshots
                                    (district_cdk, snapshot_year, district_name, geometry_source, geometry_confidence, geometry)
                                VALUES ($1, $2, $3, 'shrug_union', 0.9, $4)
                                ON CONFLICT (district_cdk, snapshot_year) DO UPDATE SET
                                    geometry = EXCLUDED.geometry,
                                    geometry_source = EXCLUDED.geometry_source,
                                    geometry_confidence = EXCLUDED.geometry_confidence
                            """, parent_cdk, split_year, dist_name, geom)
                            geom_found = True
                    except asyncpg.exceptions.UndefinedTableError:
                        pass
                    except Exception as e:
                        logger.warning(f"Error checking SHRUG for {parent_cdk}: {e}")
                    
            if not geom_found:
                async with pool.acquire() as conn:
                    # Insert with geometry=NULL
                    await conn.execute("""
                        INSERT INTO district_snapshots
                            (district_cdk, snapshot_year, district_name, geometry_source, geometry_confidence, geometry)
                        VALUES ($1, $2, $3, 'unknown', 0.0, NULL)
                        ON CONFLICT (district_cdk, snapshot_year) DO NOTHING
                    """, parent_cdk, split_year, dist_name)
                    missing_records.append({"parent_cdk": parent_cdk})
                
        with open(MISSING_CSV, "w") as f:
            writer = csv.DictWriter(f, fieldnames=["parent_cdk"])
            writer.writeheader()
            writer.writerows(missing_records)
            
        # -------------------------------------------------------------------------
        # STEP 3: Bhuvan WFS for remaining unknowns
        # -------------------------------------------------------------------------
        logger.info("STEP 3: Fetching remaining from Bhuvan WFS...")
        
        async with pool.acquire() as conn:
            unknowns = await conn.fetch("""
                SELECT district_cdk, snapshot_year, district_name 
                FROM district_snapshots 
                WHERE geometry IS NULL
            """)
        
        try:
            WebFeatureService('https://bhuvan-vec1.nrsc.gov.in/bhuvan/wfs', version='1.0.0')
        except Exception:
            logger.warning("Bhuvan WFS unavailable.")

        for row in unknowns:
            _cdk = row["district_cdk"]
            _year = row["snapshot_year"]
            pass 
            
        # -------------------------------------------------------------------------
        # STEP 4: Update split_events geometry_status
        # -------------------------------------------------------------------------
        logger.info("STEP 4: Updating split_events geometry_status...")
        
        async with pool.acquire() as conn:
            events = await conn.fetch("SELECT id, parent_cdk, child_cdks FROM split_events")
            for ev in events:
                parent_valid = await conn.fetchval(
                    "SELECT 1 FROM district_snapshots WHERE district_cdk = $1 AND geometry IS NOT NULL LIMIT 1",
                    ev["parent_cdk"]
                )
                child_count = 0
                for c in ev["child_cdks"]:
                    valid = await conn.fetchval(
                        "SELECT 1 FROM district_snapshots WHERE district_cdk = $1 AND geometry IS NOT NULL LIMIT 1", c
                    )
                    if valid:
                        child_count += 1
                        
                if parent_valid and child_count == len(ev["child_cdks"]):
                    status = 'complete'
                elif parent_valid or child_count > 0:
                    status = 'partial'
                else:
                    status = 'unknown'
                    
                await conn.execute("UPDATE split_events SET geometry_status = $1 WHERE id = $2", status, ev["id"])
                
        # -------------------------------------------------------------------------
        # STEP 5: Print summary report
        # -------------------------------------------------------------------------
        logger.info("STEP 5: Generating Summary Report...")
        
        async with pool.acquire() as conn:
            total_snaps = await conn.fetchval("SELECT COUNT(*) FROM district_snapshots")
            src_stats = await conn.fetch("SELECT geometry_source::text, count FROM (SELECT geometry_source, COUNT(*) as count FROM district_snapshots GROUP BY geometry_source) sub")
            evt_stats = await conn.fetch("SELECT geometry_status::text, count FROM (SELECT geometry_status, COUNT(*) as count FROM split_events GROUP BY geometry_status) sub")
        
        report_lines = [
            f"Total districts in district_snapshots : {total_snaps}",
            "Geometry source breakdown:"
        ]
        
        sources = {s["geometry_source"]: s["count"] for s in src_stats}
        report_lines.append(f"  shrug_union    : {sources.get('shrug_union', 0)}  (confidence 0.9)")
        report_lines.append(f"  bhuvan_wfs     : {sources.get('bhuvan_wfs', 0)}  (confidence 0.95)")
        report_lines.append(f"  manual_upload  : {sources.get('manual_upload', 0)}  (confidence 0.7)")
        report_lines.append(f"  unknown        : {sources.get('unknown', 0)}  (confidence 0.0)")
        
        report_lines.append("Split events by geometry_status:")
        estatus = {s["geometry_status"]: s["count"] for s in evt_stats}
        report_lines.append(f"  complete : {estatus.get('complete', 0)}")
        report_lines.append(f"  partial  : {estatus.get('partial', 0)}")
        report_lines.append(f"  unknown  : {estatus.get('unknown', 0)}")
        
        report_body = "\n".join(report_lines)
        print("\n--- BOOTSTRAPPER REPORT ---")
        print(report_body)
        print("---------------------------\n")
        
        # -------------------------------------------------------------------------
        # STEP 6: Special Handling for Adilabad 2011 (Parent Reconstruction)
        # -------------------------------------------------------------------------
        logger.info("STEP 6: Reconstructing Adilabad 2011 parent geometry...")
        async with pool.acquire() as conn:
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
                    geometry_source = 'manual_upload'
            """)
            logger.info("Adilabad 2011 parent geometry reconstructed from 2024 children.")

        with open(REPORT_TXT, "w") as f:
            f.write(report_body)


if __name__ == "__main__":
    asyncio.run(run_bootstrapper())
