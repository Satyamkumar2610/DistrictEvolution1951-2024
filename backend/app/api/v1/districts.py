"""
Districts API: Endpoints for district data access.
"""

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.exceptions import NotFoundError
from app.repositories.district_repo import DistrictRepository
from app.schemas.district import District, DistrictList, StateNameList

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


@router.get("/states", response_model=StateNameList)
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


@router.get("/{cdk}/lineage")
async def get_district_lineage(
    cdk: str,
    db: asyncpg.Connection = Depends(get_db),
):
    """Get the lineage (parents and children) of a district."""
    # Find children
    children_query = """
        SELECT ds.child_district as district_name, ds.state_name, c.cdk as child_cdk
        FROM district_splits ds
        LEFT JOIN districts c ON LOWER(c.district_name) = LOWER(ds.child_district) AND LOWER(c.state_name) = LOWER(ds.state_name)
        JOIN districts p ON LOWER(p.district_name) = LOWER(ds.parent_district) AND LOWER(p.state_name) = LOWER(ds.state_name)
        WHERE p.cdk = $1
    """
    children = await db.fetch(children_query, cdk)

    # Find parents
    parents_query = """
        SELECT ds.parent_district as district_name, ds.state_name, p.cdk as parent_cdk
        FROM district_splits ds
        LEFT JOIN districts p ON LOWER(p.district_name) = LOWER(ds.parent_district) AND LOWER(p.state_name) = LOWER(ds.state_name)
        JOIN districts c ON LOWER(c.district_name) = LOWER(ds.child_district) AND LOWER(c.state_name) = LOWER(ds.state_name)
        WHERE c.cdk = $1
    """
    parents = await db.fetch(parents_query, cdk)

    return {
        "cdk": cdk,
        "parents": [dict(p) for p in parents],
        "children": [dict(c) for c in children]
    }
