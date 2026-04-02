"""
Report application service for API-facing report generation.
"""

from typing import cast

import asyncpg
from fastapi import Response

from app.exceptions import NotFoundError
from app.export import get_exporter
from app.repositories.report_repo import ReportRepository
from app.schemas.report import (
    DistrictProfileDistrict,
    DistrictProfileReportResponse,
    DistrictProfileStateBenchmark,
    DistrictProfileStatistics,
)


class ReportService:
    """Service layer for district profile reports."""

    def __init__(self, conn: asyncpg.Connection):
        self.repo = ReportRepository(conn)

    async def get_district_profile_report(
        self,
        cdk: str,
        crop: str,
        output_format: str,
    ) -> DistrictProfileReportResponse | Response:
        """Generate a district profile report in JSON or CSV form."""
        district = await self.repo.get_district_context(cdk)
        if district is None:
            raise NotFoundError("District", cdk)

        yearly_data = self._build_yearly_data(
            await self.repo.get_crop_metric_history(cdk, crop),
            crop,
        )
        stats = self._build_statistics(yearly_data)
        state_avg = await self.repo.get_state_average_yield(str(district["state_name"]), crop)
        mean_yield = stats.mean_yield

        report = DistrictProfileReportResponse(
            report_type="district_profile",
            district=DistrictProfileDistrict(
                cdk=cdk,
                name=str(district["district_name"]),
                state=str(district["state_name"]),
            ),
            crop=crop,
            statistics=stats,
            state_benchmark=DistrictProfileStateBenchmark(
                avg_yield=state_avg or 0.0,
                efficiency=(round(mean_yield / state_avg, 3) if state_avg and mean_yield is not None else None),
            ),
            yearly_data=yearly_data,
        )

        if output_format == "csv":
            exporter = get_exporter("I-ASCAP Report")
            return exporter.to_csv_response(
                yearly_data,
                filename=f"{district['district_name']}_{crop}_profile.csv",
            )

        return report

    def _build_yearly_data(
        self,
        history_rows: list[dict[str, object]],
        crop: str,
    ) -> list[dict[str, float | int]]:
        """Organize metric history into per-year report rows."""
        yearly_data: dict[int, dict[str, float | int]] = {}
        crop_prefix = f"{crop}_"

        for row in history_rows:
            year = int(cast(int | str, row["year"]))
            if year not in yearly_data:
                yearly_data[year] = {"year": year}

            variable_name = str(row["variable_name"])
            variable_key = variable_name.replace(crop_prefix, "")
            yearly_data[year][variable_key] = float(cast(float | int | str, row["value"]))

        return sorted(yearly_data.values(), key=lambda item: int(item["year"]))

    def _build_statistics(
        self,
        yearly_data: list[dict[str, float | int]],
    ) -> DistrictProfileStatistics:
        """Calculate basic summary statistics for the report."""
        yields = [float(item["yield"]) for item in yearly_data if "yield" in item and float(item["yield"]) > 0]
        areas = [float(item["area"]) for item in yearly_data if "area" in item and float(item["area"]) > 0]

        stats = DistrictProfileStatistics()
        if yields:
            mean_yield = sum(yields) / len(yields)
            stats.mean_yield = round(mean_yield, 2)
            stats.max_yield = round(max(yields), 2)
            stats.min_yield = round(min(yields), 2)
            stats.years_with_data = len(yields)
            stats.first_year = int(yearly_data[0]["year"]) if yearly_data else None
            stats.last_year = int(yearly_data[-1]["year"]) if yearly_data else None

            if len(yields) > 1:
                variance = sum((value - mean_yield) ** 2 for value in yields) / len(yields)
                std_yield = variance**0.5
                stats.std_yield = round(std_yield, 2)
                stats.cv_yield = round((std_yield / mean_yield) * 100, 2) if mean_yield > 0 else 0.0

        if areas:
            stats.mean_area = round(sum(areas) / len(areas), 2)

        return stats
