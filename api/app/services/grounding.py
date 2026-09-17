"""Verbatim-quote grounding: exact | fuzzy | none. Deterministic, no LLM."""

from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

FUZZY_THRESHOLD = 90
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize(s: str | None) -> str:
    """casefold, unify unicode quotes/dashes, strip punctuation, collapse whitespace."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace(" ", " ")
    s = s.casefold()
    s = _PUNCT_RE.sub(" ", s)
    return _WS_RE.sub(" ", s).strip()


def ground(quote: str | None, text: str | None) -> str:
    q, t = normalize(quote), normalize(text)
    if not q or not t or len(q) < 4:
        return "none"
    if q in t:
        return "exact"
    if len(q) <= 3000 and fuzz.partial_ratio(q, t) >= FUZZY_THRESHOLD:
        return "fuzzy"
    return "none"


def ground_in_pages(quote: str | None, source_url: str | None, pages: dict[str, str]) -> tuple[str, str | None]:
    """Try the claimed source page first, then every other page. Returns (state, url_it_matched)."""
    if source_url and source_url in pages:
        g = ground(quote, pages[source_url])
        if g != "none":
            return g, source_url
    best = "none"
    best_url = None
    for url, text in pages.items():
        if url == source_url:
            continue
        g = ground(quote, text)
        if g == "exact":
            return g, url
        if g == "fuzzy" and best == "none":
            best, best_url = g, url
    return best, best_url
