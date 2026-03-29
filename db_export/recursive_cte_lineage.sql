-- -----------------------------------------------------------------------------
-- Recursive CTE for Lineage Traversal
-- Phase 1 of Lineage Reconstructor V2 Rewrite
-- -----------------------------------------------------------------------------
-- This query traverses the split_events table as a Directed Acyclic Graph (DAG)
-- entirely natively in Postgres. It replaces the Python memory BFS/DFS arrays.
--
-- Features:
-- 1. Unnests child_cdks array correctly for join condition.
-- 2. Tracks generation depth for topological sorting.
-- 3. Returns the exact sub-graph needed for a specific root_cdk.

WITH RECURSIVE lineage_tree AS (
    -- Base case: Find the initial split(s) originating from the root CDK
    SELECT 
        id as event_id,
        parent_cdk,
        child_cdks,
        split_year,
        ARRAY[parent_cdk] AS lineage_path, -- Tracks path to prevent infinite cycles
        1 as generation
    FROM split_events
    WHERE parent_cdk = :'root_cdk'  -- e.g., 'AR_NEFA_1951'

    UNION ALL

    -- Recursive case: Find subsequent splits where the new parent 
    -- was a child of a previous generation
    SELECT 
        se.id,
        se.parent_cdk,
        se.child_cdks,
        se.split_year,
        lt.lineage_path || se.parent_cdk,
        lt.generation + 1
    FROM split_events se
    JOIN lineage_tree lt 
      ON se.parent_cdk = ANY(lt.child_cdks)
    -- Cycle detection (DAG enforcement natively in postgres)
    WHERE NOT se.parent_cdk = ANY(lt.lineage_path) 
)
SELECT 
    event_id,
    parent_cdk,
    child_cdks,
    split_year,
    generation,
    lineage_path
FROM lineage_tree
ORDER BY generation ASC, split_year ASC;
