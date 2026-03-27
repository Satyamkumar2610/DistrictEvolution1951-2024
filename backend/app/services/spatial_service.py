from typing import Any

import asyncpg


class SpatialService:
    def __init__(self, db: asyncpg.Connection):
        self.db = db

    async def get_neighbors(self, cdk: str) -> list[dict[str, Any]]:
        """
        Find all immediately adjacent neighboring districts using PostGIS ST_Touches.
        """
        query = """
            WITH target AS (
                SELECT geometry, lgd_code, "DISTRICT" as district_name, "ST_NM" as state_name
                FROM districts_geo
                WHERE lgd_code = $1
            )
            SELECT
                n.lgd_code as neighbor_cdk,
                n."DISTRICT" as neighbor_name,
                n."ST_NM" as neighbor_state
            FROM districts_geo n
            JOIN target t ON ST_Touches(t.geometry, n.geometry)
            WHERE n.lgd_code != $1
            ORDER BY n."DISTRICT"
        """
        # Convert cdk to float because lgd_code in districts_geo is double
        # precision
        try:
            lgd_val = float(cdk)
        except ValueError:
            return []

        rows = await self.db.fetch(query, lgd_val)
        return [dict(r) for r in rows]

    async def get_cagr(self, cdk: str, crop: str, start_year: int, end_year: int) -> float:
        """
        Helper method to get CAGR of a crop yield for a district.
        """
        rows = await self.db.fetch("""
            SELECT year, value
            FROM agri_metrics
            WHERE district_lgd::text = $1
              AND variable_name = $2
              AND year BETWEEN $3 AND $4
              AND value > 0
            ORDER BY year
        """, cdk, f"{crop}_yield", start_year, end_year)

        if len(rows) < 2:
            return 0.0

        start_val = rows[0]['value']
        end_val = rows[-1]['value']
        n_years = rows[-1]['year'] - rows[0]['year']

        if n_years > 0 and start_val > 0:
            return ((end_val / start_val) ** (1 / n_years)) - 1
        return 0.0

    async def get_spatial_contagion(
        self,
        cdk: str,
        crop: str,
        start_year: int,
        end_year: int
    ) -> dict[str, Any]:
        """
        Calculates the spillover effect by comparing a district's growth
        to the average growth of its geographic neighbors.
        """
        # Get the target district's growth
        target_cagr = await self.get_cagr(cdk, crop, start_year, end_year)

        # Get target name
        target_meta = await self.db.fetchrow("SELECT district_name, state_name FROM districts WHERE lgd_code::text = $1", cdk)
        target_name = target_meta["district_name"] if target_meta else cdk

        # Get neighbors
        neighbors = await self.get_neighbors(cdk)

        neighbor_results = []
        for n in neighbors:
            n_cdk = str(int(n["neighbor_cdk"]))
            n_cagr = await self.get_cagr(n_cdk, crop, start_year, end_year)
            neighbor_results.append({
                "cdk": n_cdk,
                "name": n["neighbor_name"],
                "state": n["neighbor_state"],
                "cagr": round(n_cagr * 100, 2)
            })

        # Compute regional cluster average
        valid_cagrs = [n["cagr"] for n in neighbor_results if n["cagr"] != 0.0]
        if valid_cagrs:
            regional_avg_cagr = sum(valid_cagrs) / len(valid_cagrs)
        else:
            regional_avg_cagr = 0.0

        target_cagr_pct = round(target_cagr * 100, 2)
        diff = target_cagr_pct - regional_avg_cagr

        if target_cagr_pct > 0 and regional_avg_cagr > 0 and diff > 5:
            spillover_category = "Outperformer"
        elif target_cagr_pct < 0 and regional_avg_cagr < 0 and diff < -5:
            spillover_category = "Underperformer"
        elif target_cagr_pct > 0 and regional_avg_cagr > 0 and abs(diff) <= 5:
            spillover_category = "Clustered Growth"
        elif target_cagr_pct < 0 and regional_avg_cagr < 0 and abs(diff) <= 5:
            spillover_category = "Clustered Decline"
        else:
            spillover_category = "Divergent"

        return {
            "target": {
                "cdk": cdk,
                "name": target_name,
                "cagr": target_cagr_pct},
            "regional_avg_cagr": round(
                regional_avg_cagr,
                2),
            "spillover_category": spillover_category,
            "period": f"{start_year}-{end_year}",
            "crop": crop,
            "neighbors": sorted(
                neighbor_results,
                key=lambda x: x["cagr"],
                reverse=True)}
