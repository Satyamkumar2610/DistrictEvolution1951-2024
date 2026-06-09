"""
Metric Repository: Data access for agricultural/domain metrics.
Uses cdk (int FK) joined to districts.cdk (int PK).
"""

from app.cache import CacheTTL, cached
from app.repositories.base import BaseRepository
from app.schemas.metric import AggregatedMetric, MetricPoint


class MetricRepository(BaseRepository):
    """Repository for metric data access."""

    async def get_by_cdk_and_variables(self, cdk: str, variables: list[str]) -> list[MetricPoint]:
        """Get time series for a district and set of variables."""
        query = """
            SELECT cdk::text as cdk, year, variable_name, value
            FROM agri_metrics
            WHERE cdk::text = $1 AND variable_name = ANY($2)
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

    async def get_by_cdks_and_variables(self, cdks: list[str], variables: list[str]) -> list[MetricPoint]:
        """Get metrics for multiple districts and variables."""
        if not cdks:
            return []

        # Use text array for CDKs to natively support string-based schemas via db_compat.py
        str_cdks = [str(c) for c in cdks]

        query = """
            SELECT cdk::text as cdk, year, variable_name, value
            FROM agri_metrics
            WHERE cdk::text = ANY($1::text[]) AND variable_name = ANY($2)
            ORDER BY year ASC
        """
        rows = await self.fetch_all(query, str_cdks, variables)

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


    @cached(ttl=CacheTTL.METRICS, prefix="metrics:year_v2")
    async def get_by_year_and_variable(self, year: int, variable: str, mode: str = "historical") -> list[AggregatedMetric]:
        """Get all district values for a given year and variable.

        Modes:
        - historical: Returns data mapped to 1966 boundary system (bottom-up aggregation of modern data).
        - modern: Returns data for the current district system.
        """
        # 1. First fetch raw data
        query = """
            SELECT m.cdk as cdk, d.state_name, d.district_name, m.value
            FROM agri_metrics m
            JOIN districts d ON m.cdk = d.cdk
            WHERE m.year = $1 AND m.variable_name = $2
            AND d.district_name != 'State Average'
        """
        _rows = await self.fetch_all(query, year, variable)
        rows = [dict(r) for r in _rows]

        base_parts = variable.split("_")
        crop_name = base_parts[0] if len(base_parts) >= 2 else ""

        existing_cdks = {r["cdk"] for r in rows}

        # Fallback: check seasonal crop for missing districts
        season_map = {
            "rice": "kharif", "wheat": "rabi", "maize": "kharif", "soyabean": "kharif",
            "groundnut": "kharif", "cotton": "kharif", "pearl_millet": "kharif",
            "sorghum": "kharif", "chickpea": "rabi",
        }
        season = season_map.get(crop_name)
        if season:
            seasonal_variable = f"{variable}_{season}"
            season_rows = await self.fetch_all(query, year, seasonal_variable)
            for sr in season_rows:
                if sr["cdk"] not in existing_cdks:
                    rows.append(dict(sr))
                    existing_cdks.add(sr["cdk"])

        # Rice additive fallback
        if crop_name == "rice":
            additional_seasons = ["winter", "autumn", "summer"]
            for s in additional_seasons:
                s_var = f"{variable}_{s}"
                s_rows = await self.fetch_all(query, year, s_var)
                for sr in s_rows:
                    if sr["cdk"] not in existing_cdks:
                        rows.append(dict(sr))
                        existing_cdks.add(sr["cdk"])

        # Bottom-Up Aggregation for Historical Mode
        if mode == "historical" and year >= 1990:
            # We must roll up modern children to their parents.
            # We fetch all lineage to build a child -> parent map
            lineage_query = """
                SELECT c.cdk as child, p.cdk as parent, p.district_name, p.state_name
                FROM district_splits ds
                JOIN districts c ON LOWER(c.district_name) = LOWER(ds.child_district) AND LOWER(c.state_name) = LOWER(ds.state_name)
                JOIN districts p ON LOWER(p.district_name) = LOWER(ds.parent_district) AND LOWER(p.state_name) = LOWER(ds.state_name)
            """
            l_rows = await self.fetch_all(lineage_query)
            child_to_parent = {r["child"]: {"cdk": r["parent"], "name": r["district_name"], "state": r["state_name"]} for r in l_rows}

            # If variable is yield, we can't just sum it. But wait, we haven't done Yield Fallback yet!
            # So if it's yield, it's missing organically from DB, and will be handled by the next block!
            # If it IS organically in DB (unlikely, but possible), we shouldn't sum it.
            if "_yield" not in variable:
                agg_map = {}
                for r in rows:
                    c = r["cdk"]
                    if c in child_to_parent:
                        p = child_to_parent[c]
                        p_cdk = p["cdk"]
                        if p_cdk not in agg_map:
                            agg_map[p_cdk] = {"cdk": p_cdk, "district_name": p["name"], "state_name": p["state"], "value": 0.0}
                        agg_map[p_cdk]["value"] += (float(r["value"]) if r["value"] is not None else 0.0)
                    else:
                        agg_map[c] = r
                rows = list(agg_map.values())
                existing_cdks = {r["cdk"] for r in rows}

        # Yield Fallback: Compute yield if missing organically from DB
        if "_yield" in variable:
            area_var = variable.replace("_yield", "_area")
            prod_var = variable.replace("_yield", "_production")

            # Re-use get_by_year_and_variable recursively to get aggregated area and production!
            ap_rows_area = await self.get_by_year_and_variable(year, area_var, mode)
            ap_rows_prod = await self.get_by_year_and_variable(year, prod_var, mode)

            # Combine them
            cdk_map = {}
            for r in ap_rows_area:
                cdk_map[r.cdk] = {"state_name": r.state, "district_name": r.district, "area": r.value, "prod": 0.0}
            for r in ap_rows_prod:
                if r.cdk in cdk_map:
                    cdk_map[r.cdk]["prod"] = r.value
                else:
                    cdk_map[r.cdk] = {"state_name": r.state, "district_name": r.district, "area": 0.0, "prod": r.value}

            for cdk, data in cdk_map.items():
                if data["area"] > 0:
                    yield_val = round((data["prod"] / data["area"]) * 1000, 2)
                    rows.append(
                        {
                            "cdk": cdk,
                            "state_name": data["state_name"],
                            "district_name": data["district_name"],
                            "value": yield_val,
                        }
                    )
                    existing_cdks.add(cdk)

        # Resolve geo_keys using MappingService
        from app.services.mapping_service import get_mapping_service
        mapping_service = get_mapping_service()

        results = []
        unmapped = []
        for r in rows:
            geo_key = mapping_service.resolve_geo_key(r["cdk"], r["district_name"], r["state_name"])
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

        # We preserve the unmapped items in the results for now without faking their geo_key.
        results.extend(unmapped)

        return results


    @cached(ttl=CacheTTL.METRICS, prefix="metrics:ts")
    async def get_time_series_pivoted(self, cdk: str, crop: str) -> list[dict]:
        """Get pivoted time series {year, area, production, yield} for a crop."""
        variables = [f"{crop}_area", f"{crop}_production", f"{crop}_yield"]
        query = """
            SELECT year, variable_name, value
            FROM agri_metrics
            WHERE cdk::text = $1 AND variable_name = ANY($2)
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
                variables = [f"{crop}_area_{season}", f"{crop}_production_{season}", f"{crop}_yield_{season}"]
                rows = await self.fetch_all(query, cdk, variables)

            # Extended Fallback for Rice Time Series
            if not rows and crop.lower() == "rice":
                for s in ["winter", "autumn", "summer"]:
                    if not rows:
                        s_vars = [f"{crop}_area_{s}", f"{crop}_production_{s}", f"{crop}_yield_{s}"]
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
                timeline[year]["production"] = float(r["value"]) if r["value"] else 0
            elif var_name.endswith("_yield") or "_yield_" in var_name:
                timeline[year]["yield"] = float(r["value"]) if r["value"] else 0

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
    async def build_data_map(self, cdks: list[str], variables: list[str]) -> dict[int, dict[str, dict[str, float]]]:
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
            JOIN districts d ON m.cdk = d.cdk
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
                variables = [f"{crop}_area_{season}", f"{crop}_production_{season}", f"{crop}_yield_{season}"]
                rows = await self.fetch_all(query, f"%{state}%", variables)

            if not rows and crop.lower() == "rice":
                for s in ["winter", "autumn", "summer"]:
                    if not rows:
                        s_vars = [f"{crop}_area_{s}", f"{crop}_production_{s}", f"{crop}_yield_{s}"]
                        rows = await self.fetch_all(query, f"%{state}%", s_vars)
                    else:
                        break

        timeline: dict[int, dict] = {}
        for r in rows:
            year = r["year"]
            if year not in timeline:
                timeline[year] = {"year": year, "area": 0, "production": 0, "yield": 0}

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
