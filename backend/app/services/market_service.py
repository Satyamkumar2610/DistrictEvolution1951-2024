"""
Market Service: Mandi prices, MSP comparison, and price analytics.

Provides data from two scraped sources:
  1. Daily mandi prices (data.gov.in) → mandi_prices table
  2. MSP benchmark rates (CACP) → msp_rates table
"""

import logging
from datetime import date
from typing import Any

import asyncpg

logger = logging.getLogger("app.services.market_service")


class MarketService:
    """Service for market price endpoints."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    # ── Price Queries ─────────────────────────────────────────────

    async def get_prices(
        self,
        state: str | None = None,
        district: str | None = None,
        commodity: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get mandi prices with optional filters."""
        conditions = []
        params: list[Any] = []
        idx = 1

        if state:
            conditions.append(f"UPPER(state) = UPPER(${idx})")
            params.append(state)
            idx += 1

        if district:
            conditions.append(f"UPPER(district) = UPPER(${idx})")
            params.append(district)
            idx += 1

        if commodity:
            conditions.append(
                f"(UPPER(commodity_normalized) = UPPER(${idx}) OR UPPER(commodity) ILIKE ${idx})"
            )
            params.append(commodity)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        query = f"""
            SELECT state, district, market, commodity, commodity_normalized,
                   variety, grade, arrival_date, min_price, max_price, modal_price
            FROM mandi_prices
            {where}
            ORDER BY arrival_date DESC, modal_price DESC
            LIMIT ${idx}
        """

        rows = await self.conn.fetch(query, *params)

        return {
            "state": state,
            "district": district,
            "total": len(rows),
            "prices": [dict(row) for row in rows],
            "source": "data.gov.in (Ministry of Agriculture)",
        }

    # ── Price Trends ──────────────────────────────────────────────

    async def get_price_trends(
        self,
        state: str,
        commodity: str,
        days: int = 30,
    ) -> dict[str, Any]:
        """Get daily price trends for a commodity in a state."""
        rows = await self.conn.fetch(
            """
            SELECT arrival_date,
                   AVG(modal_price) as avg_modal,
                   MIN(min_price) as min_price,
                   MAX(max_price) as max_price,
                   COUNT(*) as record_count
            FROM mandi_prices
            WHERE UPPER(state) = UPPER($1)
              AND (UPPER(commodity_normalized) = UPPER($2) OR commodity ILIKE $2)
              AND arrival_date >= CURRENT_DATE - $3::integer
            GROUP BY arrival_date
            ORDER BY arrival_date
            """,
            state,
            commodity,
            days,
        )

        data_points = [
            {
                "date": row["arrival_date"],
                "avg_modal_price": round(float(row["avg_modal"]), 2),
                "min_price": round(float(row["min_price"]), 2) if row["min_price"] else None,
                "max_price": round(float(row["max_price"]), 2) if row["max_price"] else None,
                "record_count": row["record_count"],
            }
            for row in rows
        ]

        avg_price = None
        price_change_pct = None
        if data_points:
            prices = [dp["avg_modal_price"] for dp in data_points]
            avg_price = round(sum(prices) / len(prices), 2)
            if len(prices) >= 2 and prices[0] > 0:
                price_change_pct = round(
                    (prices[-1] - prices[0]) / prices[0] * 100, 2
                )

        return {
            "state": state,
            "commodity": commodity,
            "period_start": data_points[0]["date"] if data_points else None,
            "period_end": data_points[-1]["date"] if data_points else None,
            "data_points": data_points,
            "avg_price": avg_price,
            "price_change_pct": price_change_pct,
        }

    # ── MSP Comparison ────────────────────────────────────────────

    async def get_msp_comparison(
        self,
        state: str,
        crop: str,
        year: int | None = None,
    ) -> dict[str, Any]:
        """Compare district market prices against the MSP for a crop."""
        target_year = year or date.today().year

        # Get MSP rate
        msp_row = await self.conn.fetchrow(
            """
            SELECT crop, season, year, msp_price, grade, unit
            FROM msp_rates
            WHERE crop = $1 AND year = $2
            ORDER BY year DESC
            LIMIT 1
            """,
            crop.lower(),
            target_year,
        )

        if not msp_row:
            # Try closest year
            msp_row = await self.conn.fetchrow(
                """
                SELECT crop, season, year, msp_price, grade, unit
                FROM msp_rates
                WHERE crop = $1
                ORDER BY ABS(year - $2)
                LIMIT 1
                """,
                crop.lower(),
                target_year,
            )

        if not msp_row:
            return {"error": f"No MSP data found for crop: {crop}"}

        msp_price = float(msp_row["msp_price"])

        # Get district-level average prices
        district_rows = await self.conn.fetch(
            """
            SELECT district,
                   MAX(market) as market,
                   AVG(modal_price) as avg_modal,
                   COUNT(*) as count
            FROM mandi_prices
            WHERE UPPER(state) = UPPER($1)
              AND (commodity_normalized = $2 OR commodity ILIKE $3)
            GROUP BY district
            ORDER BY AVG(modal_price) DESC
            """,
            state,
            crop.lower(),
            f"%{crop}%",
        )

        districts: list[dict[str, Any]] = []
        above_msp = 0
        below_msp = 0
        total_modal = 0.0

        for row in district_rows:
            avg_modal = float(row["avg_modal"])
            ratio = round(avg_modal / msp_price, 3) if msp_price > 0 else 0
            premium_pct = round((avg_modal - msp_price) / msp_price * 100, 1) if msp_price > 0 else 0

            if ratio > 1.02:
                status = "Above MSP"
                above_msp += 1
            elif ratio < 0.98:
                status = "Below MSP"
                below_msp += 1
            else:
                status = "At MSP"

            districts.append({
                "district": row["district"],
                "market": row["market"],
                "avg_modal_price": round(avg_modal, 2),
                "msp_price": msp_price,
                "price_vs_msp_ratio": ratio,
                "premium_or_deficit_pct": premium_pct,
                "status": status,
            })
            total_modal += avg_modal

        state_avg = round(total_modal / len(districts), 2) if districts else None
        state_ratio = round(state_avg / msp_price, 3) if state_avg and msp_price > 0 else None

        return {
            "state": state,
            "crop": crop,
            "year": msp_row["year"],
            "msp": {
                "crop": msp_row["crop"],
                "season": msp_row["season"],
                "year": msp_row["year"],
                "msp_price": msp_price,
                "grade": msp_row["grade"],
                "unit": msp_row["unit"],
            },
            "districts": districts,
            "state_avg_modal_price": state_avg,
            "state_avg_ratio": state_ratio,
            "districts_above_msp": above_msp,
            "districts_below_msp": below_msp,
            "source": "data.gov.in + CACP",
        }

    # ── Price Map ─────────────────────────────────────────────────

    async def get_price_map(
        self, commodity: str
    ) -> dict[str, Any]:
        """Get price data for all districts for a commodity (for choropleth map)."""
        rows = await self.conn.fetch(
            """
            SELECT state, district,
                   commodity_normalized as commodity,
                   AVG(modal_price) as avg_modal,
                   MIN(min_price) as min_price,
                   MAX(max_price) as max_price,
                   COUNT(*) as count,
                   MAX(arrival_date) as latest_date
            FROM mandi_prices
            WHERE commodity_normalized = $1
               OR commodity ILIKE $2
            GROUP BY state, district, commodity_normalized
            ORDER BY state, district
            """,
            commodity.lower(),
            f"%{commodity}%",
        )

        items = [
            {
                "state": row["state"],
                "district": row["district"],
                "commodity": row["commodity"] or commodity,
                "avg_modal_price": round(float(row["avg_modal"]), 2),
                "min_price": round(float(row["min_price"]), 2) if row["min_price"] else None,
                "max_price": round(float(row["max_price"]), 2) if row["max_price"] else None,
                "record_count": row["count"],
                "date": row["latest_date"],
            }
            for row in rows
        ]

        all_prices = [i["avg_modal_price"] for i in items]
        price_range = {}
        if all_prices:
            price_range = {
                "min": min(all_prices),
                "max": max(all_prices),
                "avg": round(sum(all_prices) / len(all_prices), 2),
            }

        return {
            "commodity": commodity,
            "total_districts": len(items),
            "items": items,
            "price_range": price_range,
        }

    # ── Available Commodities ─────────────────────────────────────

    async def get_available_commodities(self) -> list[dict[str, Any]]:
        """List all commodities available in the mandi data."""
        rows = await self.conn.fetch(
            """
            SELECT commodity as name,
                   commodity_normalized as normalized,
                   COUNT(*) as record_count,
                   COUNT(DISTINCT state) as states_count,
                   MAX(arrival_date) as latest_date,
                   AVG(modal_price) as avg_price
            FROM mandi_prices
            WHERE commodity_normalized IS NOT NULL
            GROUP BY commodity, commodity_normalized
            ORDER BY record_count DESC
            """
        )

        return [
            {
                "name": row["name"],
                "normalized": row["normalized"],
                "record_count": row["record_count"],
                "states_count": row["states_count"],
                "latest_date": row["latest_date"],
                "avg_price": round(float(row["avg_price"]), 2) if row["avg_price"] else None,
            }
            for row in rows
        ]

    # ── MSP Rates ─────────────────────────────────────────────────

    async def get_msp_rates(
        self,
        crop: str | None = None,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get MSP rates with optional filters."""
        conditions = []
        params: list[Any] = []
        idx = 1

        if crop:
            conditions.append(f"crop = ${idx}")
            params.append(crop.lower())
            idx += 1

        if year:
            conditions.append(f"year = ${idx}")
            params.append(year)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = await self.conn.fetch(
            f"""
            SELECT crop, season, year, msp_price, grade, unit
            FROM msp_rates
            {where}
            ORDER BY crop, year DESC
            """,
            *params,
        )

        return [dict(row) for row in rows]
