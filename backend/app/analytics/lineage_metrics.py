"""
Lineage Metrics Analytics Module
Computes Research Metrics: District Stability Index, Boundary Volatility Index, Administrative Fragmentation Index, and Lineage Depth Score.
"""

from typing import Dict, Any, List
import asyncpg

class LineageMetricsEngine:
    def __init__(self, db: asyncpg.Connection):
        self.db = db

    async def compute_district_stability_index(self) -> List[Dict[str, Any]]:
        """
        District Stability Index = (Years without split) / (Total Years Active).
        Since we don't have exact year-by-year splits for all, we use:
        1 - (Number of Splits / (End Year - Start Year))
        """
        query = """
            SELECT d.cdk, d.district_name, d.state_name, 
                   d.start_year, d.end_year,
                   COUNT(ds.id) as split_count
            FROM districts d
            LEFT JOIN district_splits ds ON ds.parent_district = d.district_name 
                                        AND ds.state_name = d.state_name
            WHERE d.start_year IS NOT NULL
            GROUP BY d.cdk, d.district_name, d.state_name, d.start_year, d.end_year
        """
        rows = await self.db.fetch(query)
        results = []
        for r in rows:
            end_yr = r['end_year'] or 2024
            active_years = max(end_yr - r['start_year'], 1)
            splits = r['split_count']
            stability = max(1.0 - (splits / active_years), 0.0)
            results.append({
                "cdk": r['cdk'],
                "district_name": r['district_name'],
                "state_name": r['state_name'],
                "stability_index": round(stability, 4),
                "splits": splits,
                "active_years": active_years
            })
        return results

    async def compute_boundary_volatility_index(self) -> List[Dict[str, Any]]:
        """
        Boundary Volatility Index = Frequency of splits per state per decade.
        """
        query = """
            SELECT state_name, decade, count(id) as split_events
            FROM district_splits
            GROUP BY state_name, decade
            ORDER BY state_name, decade
        """
        rows = await self.db.fetch(query)
        return [dict(r) for r in rows]

    async def compute_fragmentation_index(self) -> List[Dict[str, Any]]:
        """
        Administrative Fragmentation Index = Total modern children / 1 historical parent.
        """
        query = """
            SELECT parent_district, state_name, count(id) as child_count
            FROM district_splits
            GROUP BY parent_district, state_name
            HAVING count(id) > 1
            ORDER BY child_count DESC
        """
        rows = await self.db.fetch(query)
        return [dict(r) for r in rows]

    async def compute_lineage_depth_score(self) -> List[Dict[str, Any]]:
        """
        Lineage Depth Score = Maximum depth of the DAG.
        We approximate this by checking multi-level splits (e.g. A->B->C).
        """
        query = """
            WITH RECURSIVE lineage_tree AS (
                SELECT ds.parent_district, ds.child_district, ds.state_name, 1 as depth
                FROM district_splits ds
                
                UNION ALL
                
                SELECT lt.parent_district, ds.child_district, ds.state_name, lt.depth + 1
                FROM district_splits ds
                JOIN lineage_tree lt ON ds.parent_district = lt.child_district AND ds.state_name = lt.state_name
            )
            SELECT parent_district, state_name, MAX(depth) as depth_score
            FROM lineage_tree
            GROUP BY parent_district, state_name
            ORDER BY depth_score DESC
        """
        rows = await self.db.fetch(query)
        return [dict(r) for r in rows]
