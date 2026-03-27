"""
States API: Aggregate state-level endpoints.
Provides overview statistics for each state.
"""
import asyncpg
from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.exceptions import NotFoundError

router = APIRouter(prefix="/states", tags=["States"])


@router.get("/{state_name}/overview")
async def get_state_overview(
    state_name: str,
    crop: str = Query("wheat", description="Crop to analyze"),
    year: int = Query(None, description="Year (defaults to latest)"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get aggregate overview for a state.

    Returns total districts, data coverage, avg yield,
    top/bottom performers, and year range.
    """
    # Verify state exists
    state_check = await db.fetchval(
        "SELECT COUNT(*) FROM districts WHERE state_name = $1", state_name
    )
    if not state_check:
        raise NotFoundError("State", state_name)

    # Get total districts
    total_districts = await db.fetchval(
        "SELECT COUNT(*) FROM districts WHERE state_name = $1", state_name
    )

    # Get year range
    year_range = await db.fetchrow("""
        SELECT MIN(m.year) as min_year, MAX(m.year) as max_year
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE d.state_name = $1
    """, state_name)

    # Use latest year if not specified
    target_year = year or (year_range["max_year"] if year_range else 2017)

    # Get yield variable
    yield_var = f"{crop}_yield"
    area_var = f"{crop}_area"
    prod_var = f"{crop}_production"

    # Get avg yield for the state
    avg_yield = await db.fetchval("""
        SELECT ROUND(AVG(m.value)::numeric, 2)
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE d.state_name = $1 AND m.variable_name = $2 AND m.year = $3 AND m.value > 0
    """, state_name, yield_var, target_year)

    # Get top 5 performers
    top_performers = await db.fetch("""
        SELECT d.district_name, d.lgd_code::text as cdk, ROUND(m.value::numeric, 2) as yield_value
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE d.state_name = $1 AND m.variable_name = $2 AND m.year = $3 AND m.value > 0
        ORDER BY m.value DESC
        LIMIT 5
    """, state_name, yield_var, target_year)

    # Get bottom 5 performers
    bottom_performers = await db.fetch("""
        SELECT d.district_name, d.lgd_code::text as cdk, ROUND(m.value::numeric, 2) as yield_value
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE d.state_name = $1 AND m.variable_name = $2 AND m.year = $3 AND m.value > 0
        ORDER BY m.value ASC
        LIMIT 5
    """, state_name, yield_var, target_year)

    # Get total area and production
    totals = await db.fetchrow("""
        SELECT
            ROUND(SUM(CASE WHEN m.variable_name = $2 THEN m.value END)::numeric, 2) as total_area,
            ROUND(SUM(CASE WHEN m.variable_name = $3 THEN m.value END)::numeric, 2) as total_production
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE d.state_name = $1 AND m.year = $4 AND m.value > 0
    """, state_name, area_var, prod_var, target_year)

    # Count districts with data for this crop+year
    districts_with_data = await db.fetchval("""
        SELECT COUNT(DISTINCT d.lgd_code)
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE d.state_name = $1 AND m.variable_name = $2 AND m.year = $3 AND m.value > 0
    """, state_name, yield_var, target_year)

    # Get available crops for this state
    available_crops = await db.fetch("""
        SELECT DISTINCT REPLACE(m.variable_name, '_yield', '') as crop_name
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE d.state_name = $1 AND m.variable_name LIKE '%_yield' AND m.value > 0
        ORDER BY crop_name
    """, state_name)

    return {
        "state": state_name,
        "year": target_year,
        "crop": crop,
        "total_districts": total_districts,
        "districts_with_data": districts_with_data,
        "year_range": {
            "min": year_range["min_year"] if year_range else None,
            "max": year_range["max_year"] if year_range else None,
        },
        "avg_yield": float(avg_yield) if avg_yield else 0,
        "total_area": float(
            totals["total_area"]) if totals and totals["total_area"] else 0,
        "total_production": float(
                totals["total_production"]) if totals and totals["total_production"] else 0,
        "top_performers": [
                    dict(r) for r in top_performers],
        "bottom_performers": [
            dict(r) for r in bottom_performers],
        "available_crops": [
            r["crop_name"] for r in available_crops],
    }


@router.get("/list")
async def list_states(db: asyncpg.Connection = Depends(get_db)):
    """
    List all states with district counts.
    """
    rows = await db.fetch("""
        SELECT state_name, COUNT(*) as district_count
        FROM districts
        GROUP BY state_name
        ORDER BY state_name
    """)
    return [{"state": r["state_name"], "district_count": r["district_count"]}
            for r in rows]
