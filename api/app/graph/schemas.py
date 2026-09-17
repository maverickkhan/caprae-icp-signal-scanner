"""Structured-output schemas. Every LLM call returns one top-level object (lists are wrapped)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FACT_CATEGORIES = (
    "founding_history",
    "ownership_leadership",
    "team_size",
    "locations_service_area",
    "hiring",
    "services_tech",
    "contact",
    "certifications_awards",
    "affiliations",
    "website_signals",
    "other",
)


class Criterion(BaseModel):
    key: str = Field(description="snake_case identifier, e.g. years_in_business_20plus")
    label: str = Field(description="Short human label, <= 6 words")
    weight: int = Field(ge=1, le=5, description="Importance 1 (minor) .. 5 (critical)")
    test: str = Field(description="A yes/no question answerable from the company's public website or domain records")
    polarity: Literal["positive", "negative"] = Field(description="positive = meeting it is good; negative = meeting it is a disqualifier")


class CriteriaList(BaseModel):
    criteria: list[Criterion] = Field(min_length=4, max_length=8)


class CompanyFact(BaseModel):
    category: str = Field(description=f"One of: {', '.join(FACT_CATEGORIES)}")
    fact: str = Field(description="One-sentence statement of the fact, <= 160 chars")
    evidence_quote: str = Field(description="Verbatim excerpt copied character-for-character from the page text, <= 200 chars")
    confidence: float = Field(ge=0, le=1, description="How directly the quote supports the fact")


class FactList(BaseModel):
    facts: list[CompanyFact] = Field(default_factory=list, max_length=15)


class Judgment(BaseModel):
    criterion_key: str
    verdict: Literal["met", "not_met", "unknown"]
    fact_ids: list[int] = Field(default_factory=list, description="ids of the facts that support the verdict; empty when unknown")
    reasoning: str = Field(description="<= 200 chars")


class JudgmentList(BaseModel):
    judgments: list[Judgment]


class OutreachNote(BaseModel):
    note: str = Field(description="Exactly 4 sentences, plain text, no placeholders")
    fact_ids: list[int] = Field(description="Exactly two fact ids referenced in the note")
