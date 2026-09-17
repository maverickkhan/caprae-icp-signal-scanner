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


class CriterionIn(BaseModel):
    key: str | None = None
    label: str
    weight: int = 1
    test: str = ""
    polarity: str = "positive"


class IcpOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description_text: str
    description_hash: str | None = None
    criteria: list[dict]


class IcpCreate(BaseModel):
    name: str
    description_text: str


class IcpUpdate(BaseModel):
    name: str | None = None
    description_text: str | None = None
    criteria: list[CriterionIn] | None = None


class ScanSummary(BaseModel):
    scan_id: int
    status: str
    score: float | None = None
    coverage: float | None = None
    met_criteria: list[str] = []
    red_flags: list[str] = []
    no_evidence_reason: str | None = None
    finished_at: datetime | None = None
    error: str | None = None


class CompanyWithScan(CompanyOut):
    scan: ScanSummary | None = None
