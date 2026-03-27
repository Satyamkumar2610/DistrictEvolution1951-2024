"""
Reports API: Generate downloadable reports combining multiple analytics.
"""
import asyncpg
from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.exceptions import NotFoundError
from app.export import get_exporter

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/district-profile")
async def get_district_profile_report(
    cdk: str = Query(..., description="District LGD code"),
    crop: str = Query("wheat", description="Crop to analyze"),
    format: str = Query("json", description="Output format: json or csv"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Generate a comprehensive district profile report.

    Combines metrics, risk profile, efficiency, and forecast data
    into a single downloadable report.
    """
    # Verify district
    district = await db.fetchrow("""
        SELECT lgd_code::text as cdk, district_name, state_name
        FROM districts WHERE lgd_code::text = $1
    """, cdk)

    if not district:
        raise NotFoundError("District", cdk)

    district_name = district["district_name"]
    state_name = district["state_name"]

    # Get yield data history
    yield_var = f"{crop}_yield"
    area_var = f"{crop}_area"
    prod_var = f"{crop}_production"

    yield_history = await db.fetch("""
        SELECT year, variable_name, value
        FROM agri_metrics
        WHERE district_lgd::text = $1
        AND variable_name IN ($2, $3, $4)
        AND value > 0
        ORDER BY year
    """, cdk, yield_var, area_var, prod_var)

    # Organize by year
    yearly_data = {}
    for row in yield_history:
        year = row["year"]
        if year not in yearly_data:
            yearly_data[year] = {"year": year}
        var_short = row["variable_name"].replace(f"{crop}_", "")
        yearly_data[year][var_short] = float(row["value"])

    years_list = sorted(yearly_data.values(), key=lambda x: x["year"])

    # Basic statistics
    yields = [y.get("yield", 0) for y in years_list if y.get("yield", 0) > 0]
    areas = [y.get("area", 0) for y in years_list if y.get("area", 0) > 0]

    stats = {}
    if yields:
        stats = {
            "mean_yield": round(sum(yields) / len(yields), 2),
            "max_yield": round(max(yields), 2),
            "min_yield": round(min(yields), 2),
            "years_with_data": len(yields),
            "first_year": years_list[0]["year"] if years_list else None,
            "last_year": years_list[-1]["year"] if years_list else None,
        }
        if len(yields) > 1:
            mean = stats["mean_yield"]
            variance = sum((y - mean) ** 2 for y in yields) / len(yields)
            std = variance ** 0.5
            stats["std_yield"] = round(std, 2)
            stats["cv_yield"] = round((std / mean) * 100, 2) if mean > 0 else 0

    if areas:
        stats["mean_area"] = round(sum(areas) / len(areas), 2)

    # State benchmarks
    state_avg = await db.fetchval("""
        SELECT ROUND(AVG(m.value)::numeric, 2)
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE d.state_name = $1 AND m.variable_name = $2 AND m.value > 0
    """, state_name, yield_var)

    report = {
        "report_type": "district_profile",
        "district": {
            "cdk": cdk,
            "name": district_name,
            "state": state_name,
        },
        "crop": crop,
        "statistics": stats,
        "state_benchmark": {
            "avg_yield": float(state_avg) if state_avg else 0,
            "efficiency": round(stats["mean_yield"] / float(state_avg), 3)
            if state_avg and stats.get("mean_yield")
            else None,
        },
        "yearly_data": years_list,
    }

    if format == "csv":
        exporter = get_exporter("I-ASCAP Report")
        return exporter.to_csv_response(
            years_list,
            filename=f"{district_name}_{crop}_profile.csv",
        )

    return report
