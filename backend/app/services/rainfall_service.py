"""
IMD Rainfall Data Service.
Reads district-level rainfall normals from database (populated via ETL).
"""

from dataclasses import dataclass
from typing import Any

import asyncpg


@dataclass
class RainfallData:
    """District rainfall normals."""

    state: str
    district: str
    jan: float
    feb: float
    mar: float
    apr: float
    may: float
    jun: float
    jul: float
    aug: float
    sep: float
    oct: float
    nov: float
    dec: float
    annual: float
    monsoon_jjas: float  # Jun-Sep monsoon
    winter_jf: float  # Jan-Feb
    pre_monsoon_mam: float  # Mar-May
    post_monsoon_ond: float  # Oct-Dec


STATE_MAPPING = {
    "CHHATTISGARH": "CHATISGARH",
    "ODISHA": "ORISSA",
    "UTTARAKHAND": "UTTARANCHAL",
    "HIMACHAL PRADESH": "HIMACHAL",
    "PUDUCHERRY": "PONDICHERRY",
    "ANDAMAN & NICOBAR ISLANDS": "ANDAMAN And NICOBAR ISLANDS",
    "DADRA & NAGAR HAVELI": "DADAR NAGAR HAVELI",
    "DAMAN & DIU": "DAMAN AND DUI",
}


def normalize_state(state: str) -> str:
    """Normalize state name to match rainfall_normals database conventions."""
    if not state:
        return state

    upper_state = state.upper()
    return STATE_MAPPING.get(upper_state, upper_state)


async def get_rainfall_by_district(db: asyncpg.Connection, state: str, district: str) -> RainfallData | None:
    """
    Get rainfall data for a specific district from database.
    """
    db_state = normalize_state(state)

    row = await db.fetchrow(
        """
        SELECT state_ut, district, jan, feb, mar, apr, may, jun, jul, aug, sep, oct, nov, dec_month,
               annual, jjas, mam, ond, jan_feb
        FROM rainfall_normals
        WHERE UPPER(state_ut) = $1 AND UPPER(district) = UPPER($2)
    """,
        db_state,
        district,
    )

    if not row:
        return None

    return RainfallData(
        state=row["state_ut"],
        district=row["district"],
        jan=float(row["jan"] or 0),
        feb=float(row["feb"] or 0),
        mar=float(row["mar"] or 0),
        apr=float(row["apr"] or 0),
        may=float(row["may"] or 0),
        jun=float(row["jun"] or 0),
        jul=float(row["jul"] or 0),
        aug=float(row["aug"] or 0),
        sep=float(row["sep"] or 0),
        oct=float(row["oct"] or 0),
        nov=float(row["nov"] or 0),
        dec=float(row["dec_month"] or 0),
        annual=float(row["annual"] or 0),
        monsoon_jjas=float(row["jjas"] or 0),
        winter_jf=float(row["jan_feb"] or 0),
        pre_monsoon_mam=float(row["mam"] or 0),
        post_monsoon_ond=float(row["ond"] or 0),
    )


async def get_all_rainfall(db: asyncpg.Connection, state: str | None = None) -> list[dict[str, Any]]:
    """
    Get all rainfall data (optionally filtered by state) from database.
    Returns simplified format for map visualization.
    """
    if state:
        db_state = normalize_state(state)
        rows = await db.fetch(
            """
            SELECT state_ut, district, annual, jjas as monsoon
            FROM rainfall_normals
            WHERE UPPER(state_ut) = $1
            ORDER BY district
        """,
            db_state,
        )
    else:
        rows = await db.fetch("""
            SELECT state_ut, district, annual, jjas as monsoon
            FROM rainfall_normals
            ORDER BY state_ut, district
        """)

    return [
        {
            "state": row["state_ut"],
            "district": row["district"],
            "annual": float(row["annual"] or 0),
            "monsoon": float(row["monsoon"] or 0),
        }
        for row in rows
    ]


async def get_state_rainfall_stats(db: asyncpg.Connection, state: str) -> dict[str, Any]:
    """
    Get aggregated rainfall statistics for a state.
    """
    db_state = normalize_state(state)

    row = await db.fetchrow(
        """
        SELECT
            COUNT(*) as district_count,
            AVG(annual) as avg_annual,
            MIN(annual) as min_annual,
            MAX(annual) as max_annual,
            AVG(jjas) as avg_monsoon
        FROM rainfall_normals
        WHERE UPPER(state_ut) = $1
    """,
        db_state,
    )

    if not row or row["district_count"] == 0:
        return {"error": f"No data for state: {state}"}

    return {
        "state": state,
        "district_count": row["district_count"],
        "avg_annual_mm": round(float(row["avg_annual"] or 0), 2),  # type: ignore
        "min_annual_mm": round(float(row["min_annual"] or 0), 2),  # type: ignore
        "max_annual_mm": round(float(row["max_annual"] or 0), 2),  # type: ignore
        "avg_monsoon_mm": round(float(row["avg_monsoon"] or 0), 2),  # type: ignore
    }


