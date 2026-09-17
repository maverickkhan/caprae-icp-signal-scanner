"""Deterministic backstop for ownership / affiliation / founding statements the LLM extractor sometimes skips.

Only explicit corporate-relationship phrases followed by a named organisation count (e.g. "is a brand of
American Residential Services LLC"). Generic phrases ("part of our family", "backed by our guarantee",
"member of", licence numbers) never match. Each hit becomes a fact whose evidence_quote is the verbatim
sentence (trimmed at word boundaries), so grounding is exact by construction.
"""

from __future__ import annotations

import re

# A proper-noun organisation name: capitalised words, optional corporate suffix. Max ~6 tokens.
_ORG = r"(?P<org>[A-Z][\w&'’.-]*(?:[ /-][A-Z0-9][\w&'’.-]*){0,5}(?:,? (?:LLC|L\.L\.C\.|Inc\.?|Corp\.?|Corporation|Co\.|Ltd\.?|Group|Holdings|Partners|Capital|Company|Companies|Enterprises|Industries|Equity|Ventures))?)"
_CORP_SUFFIX = r"(?:LLC|L\.L\.C\.|Inc\.?|Corp\.?|Corporation|Ltd\.?|Group|Holdings|Partners|Capital|Equity|Ventures|Companies|Industries)"
_ORG_CORP = r"(?P<org>[A-Z][\w&'’.-]*(?:[ /-][A-Z0-9][\w&'’.-]*){0,5},? " + _CORP_SUFFIX + r")"

_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    # "<X> is a (leading) brand of <Org>" — product lists ("every brand of Carrier") do not have "is a".
    ("affiliations", "brand", re.compile(r"\b(?:is|as) (?:a |the )?(?:leading |flagship |premier )?brand of " + _ORG, re.U)),
    ("affiliations", "subsidiary", re.compile(r"\b(?:is )?(?:a |the )?(?:wholly[- ]owned )?(?P<kind>subsidiary|division) of " + _ORG, re.U)),
    # ownership by a corporate entity only (a person or family is not a corporate red flag)
    ("affiliations", "owned", re.compile(r"\b(?P<verb>owned|acquired) by " + _ORG_CORP, re.U)),
    ("affiliations", "company_owned", re.compile(r"\bcompany-owned (?:locations?|branches|service centers?) across (?P<region>[^.\n]{2,60})", re.I)),
    ("affiliations", "franchise", re.compile(r"\b(?:owned and operated franchise|franchisee|a franchise of " + _ORG + r"|independently owned and operated franchise|each (?:location|franchise) is independently owned and operated)", re.U)),
    ("ownership_leadership", "family", re.compile(r"\b(?:family[- ](?:owned|run|operated)|owner[- ]operated|locally owned and operated)\b", re.I)),
    ("founding_history", "since", re.compile(r"\b(?:since|established in|founded in|est\.?|serving [^.\n]{0,40} since) (?P<year>(?:19|20)\d{2})\b", re.I)),
    ("founding_history", "years", re.compile(r"\b(?:over|more than|nearly|for) (?P<years>\d{2})\+? years (?:of |in )(?:business|experience|service)", re.I)),
]

_MAX_PER_PATTERN = 2
_QUOTE_LIMIT = 200
_TESTIMONIAL_RE = re.compile(r"[\"“”]|★|\breview(?:s|ed)?\b|\btestimonial|\bstars?\b|\brated\b|\bthank you\b|\bhighly recommend\b|\bmy (?:home|house|unit|ac|system)\b|\bI (?:called|had|was|am|have|would|highly)\b|\bthey (?:were|came|did|showed|are|fixed)\b", re.I)


def _sentence(text: str, start: int, end: int) -> str:
    """The sentence containing [start, end), trimmed to word boundaries and <= _QUOTE_LIMIT chars."""
    s = max(text.rfind(". ", 0, start), text.rfind("\n", 0, start), text.rfind("! ", 0, start), text.rfind("? ", 0, start))
    s = 0 if s == -1 else s + 2 if text[s] != "\n" else s + 1
    e = len(text)
    for terminator in (". ", ".\n", "!", "?", "\n"):
        i = text.find(terminator, end)
        if i != -1:
            e = min(e, i + (1 if terminator[0] in ".!?" else 0))
    quote = text[s:e]
    if len(quote) > _QUOTE_LIMIT:
        # keep the match, cut at word boundaries on both sides
        room = _QUOTE_LIMIT - (end - start)
        left = max(s, start - room // 2)
        right = min(e, end + room - (start - left))
        quote = text[left:right]
        if left > s:
            quote = quote[quote.find(" ") + 1 :] if " " in quote[: start - left] else quote
        if right < e:
            quote = quote[: quote.rfind(" ")] if " " in quote[end - left :] else quote
    quote = re.sub(r"\s+", " ", quote).strip()
    return quote.lstrip(",;:-–—·|)] ").rstrip(" ,;:-–—·|([")


def _clean_org(org: str | None) -> str:
    return (org or "").strip().rstrip(".,;: ")


def _fact_sentence(kind: str, m: re.Match) -> str:
    g = {k: (_clean_org(v) if k == "org" else v) for k, v in m.groupdict().items()}
    if kind == "brand":
        return f"The company describes itself as a brand of {g['org']}."
    if kind == "subsidiary":
        return f"The company describes itself as a {g['kind'].lower()} of {g['org']}."
    if kind == "owned":
        return f"The company states it is {g['verb'].lower()} by {g['org']}."
    if kind == "company_owned":
        return f"The company operates company-owned locations across {g['region'].strip()}."
    if kind == "franchise":
        return "The company describes itself as a franchise or franchisee."
    if kind == "family":
        return f"The company describes itself as {m.group(0).lower()}."
    if kind == "since":
        return f"The page states the business has operated since {g['year']}."
    if kind == "years":
        return f"The page mentions {g['years']}+ years of business or experience."
    return m.group(0)


def regex_signals(text: str, url: str) -> list[dict]:
    facts: list[dict] = []
    seen: set[str] = set()
    for category, kind, pat in _PATTERNS:
        n = 0
        for m in pat.finditer(text):
            quote = _sentence(text, m.start(), m.end())
            if len(quote) < 12 or _TESTIMONIAL_RE.search(quote):
                continue
            key = quote.lower()
            if key in seen:
                continue
            seen.add(key)
            facts.append(
                {
                    "category": category,
                    "fact": _fact_sentence(kind, m),
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
