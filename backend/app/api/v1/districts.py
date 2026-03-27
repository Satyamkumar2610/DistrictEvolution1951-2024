"""
Districts API: Endpoints for district data access.
"""

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.exceptions import NotFoundError
from app.repositories.district_repo import DistrictRepository
from app.schemas.district import District, DistrictList

router = APIRouter()


@router.get("", response_model=DistrictList)
async def list_districts(
    state: str | None = Query(None, description="Filter by state name", max_length=50),
    search: str | None = Query(None, description="Search by district name", min_length=3, max_length=50),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    List all districts with optional filtering.

    - **state**: Filter to a specific state
    - **search**: Search districts by name (case-insensitive)
    """
    repo = DistrictRepository(db)

    if search:
        districts = await repo.search(search, state)
    else:
        districts = await repo.get_all(state)

    return DistrictList(total=len(districts), items=districts)


@router.get("/states")
async def list_states(db: asyncpg.Connection = Depends(get_db)):
    """Get list of all unique states."""
    repo = DistrictRepository(db)
    states = await repo.get_states()
    return {"states": states}


@router.get("/{cdk}", response_model=District)
async def get_district(
    cdk: str,
    db: asyncpg.Connection = Depends(get_db),
):
    """Get a single district by CDK."""
    repo = DistrictRepository(db)
    district = await repo.get_by_cdk(cdk)

    if not district:
        raise NotFoundError("District", cdk)

    return district
