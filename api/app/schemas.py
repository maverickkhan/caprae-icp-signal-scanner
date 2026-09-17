"""Pydantic response/request models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    domain: str
    name: str | None = None
    industry: str | None = None
    city: str | None = None
    state: str | None = None
    employee_range: str | None = None
    revenue_estimate: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    source: str | None = None
    reachable: bool | None = None
    created_at: datetime | None = None


class ImportResult(BaseModel):
    inserted: int
    duplicates_skipped: int
    no_domain_skipped: int
    total_rows: int
