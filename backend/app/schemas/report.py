"""
Report response schemas.
"""

from pydantic import BaseModel


class DistrictProfileStatistics(BaseModel):
    mean_yield: float | None = None
    max_yield: float | None = None
    min_yield: float | None = None
    years_with_data: int | None = None
    first_year: int | None = None
    last_year: int | None = None
    std_yield: float | None = None
    cv_yield: float | None = None
    mean_area: float | None = None


class DistrictProfileDistrict(BaseModel):
    cdk: str
    name: str
    state: str


class DistrictProfileStateBenchmark(BaseModel):
    avg_yield: float
    efficiency: float | None = None


class DistrictProfileReportResponse(BaseModel):
    report_type: str
    district: DistrictProfileDistrict
    crop: str
    statistics: DistrictProfileStatistics
    state_benchmark: DistrictProfileStateBenchmark
    yearly_data: list[dict[str, float | int]]
