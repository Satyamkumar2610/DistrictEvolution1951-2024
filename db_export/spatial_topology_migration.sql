-- -----------------------------------------------------------------------------
-- Phase 2: PostGIS Topology Migration
-- -----------------------------------------------------------------------------
-- This script migrates our independent, potentially overlapping district polygons
-- into a strict topological model. Instead of storing independent shapes, we 
-- store shared boundary lines (edges) and construct districts out of "faces".
--
-- Benefits: Zero slivers, perfect area preservation upon splits, 
-- and native fast vector tile generation.

-- 1. Enable the Topology Extension 
-- (Requires PostGIS to be built with topology support)
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- 2. Create the topology namespace (tolerance ~1 meter in 4326 degrees roughly)
SELECT topology.CreateTopology('district_topo', 4326, 0.00001);

-- 3. Add a topological column to our existing snapshots table
SELECT topology.AddTopoGeometryColumn(
    'district_topo',          -- topology name
    'public',                 -- schema name
    'district_snapshots',     -- table name
    'topo_geom',              -- column name
    'MULTIPOLYGON'            -- feature type
);

-- -----------------------------------------------------------------------------
-- Example Migration Function (To be run by ETL script)
-- Converts standard GEOMETRY to TOPO_GEOM
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION migrate_to_topology() RETURNS void AS $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN SELECT id, geometry FROM district_snapshots WHERE geometry IS NOT NULL
    LOOP
        BEGIN
            -- Try to convert the geometry and add its edges to the topology mesh
            UPDATE district_snapshots
            SET topo_geom = topology.toTopoGeom(geometry, 'district_topo', 1, 0.00001)
            WHERE id = rec.id;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Skipping invalid geometry ID: %', rec.id;
        END;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- 4. Create a Martin/pg_tileserv compatible view
-- Vector tile clients (MapLibre) will hit this view directly
CREATE OR REPLACE VIEW api_vector_districts AS
SELECT 
    id,
    district_cdk,
    district_name,
    snapshot_year,
    -- Cast TopoGeometry back to GEOMETRY for MVT rendering out
    topology.AsGeometry(topo_geom) as geom
FROM district_snapshots
WHERE topo_geom IS NOT NULL;
