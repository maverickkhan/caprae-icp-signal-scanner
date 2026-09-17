"""Deterministic fit score. Unknown criteria never count for or against; coverage shows how much was verifiable."""

from __future__ import annotations

from typing import TypedDict


class CriterionScore(TypedDict):
    key: str
    label: str
    weight: int
    polarity: str
    verdict: str  # met | not_met | unknown
    earned: int  # weight earned toward the score (0 if unknown or failed)
    counted: bool  # verdict known → contributes to denominator
    disqualified: bool  # negative criterion that was met


class ScoreResult(TypedDict):
    score: float | None  # 0..100, None if nothing is known
    coverage: float  # % of criteria with a known verdict
    earned_weight: int
    known_weight: int
    total_weight: int
    breakdown: list[CriterionScore]


def _earned(polarity: str, verdict: str, weight: int) -> int:
    if verdict == "unknown":
        return 0
    good = verdict == "met" if polarity != "negative" else verdict == "not_met"
    return weight if good else 0


def compute_score(criteria: list[dict], verdicts: dict[str, str]) -> ScoreResult:
    breakdown: list[CriterionScore] = []
    earned = known = total = 0
    for c in criteria:
        w = int(c.get("weight") or 1)
        v = verdicts.get(c["key"], "unknown")
        if v not in ("met", "not_met"):
            v = "unknown"
        e = _earned(c.get("polarity", "positive"), v, w)
        counted = v != "unknown"
        total += w
        if counted:
            known += w
            earned += e
        breakdown.append(
            CriterionScore(
                key=c["key"],
                label=c.get("label", c["key"]),
                weight=w,
                polarity=c.get("polarity", "positive"),
                verdict=v,
                earned=e,
                counted=counted,
                disqualified=(c.get("polarity") == "negative" and v == "met"),
            )
        )
    n_known = sum(1 for b in breakdown if b["counted"])
    return ScoreResult(
        score=round(100.0 * earned / known, 1) if known else None,
        coverage=round(100.0 * n_known / len(criteria), 1) if criteria else 0.0,
        earned_weight=earned,
        known_weight=known,
        total_weight=total,
        breakdown=breakdown,
    )
