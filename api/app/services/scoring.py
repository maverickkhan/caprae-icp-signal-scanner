"""Deterministic fit score.

- score    = 100 x met-positive weight / known-positive weight, minus a penalty for every "avoid"
             (negative-polarity) criterion that IS present: penalty = 100 x its weight / total positive weight.
             Floored at 0. None ("No evidence") when no positive criterion has a known verdict.
- coverage = known positive criteria / all positive criteria (x100).
- An avoid criterion that is NOT present is neutral: it adds nothing and does not count toward coverage.
- Unknown never counts for or against.
"""

from __future__ import annotations

from typing import TypedDict

SCORING_VERSION = 2  # bump when the formula changes: invalidates cached scans via criteria_hash


class CriterionScore(TypedDict):
    key: str
    label: str
    weight: int
    polarity: str
    verdict: str  # met | not_met | unknown
    earned: int  # positive weight earned toward the score (0 if unknown/not met/negative)
    counted: bool  # positive criterion with a known verdict -> in the denominator
    red_flag: bool  # negative criterion that was met -> penalty applied
    penalty: float  # points subtracted from the score (red flags only)


class ScoreResult(TypedDict):
    score: float | None  # 0..100, None if no positive criterion is known
    coverage: float  # % of positive criteria with a known verdict
    earned_weight: int
    known_weight: int
    total_weight: int  # total positive weight
    penalty: float  # total points subtracted for red flags
    breakdown: list[CriterionScore]


def compute_score(criteria: list[dict], verdicts: dict[str, str]) -> ScoreResult:
    positives = [c for c in criteria if c.get("polarity", "positive") != "negative"]
    total_pos = sum(int(c.get("weight") or 1) for c in positives)
    breakdown: list[CriterionScore] = []
    earned = known = 0
    n_known = 0
    penalty_total = 0.0
    for c in criteria:
        w = int(c.get("weight") or 1)
        v = verdicts.get(c["key"], "unknown")
        if v not in ("met", "not_met"):
            v = "unknown"
        negative = c.get("polarity", "positive") == "negative"
        e = 0
        counted = False
        red_flag = False
        penalty = 0.0
        if negative:
            if v == "met":
                red_flag = True
                penalty = round(100.0 * w / total_pos, 1) if total_pos else 100.0
                penalty_total += penalty
        elif v != "unknown":
            counted = True
            known += w
            n_known += 1
            if v == "met":
                e = w
                earned += w
        breakdown.append(
            CriterionScore(
                key=c["key"],
                label=c.get("label", c["key"]),
                weight=w,
                polarity="negative" if negative else "positive",
                verdict=v,
                earned=e,
                counted=counted,
                red_flag=red_flag,
                penalty=penalty,
            )
        )
    score: float | None = None
    if known:
        score = round(max(0.0, 100.0 * earned / known - penalty_total), 1)
    return ScoreResult(
        score=score,
        coverage=round(100.0 * n_known / len(positives), 1) if positives else 0.0,
        earned_weight=earned,
        known_weight=known,
        total_weight=total_pos,
        penalty=round(penalty_total, 1),
        breakdown=breakdown,
    )
