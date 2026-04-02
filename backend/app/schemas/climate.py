"""
Climate and rainfall response schemas.
"""

from pydantic import BaseModel, Field


class RainfallStatsResponse(BaseModel):
    source: str
    record_count: int
    status: str


class MonthlyRainfall(BaseModel):
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


class SeasonalRainfall(BaseModel):
    winter_jf: float
    pre_monsoon_mam: float
    monsoon_jjas: float
    post_monsoon_ond: float


class RainfallResponse(BaseModel):
    state: str
    district: str
    monthly: MonthlyRainfall
    seasonal: SeasonalRainfall
    annual: float
    source: str


class RainfallMapItem(BaseModel):
    state: str
    district: str
    annual: float
    monsoon: float


class StateRainfallStatsResponse(BaseModel):
    state: str
    district_count: int
    avg_annual_mm: float
    min_annual_mm: float
    max_annual_mm: float
    avg_monsoon_mm: float


class ClimateValidity(BaseModel):
    climate_assumption: str
    baseline_period: str
    warning: str


class WaterStressDistrict(BaseModel):
    district_name: str
    cdk: str
    total_area: float
    water_intensive_area: float
    water_intensive_share: float
    annual_rainfall: float
    mismatch_score: float
    category: str
    crop_breakdown: dict[str, float]


class WaterStressResponse(BaseModel):
    state: str
    year: int
    districts: list[WaterStressDistrict]
    validity: ClimateValidity


class CorrelationMetric(BaseModel):
    r: float
    interpretation: str
    direction: str


class RainfallCorrelationSet(BaseModel):
    annual_rainfall: CorrelationMetric
    monsoon_rainfall: CorrelationMetric


class RainfallYieldDataPoint(BaseModel):
    district: str
    yield_: float = Field(alias="yield")
    annual_rainfall: float
    monsoon_rainfall: float


class RainfallYieldCorrelationResponse(BaseModel):
    state: str
    crop: str
    year: int
    sample_size: int
    correlations: RainfallCorrelationSet
    data_points: list[RainfallYieldDataPoint]
    note: str
    validity: ClimateValidity
