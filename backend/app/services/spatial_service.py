import json
from typing import Any

import asyncpg

from app.exceptions import NotFoundError, ValidationError
from app.repositories.spatial_repo import SpatialRepository
from app.schemas.spatial import (
    DistrictLineageResponse,
    GenericStatusResponse,
    SplitAreaCalculationResponse,
)
from app.services.geometry_service import GeometryService


class SpatialService:
    def __init__(self, db: asyncpg.Connection | None = None):
        self.db = db
        self.repo = SpatialRepository(db) if db is not None else None
        self.geometry_service = GeometryService()

    def _require_db(self) -> asyncpg.Connection:
        if self.db is None:
            raise RuntimeError("Database connection is required for this spatial operation")
        return self.db

    def _require_repo(self) -> SpatialRepository:
        if self.repo is None:
            raise RuntimeError("Database connection is required for this spatial operation")
        return self.repo

    async def get_neighbors(self, cdk: str) -> list[dict[str, Any]]:
        """
        Find all immediately adjacent neighboring districts using PostGIS ST_Touches.
        """
        return await self._require_repo().get_neighbors(cdk)

    async def get_cagr(self, cdk: str, crop: str, start_year: int, end_year: int) -> float:
        """
        Helper method to get CAGR of a crop yield for a district.
        """
        rows = await self._require_repo().get_crop_yield_series(cdk, crop, start_year, end_year)

        if len(rows) < 2:
            return 0.0

        start_val = float(rows[0]["value"])
        end_val = float(rows[-1]["value"])
        n_years = int(rows[-1]["year"]) - int(rows[0]["year"])

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
        repo = self._require_repo()
        if not await repo.district_exists(cdk):
            raise NotFoundError("District", cdk)

        # Get the target district's growth
        target_cagr = await self.get_cagr(cdk, crop, start_year, end_year)

        # Get target name
        target_meta = await repo.get_target_meta(cdk)
        target_name = str(target_meta["district_name"]) if target_meta else cdk

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
        regional_avg_cagr = sum(valid_cagrs) / len(valid_cagrs) if valid_cagrs else 0.0

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

    def calculate_split_areas(
        self,
        parent_content: bytes,
        child_content: bytes,
    ) -> SplitAreaCalculationResponse:
        """Calculate transferred and remaining area from uploaded GeoJSON payloads."""
        try:
            parent_dict = json.loads(parent_content.decode("utf-8"))
            child_dict = json.loads(child_content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError(detail="Invalid JSON format uploaded.") from exc

        try:
            result = self.geometry_service.calculate_split_areas(parent_dict, child_dict)
        except ValueError as exc:
            raise ValidationError(detail=str(exc)) from exc

        return SplitAreaCalculationResponse.model_validate(result)

    async def calculate_spatial_diff(self, split_event_id: int) -> GenericStatusResponse:
        """Compute and persist spatial diff results for a split event."""
        from app.analytics.harmonizer import BoundaryHarmonizer

        harmonizer = BoundaryHarmonizer()
        await harmonizer.compute_split_diff(self._require_db(), split_event_id)
        return GenericStatusResponse(
            status="success",
            message=f"Calculated split diff for event {split_event_id}",
        )

    async def get_district_lineage(self, district_id: str) -> DistrictLineageResponse:
        """Fetch split events and transfer records for a district."""
        repo = self._require_repo()
        events = await repo.get_split_events_for_district(district_id)
        transfers = await repo.get_area_transfers_for_district(district_id)
        return DistrictLineageResponse(
            district_id=district_id,
            split_events=events,
            area_transfers=transfers,
        )

    async def upload_manual_geojson(
        self,
        district_id: str,
        snapshot_year: int,
        content: bytes,
    ) -> GenericStatusResponse:
        """Parse and persist a manual GeoJSON upload for a district snapshot."""
        try:
            parsed = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError(detail="Invalid JSON format uploaded.") from exc

        if "features" in parsed and len(parsed["features"]) > 0:
            geom = parsed["features"][0].get("geometry")
        elif "geometry" in parsed:
            geom = parsed["geometry"]
        else:
            geom = parsed

        geometry_geojson = json.dumps(geom)
        repo = self._require_repo()
        district_name = await repo.get_district_name(district_id)
        await repo.upsert_manual_geojson(
            district_id=district_id,
            snapshot_year=snapshot_year,
            district_name=district_name or district_id,
            geometry_geojson=geometry_geojson,
        )

        return GenericStatusResponse(
            status="success",
            message=f"Uploaded manual GeoJSON for {district_id} ({snapshot_year})",
        )
