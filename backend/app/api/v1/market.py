"""
Market API: Mandi prices, MSP comparison, and price analytics.
"""

import logging

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.schemas.market import (
    CommodityInfo,
    MandiPriceResponse,
    MSPComparisonResponse,
    MSPRate,
    PriceMapResponse,
    PriceTrend,
)
from app.services.market_service import MarketService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/prices", response_model=MandiPriceResponse)
async def get_mandi_prices(
    state: str | None = Query(None, description="State name, e.g. 'Maharashtra'"),
    district: str | None = Query(None, description="District name"),
    commodity: str | None = Query(None, description="Commodity name (e.g. 'wheat', 'rice')"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get current mandi commodity prices.

    Filter by state, district, and/or commodity. Returns up to `limit` records
    ordered by most recent date first.
    """
    svc = MarketService(db)
    result = await svc.get_prices(
        state=state,
        district=district,
        commodity=commodity,
        limit=limit,
    )
    return MandiPriceResponse.model_validate(result)


@router.get("/trends", response_model=PriceTrend)
async def get_price_trends(
    state: str = Query(..., description="State name"),
    commodity: str = Query(..., description="Commodity (normalized name, e.g. 'wheat')"),
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get daily price trend for a commodity in a state.

    Returns average modal price per day, plus overall change percentage.
    """
    svc = MarketService(db)
    result = await svc.get_price_trends(state=state, commodity=commodity, days=days)
    return PriceTrend.model_validate(result)


@router.get("/msp-comparison", response_model=MSPComparisonResponse)
async def get_msp_comparison(
    state: str = Query(..., description="State name"),
    crop: str = Query(..., description="Crop name (e.g. 'wheat', 'rice')"),
    year: int | None = Query(None, description="MSP year (defaults to current)"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Compare district market prices against the official MSP.

    Shows which districts are selling above or below MSP, with ratio and
    percentage premium/deficit for each district.
    """
    svc = MarketService(db)
    result = await svc.get_msp_comparison(state=state, crop=crop, year=year)
    return MSPComparisonResponse.model_validate(result)


@router.get("/map", response_model=PriceMapResponse)
async def get_price_map(
    commodity: str = Query(..., description="Commodity name"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get price data for all districts for a commodity.

    Returns district-level average prices suitable for choropleth map rendering.
    """
    svc = MarketService(db)
    result = await svc.get_price_map(commodity=commodity)
    return PriceMapResponse.model_validate(result)


@router.get("/commodities", response_model=list[CommodityInfo])
async def get_available_commodities(
    db: asyncpg.Connection = Depends(get_db),
):
    """
    List all commodities available in the mandi price data.

    Returns name, normalized name, record count, state coverage, and average price.
    """
    svc = MarketService(db)
    result = await svc.get_available_commodities()
    return [CommodityInfo.model_validate(item) for item in result]


@router.get("/msp-rates", response_model=list[MSPRate])
async def get_msp_rates(
    crop: str | None = Query(None, description="Filter by crop name"),
    year: int | None = Query(None, description="Filter by year"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get official MSP rates.

    Returns Minimum Support Prices set by the Government of India (CACP).
    Filter by crop and/or year.
    """
    svc = MarketService(db)
    result = await svc.get_msp_rates(crop=crop, year=year)
    return [MSPRate.model_validate(item) for item in result]
