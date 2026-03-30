"""
State Service: Orchestrates state-level overview and listing responses.
"""

import asyncpg

from app.exceptions import NotFoundError
from app.repositories.state_repo import StateRepository
from app.schemas.district import Performer, StateCount, StateOverview, YearRange


class StateService:
    """Service for state aggregate endpoints."""

    def __init__(self, conn: asyncpg.Connection):
        self.repo = StateRepository(conn)

    async def get_overview(
        self,
        state_name: str,
        crop: str,
        year: int | None = None,
    ) -> StateOverview:
        """Build the full state overview response."""
        if not await self.repo.state_exists(state_name):
            raise NotFoundError("State", state_name)

        total_districts = await self.repo.get_total_districts(state_name)
        year_range = await self.repo.get_year_range(state_name)
        target_year = year or year_range["max_year"] or 2017

        yield_var = f"{crop}_yield"
        area_var = f"{crop}_area"
        production_var = f"{crop}_production"

        avg_yield = await self.repo.get_avg_yield(state_name, yield_var, target_year)
        top_performers = await self.repo.get_performers(
            state_name,
            yield_var,
            target_year,
            descending=True,
        )
        bottom_performers = await self.repo.get_performers(
            state_name,
            yield_var,
            target_year,
            descending=False,
        )
        totals = await self.repo.get_metric_totals(
            state_name,
            area_var,
            production_var,
            target_year,
        )
        districts_with_data = await self.repo.count_districts_with_data(
            state_name,
            yield_var,
            target_year,
        )
        available_crops = await self.repo.get_available_crops(state_name)

        return StateOverview(
            state=state_name,
            year=target_year,
            crop=crop,
            total_districts=total_districts,
            districts_with_data=districts_with_data,
            year_range=YearRange(min=year_range["min_year"], max=year_range["max_year"]),
            avg_yield=avg_yield or 0.0,
            total_area=totals["total_area"] or 0.0,
            total_production=totals["total_production"] or 0.0,
            top_performers=[
                Performer(
                    district_name=str(row["district_name"]),
                    cdk=str(row["cdk"]),
                    yield_value=float(row["yield_value"]),
                )
                for row in top_performers
            ],
            bottom_performers=[
                Performer(
                    district_name=str(row["district_name"]),
                    cdk=str(row["cdk"]),
                    yield_value=float(row["yield_value"]),
                )
                for row in bottom_performers
            ],
            available_crops=available_crops,
        )

    async def list_states(self) -> list[StateCount]:
        """Return all states with district counts."""
        rows = await self.repo.list_state_counts()
        return [
            StateCount(
                state=str(row["state"]),
                district_count=int(row["district_count"]),
            )
            for row in rows
        ]
