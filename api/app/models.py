"""SQLAlchemy models (schema from docs/PLAN.md)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(64))
    employee_range: Mapped[str | None] = mapped_column(String(64))
    revenue_estimate: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(64))
    linkedin_url: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str | None] = mapped_column(String(64))
    reachable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IcpProfile(Base):
    __tablename__ = "icp_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description_text: Mapped[str] = mapped_column(Text, nullable=False)
    description_hash: Mapped[str | None] = mapped_column(String(64))
    # [{key, label, weight, test, polarity}]
    criteria: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    icp_id: Mapped[int] = mapped_column(ForeignKey("icp_profiles.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")  # running|done|error
    score: Mapped[float | None] = mapped_column(Float)
    coverage: Mapped[float | None] = mapped_column(Float)
    outreach_note: Mapped[str | None] = mapped_column(Text)
    model_versions: Mapped[dict | None] = mapped_column(JSONB)
    pages_fetched: Mapped[int | None] = mapped_column(Integer)
    fallback_used: Mapped[bool | None] = mapped_column(Boolean)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_scans_company_icp_finished", "company_id", "icp_id", "finished_at"),)


class Fact(Base):
    __tablename__ = "facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(64))
    fact: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_quote: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    grounding: Mapped[str] = mapped_column(String(16), nullable=False, default="none")  # exact|fuzzy|none


class CriterionResult(Base):
    __tablename__ = "criterion_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    criterion_key: Mapped[str] = mapped_column(String(64), nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")  # met|not_met|unknown
    evidence_quote: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    grounding: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    confidence: Mapped[float | None] = mapped_column(Float)


class Page(Base):
    __tablename__ = "pages"

    url: Mapped[str] = mapped_column(Text, primary_key=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status_code: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    via: Mapped[str] = mapped_column(String(16), nullable=False, default="live")  # live|wayback


class Enrichment(Base):
    __tablename__ = "enrichments"

    domain: Mapped[str] = mapped_column(String(255), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)  # rdap|wayback
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
