"""
Metric Repository: Data access for agricultural/domain metrics.
Uses district_lgd (int FK) joined to districts.lgd_code (int PK).
"""

from app.cache import CacheTTL, cached
from app.repositories.base import BaseRepository
from app.schemas.metric import AggregatedMetric, MetricPoint


class MetricRepository(BaseRepository):
    """Repository for metric data access."""

    async def get_by_cdk_and_variables(
        self,
        cdk: str,
        variables: list[str]
    ) -> list[MetricPoint]:
        """Get time series for a district and set of variables."""
        query = """
            SELECT district_lgd::text as cdk, year, variable_name, value
            FROM agri_metrics
            WHERE district_lgd::text = $1 AND variable_name = ANY($2)
            ORDER BY year ASC
        """
        rows = await self.fetch_all(query, cdk, variables)

        return [
            MetricPoint(
                cdk=r["cdk"],
                year=r["year"],
                variable=r["variable_name"],
                value=float(r["value"]) if r["value"] else 0,
                source="ICRISAT",
            )
            for r in rows
        ]

    async def get_by_cdks_and_variables(
        self,
        cdks: list[str],
        variables: list[str]
    ) -> list[MetricPoint]:
        """Get metrics for multiple districts and variables."""
        # Convert text CDKs to int array for efficient query
        int_cdks = []
        for c in cdks:
            try:
                int_cdks.append(int(c))
            except (ValueError, TypeError):
                continue

        if not int_cdks:
            return []

        query = """
            SELECT district_lgd::text as cdk, year, variable_name, value
            FROM agri_metrics
            WHERE district_lgd = ANY($1::int[]) AND variable_name = ANY($2)
            ORDER BY year ASC
        """
        rows = await self.fetch_all(query, int_cdks, variables)

        return [
            MetricPoint(
                cdk=r["cdk"],
                year=r["year"],
                variable=r["variable_name"],
                value=float(r["value"]) if r["value"] else 0,
                source="ICRISAT",
            )
            for r in rows
        ]

    @cached(ttl=CacheTTL.METRICS, prefix="metrics:year")
    async def get_by_year_and_variable(
        self,
        year: int,
        variable: str
    ) -> list[AggregatedMetric]:
        """Get all district values for a given year and variable.

        Includes split-lineage fallback: if a child district has data but
        no GeoJSON polygon, its value is mapped to the parent's polygon.
        """
        query = """
            SELECT m.district_lgd::text as cdk, d.state_name, d.district_name, m.value
            FROM agri_metrics m
            JOIN districts d ON m.district_lgd = d.lgd_code
            WHERE m.year = $1 AND m.variable_name = $2
            AND d.district_name != 'State Average'
        """
        rows = await self.fetch_all(query, year, variable)

        # Extract crop name for fallback logic
        base_parts = variable.split("_")
        crop_name = base_parts[0] if len(base_parts) >= 2 else ""

        # Fallback: If no data found, try seasonal crop
        if not rows:
            season_map = {
                "rice": "kharif",
                "wheat": "rabi",
                "maize": "kharif",
                "soyabean": "kharif",
                "groundnut": "kharif",
                "cotton": "kharif",
                "pearl_millet": "kharif",
                "sorghum": "kharif",
                "chickpea": "rabi"}
            season = season_map.get(crop_name)

            if season:
                seasonal_variable = f"{variable}_{season}"
                rows = await self.fetch_all(query, year, seasonal_variable)

        # Rice additive fallback: Merge other seasons for districts missing
        # from primary
        if crop_name == "rice" and rows:
            existing_cdks = set(r["cdk"] for r in rows)

            additional_seasons = ["winter", "autumn", "summer"]
            for s in additional_seasons:
                s_var = f"{variable}_{s}"
                s_rows = await self.fetch_all(query, year, s_var)

                for sr in s_rows:
                    if sr["cdk"] not in existing_cdks:
                        rows.append(sr)
                        existing_cdks.add(sr["cdk"])

        # Resolve geo_keys using MappingService
        from app.services.mapping_service import get_mapping_service
        mapping_service = get_mapping_service()

        # Build results with geo_key resolution
        results = []
        unmapped = []  # Track items needing split-lineage fallback

        for r in rows:
            geo_key = mapping_service.resolve_geo_key(
                r["cdk"], r["district_name"], r["state_name"]
            )
            metric = AggregatedMetric(
                cdk=r["cdk"],
                state=r["state_name"] or "",
                district=r["district_name"] or "",
                value=float(r["value"]) if r["value"] is not None else 0.0,
                metric=variable.split("_")[-1],
                method="Raw",
                feature_id=geo_key,
                geo_key=geo_key,
            )
            if geo_key:
                results.append(metric)
            else:
                unmapped.append(metric)

        # Split-lineage fallback: map child data to parent's polygon
        if unmapped:
            child_lgds = [int(m.cdk) for m in unmapped if m.cdk.isdigit()]
            if child_lgds:
                lineage_query = """
                    SELECT ds.child_lgd, ds.parent_lgd, pd.district_name, pd.state_name
                    FROM district_splits ds
                    JOIN districts pd ON pd.lgd_code = ds.parent_lgd
                    WHERE ds.child_lgd = ANY($1::int[])
                """
                lineage_rows = await self.fetch_all(lineage_query, child_lgds)
                parent_map = {
                    r["child_lgd"]: (r["parent_lgd"], r["district_name"], r["state_name"])
                    for r in lineage_rows
                }

                for m in unmapped:
                    child_lgd = int(m.cdk) if m.cdk.isdigit() else None
                    if child_lgd and child_lgd in parent_map:
                        p_lgd, p_dist, p_state = parent_map[child_lgd]
                        geo_key = mapping_service.resolve_geo_key(
                            str(p_lgd), p_dist, p_state
                        )
                        if geo_key:
                            m.feature_id = geo_key
                            m.geo_key = geo_key
                            m.method = "SplitInherited"
                    results.append(m)

        return results

    @cached(ttl=CacheTTL.METRICS, prefix="metrics:ts")
    async def get_time_series_pivoted(
        self,
        cdk: str,
        crop: str
    ) -> list[dict]:
        """Get pivoted time series {year, area, production, yield} for a crop."""
        variables = [f"{crop}_area", f"{crop}_production", f"{crop}_yield"]
        query = """
            SELECT year, variable_name, value
            FROM agri_metrics
            WHERE district_lgd::text = $1 AND variable_name = ANY($2)
            ORDER BY year ASC
        """
        rows = await self.fetch_all(query, cdk, variables)

        # Fallback: If no data found, try seasonal crop
        if not rows:
            season_map = {
                "rice": "kharif",
                "wheat": "rabi",
                "maize": "kharif",
                "soyabean": "kharif",
                "groundnut": "kharif",
                "cotton": "kharif",
                "pearl_millet": "kharif",
                "sorghum": "kharif",
            }
            season = season_map.get(crop.lower())
            if season:
                variables = [
                    f"{crop}_area_{season}",
                    f"{crop}_production_{season}",
                    f"{crop}_yield_{season}"]
                rows = await self.fetch_all(query, cdk, variables)

            # Extended Fallback for Rice Time Series
            if not rows and crop.lower() == "rice":
                for s in ["winter", "autumn", "summer"]:
                    if not rows:
                        s_vars = [
                            f"{crop}_area_{s}",
                            f"{crop}_production_{s}",
                            f"{crop}_yield_{s}"]
                        rows = await self.fetch_all(query, cdk, s_vars)
                    else:
                        break

        # Pivot data
        timeline: dict[int, dict] = {}
        for r in rows:
            year = r["year"]
            if year not in timeline:
                timeline[year] = {"year": year}

            var_name = r["variable_name"]
            if var_name.endswith("_area") or "_area_" in var_name:
                timeline[year]["area"] = float(r["value"]) if r["value"] else 0
            elif var_name.endswith("_production") or "_production_" in var_name:
                timeline[year]["production"] = float(
                    r["value"]) if r["value"] else 0
            elif var_name.endswith("_yield") or "_yield_" in var_name:
                timeline[year]["yield"] = float(
                    r["value"]) if r["value"] else 0

        # Post-process: Calculate yield if missing
        for _year, data in timeline.items():
            if "yield" not in data or data["yield"] == 0:
                area = data.get("area", 0) or 0
                prod = data.get("production", 0) or 0
                if area > 0:
                    data["yield"] = round((prod / area) * 1000, 2)

            # Ensure none is 0 instead of None for chart safety
            if "yield" not in data:
                data["yield"] = 0
            if "area" not in data:
                data["area"] = 0
            if "production" not in data:
                data["production"] = 0

        return list(timeline.values())

    @cached(ttl=CacheTTL.SUMMARY, prefix="metrics:map")
    async def build_data_map(
        self,
        cdks: list[str],
        variables: list[str]
    ) -> dict[int, dict[str, dict[str, float]]]:
        """
        Build nested map: year -> cdk -> {area, prod, yld}
        Used for boundary reconstruction calculations.
        """
        metrics = await self.get_by_cdks_and_variables(cdks, variables)

        data_map: dict[int, dict[str, dict[str, float]]] = {}

        for m in metrics:
            year = m.year
            cdk = m.cdk

            if year not in data_map:
                data_map[year] = {}
            if cdk not in data_map[year]:
                data_map[year][cdk] = {"area": 0, "prod": 0, "yld": 0}

            if "_area" in m.variable:
                data_map[year][cdk]["area"] = m.value
            elif "_production" in m.variable:
                data_map[year][cdk]["prod"] = m.value
            elif "_yield" in m.variable:
                data_map[year][cdk]["yld"] = m.value

        return data_map

    @cached(ttl=CacheTTL.METRICS, prefix="metrics:state_agg")
    async def get_state_time_series_aggregated(self, state: str, crop: str) -> list[dict]:
        """Aggregate district data up to state level if pre-aggregated data is missing."""
        variables = [f"{crop}_area", f"{crop}_production", f"{crop}_yield"]

        query = """
            SELECT m.year, m.variable_name, SUM(m.value) as value
            FROM agri_metrics m
            JOIN districts d ON m.district_lgd = d.lgd_code
            WHERE d.state_name ILIKE $1
            AND m.variable_name = ANY($2)
            AND d.district_name != 'State Average'
            GROUP BY m.year, m.variable_name
            ORDER BY m.year ASC
        """
        rows = await self.fetch_all(query, f"%{state}%", variables)

        if not rows:
            season_map = {
                "rice": "kharif",
                "wheat": "rabi",
                "maize": "kharif",
                "soyabean": "kharif",
                "groundnut": "kharif",
                "cotton": "kharif",
                "pearl_millet": "kharif",
                "sorghum": "kharif",
            }
            season = season_map.get(crop.lower())
            if season:
                variables = [
                    f"{crop}_area_{season}",
                    f"{crop}_production_{season}",
                    f"{crop}_yield_{season}"]
                rows = await self.fetch_all(query, f"%{state}%", variables)

            if not rows and crop.lower() == "rice":
                for s in ["winter", "autumn", "summer"]:
                    if not rows:
                        s_vars = [
                            f"{crop}_area_{s}",
                            f"{crop}_production_{s}",
                            f"{crop}_yield_{s}"]
                        rows = await self.fetch_all(query, f"%{state}%", s_vars)
                    else:
                        break

        timeline: dict[int, dict] = {}
        for r in rows:
            year = r["year"]
            if year not in timeline:
                timeline[year] = {
                    "year": year,
                    "area": 0,
                    "production": 0,
                    "yield": 0}

            var_name = r["variable_name"]
            val = float(r["value"]) if r["value"] else 0
            if var_name.endswith("_area") or "_area_" in var_name:
                timeline[year]["area"] = val
            elif var_name.endswith("_production") or "_production_" in var_name:
                timeline[year]["production"] = val

        for _year, data in timeline.items():
            area = data.get("area", 0)
            prod = data.get("production", 0)
            if area > 0:
                data["yield"] = round((prod / area) * 1000, 2)

        return list(timeline.values())
