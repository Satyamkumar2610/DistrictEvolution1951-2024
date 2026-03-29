"""
Lineage API: Endpoints for lineage graph and split events.
Updated to use lgd_code/district_lgd schema where applicable.
Note: lineage_events uses CDK text keys that cannot join to districts.lgd_code.
"""

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.exceptions import NotFoundError
from app.repositories.district_repo import DistrictRepository
from app.repositories.lineage_repo import LineageRepository
from app.schemas.lineage import (
    DistrictHistoryItem,
    LineageGraph,
    ProvenanceTrackingResponse,
    SplitEventSummary,
    StateCoverageResponse,
    UnmappedSplitItem,
)

router = APIRouter()


@router.get("/history", response_model=list[DistrictHistoryItem])
async def get_district_history(
    state: str | None = Query(None, description="Filter by state name"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get comprehensive district split history from detailed records (1951-2024).
    """
    query = """
        SELECT state_name, split_year, parent_district, child_district, parent_lgd::text as parent_cdk, child_lgd::text as child_cdk, source
        FROM district_splits
        WHERE ($1::text IS NULL OR UPPER(state_name) = UPPER($1))
        ORDER BY state_name, split_year
    """
    rows = await db.fetch(query, state)
    return [dict(r) for r in rows]


@router.get("/events", response_model=LineageGraph)
async def get_lineage_events(
    state: str | None = Query(None, description="Filter by state"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get lineage events (administrative boundary changes).

    Returns split/merge/rename events optionally filtered by state.
    """
    district_repo = DistrictRepository(db)
    lineage_repo = LineageRepository(db)

    if state:
        cdk_meta = await district_repo.get_cdk_to_meta_map()
        cdk_to_state = {cdk: meta["state"] for cdk, meta in cdk_meta.items()}
        events = await lineage_repo.get_events_by_state(state, cdk_to_state)
    else:
        events = await lineage_repo.get_all_events()

    return LineageGraph(total_events=len(events), events=events)


@router.get("/splits", response_model=list[SplitEventSummary])
async def get_split_events(
    state: str = Query(..., description="State name (required)"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get grouped split events for a state.

    Returns parent districts with their children, sorted by year.
    """
    from app.services.analysis_service import AnalysisService

    service = AnalysisService(db)
    return await service.get_split_events_for_state(state)


@router.get("/tracking", response_model=ProvenanceTrackingResponse)
async def get_data_tracking(
    cdk: str = Query(..., description="District LGD code (as text)"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get data lineage tracking for a district.

    Returns:
    - Data sources used
    - Year coverage
    - Related lineage events (splits/merges)
    - Data provenance chain
    """
    # Get district info
    district = await db.fetchrow("""
        SELECT lgd_code::text as cdk, district_name, state_name, start_year, end_year
        FROM districts WHERE lgd_code::text = $1
    """, cdk)

    if not district:
        raise NotFoundError("District", cdk)

    # Get data coverage
    coverage = await db.fetchrow("""
        SELECT
            COUNT(DISTINCT year) as years_with_data,
            MIN(year) as first_year,
            MAX(year) as last_year,
            COUNT(DISTINCT variable_name) as variables,
            COUNT(*) as total_records
        FROM agri_metrics WHERE district_lgd::text = $1
    """, cdk)

    # Lineage events use CDK text keys which don't match lgd_code
    # So we skip the lineage JOINs here — they'd return nothing meaningful

    return {
        "district": dict(district),
        "data_coverage": {
            "years_with_data": coverage["years_with_data"],
            "first_year": coverage["first_year"],
            "last_year": coverage["last_year"],
            "variables": coverage["variables"],
            "total_records": coverage["total_records"]},
        "data_sources": [
            {
                "source": "ICRISAT/DES",
                "record_count": coverage["total_records"],
                "from_year": coverage["first_year"],
                "to_year": coverage["last_year"]}],
        "lineage": {
            "split_into": [],
            "created_from": []}}


@router.get("/coverage", response_model=StateCoverageResponse)
async def get_state_coverage(
    state: str = Query(..., description="State name"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get data coverage summary for all districts in a state.

    Shows years with data, record counts, and lineage status per district.
    """
    coverage = await db.fetch("""
        SELECT
            d.lgd_code::text as cdk,
            d.district_name,
            d.start_year,
            d.end_year,
            COUNT(DISTINCT am.year) as years_with_data,
            COUNT(am.id) as record_count,
            'original' as lineage_status
        FROM districts d
        LEFT JOIN agri_metrics am ON d.lgd_code = am.district_lgd
        WHERE d.state_name = $1
        GROUP BY d.lgd_code, d.district_name, d.start_year, d.end_year
        ORDER BY d.district_name
    """, state)

    return {
        "state": state,
        "districts": len(coverage),
        "coverage": [dict(c) for c in coverage]
    }


@router.get("/unmapped", response_model=list[UnmappedSplitItem])
async def get_unmapped_splits(
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get all districts involved in splits that cannot be mapped to an LGD code.
    """
    from app.core.name_matching import (
        STATE_ALIASES,
        TELANGANA_DISTRICTS,
        check_historical_resolution,
        resolve_district_name,
    )

    districts = await db.fetch("SELECT lgd_code, district_name, state_name FROM districts")
    lgd_lookup = {}
    for r in districts:
        key = (
            r['district_name'].strip().lower(),
            r['state_name'].strip().lower())
        lgd_lookup[key] = r['lgd_code']

    def resolve_lgd(district_name, state_name):
        dn = resolve_district_name(district_name)
        sn = state_name.lower().strip()
        if (dn, sn) in lgd_lookup:
            return lgd_lookup[(dn, sn)]

        for alias_key, alias_states in STATE_ALIASES.items():
            if alias_key in sn:
                for alt_state in alias_states:
                    if (dn, alt_state.lower()) in lgd_lookup:
                        return lgd_lookup[(dn, alt_state.lower())]

        if dn in TELANGANA_DISTRICTS and "andhra" in sn and (dn, "telangana") in lgd_lookup:
            return lgd_lookup[(dn, "telangana")]

        return None

    splits = await db.fetch("SELECT parent_district, child_district, split_year, state_name FROM district_splits")

    unmapped = set()

    for row in splits:
        p_lgd = resolve_lgd(row['parent_district'], row['state_name'])
        if not p_lgd and not check_historical_resolution(
                row['state_name'], row['parent_district']):
            unmapped.add(
                (row['parent_district'],
                 row['state_name'],
                    row['split_year'],
                    'Parent'))

        c_lgd = resolve_lgd(row['child_district'], row['state_name'])
        if not c_lgd and not check_historical_resolution(
                row['state_name'], row['child_district']):
            unmapped.add(
                (row['child_district'],
                 row['state_name'],
                    row['split_year'],
                    'Child'))

    sorted_unmapped = sorted(list(unmapped), key=lambda x: (x[1], x[0], x[2]))

    return [
        {"district": u[0], "state": u[1], "year": u[2], "role": u[3]}
        for u in sorted_unmapped
    ]