async def get_rainfall_count(db: asyncpg.Connection) -> int:
    """Get total number of rainfall records in database."""
    return await db.fetchval("SELECT COUNT(*) FROM rainfall_normals")


async def get_water_stress_index(db: asyncpg.Connection, state: str, year: int) -> list[dict[str, Any]]:
    """
    Compute a Water Stress / Mismatch Index for districts in a state.
    Matches the area of water-intensive crops (Rice, Sugarcane, Cotton)
    against the district's annual historical rainfall.
    """
    # 1. Get area for water intensive crops vs total area
    query = """
        SELECT
            d.district_name,
            d.lgd_code,
            SUM(CASE WHEN m.variable_name LIKE 'rice_area%' AND m.variable_name NOT LIKE '%_kharif%' AND m.variable_name NOT LIKE '%_rabi%' THEN m.value ELSE 0 END) as rice_area,
            SUM(CASE WHEN m.variable_name LIKE 'sugarcane_area%' AND m.variable_name NOT LIKE '%_kharif%' AND m.variable_name NOT LIKE '%_rabi%' THEN m.value ELSE 0 END) as sugarcane_area,
            SUM(CASE WHEN m.variable_name LIKE 'cotton_area%' AND m.variable_name NOT LIKE '%_kharif%' AND m.variable_name NOT LIKE '%_rabi%' THEN m.value ELSE 0 END) as cotton_area,
            SUM(CASE WHEN m.variable_name LIKE '%_area%' AND m.variable_name NOT LIKE '%_kharif%' AND m.variable_name NOT LIKE '%_rabi%' THEN m.value ELSE 0 END) as total_area
        FROM districts d
        JOIN agri_metrics m ON d.lgd_code = m.district_lgd
        WHERE d.state_name = $1 AND m.year = $2
        GROUP BY d.district_name, d.lgd_code
    """
    rows = await db.fetch(query, state, year)

    results = []
    for row in rows:
        district_name = row["district_name"]
        total_area = float(row["total_area"] or 0)

        if total_area == 0:
            continue

        rice_area = float(row["rice_area"] or 0)
        sugarcane_area = float(row["sugarcane_area"] or 0)
        cotton_area = float(row["cotton_area"] or 0)

        water_intensive_area = rice_area + sugarcane_area + cotton_area
        water_intensive_share = water_intensive_area / total_area

        if water_intensive_area == 0:
            continue

        # 2. Get rainfall data
        rainfall = await get_rainfall_by_district(db, state, district_name)
        if not rainfall:
            continue

        annual_rain = rainfall.annual

        # 3. Compute Mismatch Score (0-100)
        # High share (>50%) + Low Rain (< 1000mm) = High Stress
        normalized_share = min(1.0, water_intensive_share / 0.5)  # Maxes at 50% share
        # Deficit factor (1 at 0mm, 0 at >=1500mm)
        normalized_deficit = max(0.0, 1.0 - (annual_rain / 1500))

        mismatch_score = round(normalized_share * normalized_deficit * 100, 1)  # type: ignore

        if mismatch_score > 60:
            category = "Critical"
        elif mismatch_score > 40:
            category = "High"
        elif mismatch_score > 20:
            category = "Moderate"
        else:
            category = "Low"

        results.append(
            {
                "district_name": district_name,
                "cdk": str(row["lgd_code"]),
                "total_area": round(total_area, 2),  # type: ignore
                "water_intensive_area": round(water_intensive_area, 2),  # type: ignore
                "water_intensive_share": round(water_intensive_share * 100, 1),  # type: ignore
                "annual_rainfall": round(annual_rain, 1),  # type: ignore
                "mismatch_score": mismatch_score,
                "category": category,
                "crop_breakdown": {
                    "rice": round(rice_area, 2),  # type: ignore
                    "sugarcane": round(sugarcane_area, 2),  # type: ignore
                    "cotton": round(cotton_area, 2),  # type: ignore
                },
            }
        )

    # Sort by mismatch score descending
    results.sort(key=lambda x: x["mismatch_score"], reverse=True)
    return results
