"""Deterministic backstop for high-value statements the LLM extractor sometimes skips.

Regex over the page text for ownership / affiliation / founding / franchise phrases. Each hit becomes a fact
whose evidence_quote is the verbatim sentence window, so grounding is exact by construction.
"""

from __future__ import annotations

import re

_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    (
        "affiliations",
        "The company states it is a brand, division or subsidiary of another company.",
        re.compile(r"\b(?:a |the )?(?:leading |flagship )?(?:brand|division|subsidiary|part|member|portfolio company) of [A-Z][^.\n]{2,80}", re.I),
    ),
    (
        "affiliations",
        "The company states it is owned by or backed by another company or investor.",
        re.compile(r"\b(?:owned|acquired|backed) by [A-Z][^.\n]{2,80}", re.I),
    ),
    (
        "affiliations",
        "The company operates company-owned locations.",
        re.compile(r"\bcompany-owned (?:locations?|branches|stores)\b[^.\n]{0,80}", re.I),
    ),
    (
        "affiliations",
        "The company describes itself as a franchise or franchisee.",
        re.compile(r"\b(?:independently owned and operated franchise|franchisee|franchise of|a franchise\b)[^.\n]{0,80}", re.I),
    ),
    (
        "ownership_leadership",
        "The company describes itself as family-owned or owner-operated.",
        re.compile(r"\b(?:family[- ](?:owned|run|operated)|owner[- ]operated|locally owned and operated)\b[^.\n]{0,80}", re.I),
    ),
    (
        "founding_history",
        "The page states when the business was founded or how long it has operated.",
        re.compile(r"\b(?:since|established in|founded in|serving [^.\n]{0,40} since|in business (?:for|since)|over|more than) (?:19|20)\d{2}\b[^.\n]{0,60}|\b(?:over|more than) \d{2} years\b[^.\n]{0,60}", re.I),
    ),
]

_MAX_PER_PATTERN = 2


def _window(text: str, start: int, end: int, limit: int = 200) -> str:
    """Expand a match to sentence-ish boundaries, capped at `limit` chars, verbatim."""
    s = max(0, text.rfind(".", 0, start) + 1)
    e = text.find(".", end)
    e = len(text) if e == -1 else e + 1
    quote = text[s:e].strip()
    if len(quote) > limit:
        # keep the match inside the window
        lead = max(0, start - s - (limit - (end - start)) // 2)
        quote = text[s + lead : s + lead + limit].strip()
    return re.sub(r"\s+", " ", quote)


def regex_signals(text: str, url: str) -> list[dict]:
    facts: list[dict] = []
    seen: set[str] = set()
    for category, fact, pat in _PATTERNS:
        n = 0
        for m in pat.finditer(text):
            quote = _window(text, m.start(), m.end())
            key = quote.lower()
            if len(quote) < 12 or key in seen:
                continue
            seen.add(key)
            facts.append(
                {
                    "category": category,
                    "fact": f"{fact} Quote: \"{quote[:120]}\"",
                    "evidence_quote": quote,
                    "source_url": url,
                    "confidence": 0.9,
                    "signal": True,
                }
            )
            n += 1
            if n >= _MAX_PER_PATTERN:
                break
    return facts
