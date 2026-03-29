"""
Search response schemas.
"""
from pydantic import BaseModel


class SearchResultItem(BaseModel):
    cdk: str | None = None
    name: str
    state: str
    result_type: str
    start_year: int | None = None
    end_year: int | None = None
    district_count: int | None = None


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResultItem]
