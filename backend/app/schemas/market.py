"""
Market Data Schemas: Mandi prices, MSP benchmarks, and price analytics.
"""

import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Mandi Price Models ────────────────────────────────────────────────


class MandiPrice(BaseModel):
    """A single commodity price record from a mandi."""

    state: str
    district: str
    market: Optional[str] = None
    commodity: str
    commodity_normalized: Optional[str] = None
    variety: Optional[str] = None
    grade: Optional[str] = None
    arrival_date: datetime.date
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    modal_price: float


class MandiPriceResponse(BaseModel):
    """Response for mandi price queries."""

    state: Optional[str] = None
    district: Optional[str] = None
    total: int
    prices: list[MandiPrice] = Field(default_factory=list)
    source: str = "data.gov.in (Ministry of Agriculture)"


# ── Price Trend Models ────────────────────────────────────────────────


class PriceTrendPoint(BaseModel):
    """A single point in a price trend over time."""

    price_date: datetime.date = Field(alias="date")
    avg_modal_price: float
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    record_count: int = 0


class PriceTrend(BaseModel):
    """Price trend for a commodity in a state."""

    state: str
    commodity: str
    period_start: Optional[datetime.date] = None
    period_end: Optional[datetime.date] = None
    data_points: list[PriceTrendPoint] = Field(default_factory=list)
    avg_price: Optional[float] = None
    price_change_pct: Optional[float] = None


# ── MSP Comparison Models ────────────────────────────────────────────


class MSPRate(BaseModel):
    """Official Minimum Support Price for a crop."""

    crop: str
    season: str
    year: int
    msp_price: float
    grade: Optional[str] = None
    unit: str = "INR/quintal"


class MSPComparisonItem(BaseModel):
    """A district's market price compared to MSP."""

    district: str
    market: Optional[str] = None
    avg_modal_price: float
    msp_price: float
    price_vs_msp_ratio: float = Field(
        ..., description="Ratio: > 1.0 means farmer gets above MSP"
    )
    premium_or_deficit_pct: float = Field(
        ..., description="Percentage above(+) or below(-) MSP"
    )
    status: str = Field(
        ..., description="'Above MSP', 'At MSP', or 'Below MSP'"
    )


class MSPComparisonResponse(BaseModel):
    """MSP comparison results for a state and crop."""

    state: str
    crop: str
    year: int
    msp: MSPRate
    districts: list[MSPComparisonItem] = Field(default_factory=list)
    state_avg_modal_price: Optional[float] = None
    state_avg_ratio: Optional[float] = None
    districts_above_msp: int = 0
    districts_below_msp: int = 0
    source: str = "data.gov.in + CACP"


# ── Price Map Models ─────────────────────────────────────────────────


class PriceMapItem(BaseModel):
    """District-level price for map choropleth."""

    state: str
    district: str
    commodity: str
    avg_modal_price: float
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    record_count: int = 0
    price_date: Optional[datetime.date] = Field(None, alias="date")


class PriceMapResponse(BaseModel):
    """Price map data for a commodity across all districts."""

    commodity: str
    total_districts: int
    items: list[PriceMapItem] = Field(default_factory=list)
    price_range: dict[str, float] = Field(
        default_factory=dict,
        description="min/max/avg across all districts",
    )


# ── Available Commodities ────────────────────────────────────────────


class CommodityInfo(BaseModel):
    """Info about an available commodity in the market data."""

    name: str
    normalized: str
    record_count: int
    states_count: int
    latest_date: Optional[datetime.date] = None
    avg_price: Optional[float] = None
