from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class PageData(TypedDict):
    url: str
    text: str
    via: str
    status_code: int | None


class ScanState(TypedDict, total=False):
    scan_id: int
    company_id: int
    company_name: str | None
    domain: str
    icp_id: int
    icp_name: str
    criteria: list[dict]
    # plan_and_fetch
    pages: list[PageData]
    pages_fetched: int
    fallback_used: bool
    reachable: bool | None
    content_chars: int  # total extracted text across all usable pages (live or Wayback)
    no_evidence_reason: str | None  # site_unreadable | content_too_thin | None
    enrichments: dict
    # extract (fan-out) -> ground_merge
    raw_facts: Annotated[list[dict], operator.add]
    facts: list[dict]
    # judge -> score -> note
    judgments: list[dict]
    verdicts: dict[str, str]
    score: dict
    note: str | None
    note_fact_ids: list[int]
    note_status: str  # ok | unverified | skipped | red_flag
    timings: dict[str, float]


class ExtractInput(TypedDict):
    domain: str
    url: str
    text: str
