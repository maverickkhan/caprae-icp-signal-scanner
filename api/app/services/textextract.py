"""HTML -> plain text for the LLM. Deterministic; output is what quotes are grounded against."""

import hashlib
import html as html_lib
import re

import trafilatura

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_DESC_RE = re.compile(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']{0,300})', re.I)
# Copyright / "since" lines usually live in footers that boilerplate removal drops; keep them.
_COPYRIGHT_RE = re.compile(r"(?:©|&copy;|&#169;|copyright)\s*[^<\n]{0,140}", re.I)
_THIRD_PARTY_RE = re.compile(r"google|mapbox|openstreetmap|leaflet|wordpress|wix|squarespace|godaddy|elementor|shopify|weebly|duda|yelp|facebook|jquery|bootstrap|font ?awesome|adobe|microsoft|apple", re.I)


def _strip_tags(s: str) -> str:
    return _WS_RE.sub(" ", html_lib.unescape(_TAG_RE.sub(" ", s))).strip()


def extract_text(html: str, url: str, cap: int = 6000) -> str:
    body = ""
    try:
        body = (
            trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=True,
                favor_recall=True,
                deduplicate=True,
            )
            or ""
        )
    except Exception:  # noqa: BLE001 - lxml can choke on odd markup; treat as empty
        body = ""
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    parts: list[str] = []
    m = _TITLE_RE.search(html)
    if m:
        title = _strip_tags(m.group(1))[:200]
        if title:
            parts.append(f"Page title: {title}")
    m = _DESC_RE.search(html)
    if m:
        desc = _strip_tags(m.group(1))
        if desc:
            parts.append(f"Meta description: {desc}")
    if body:
        parts.append(body[:cap])

    seen: set[str] = set()
    footer: list[str] = []
    for c in _COPYRIGHT_RE.findall(html):
        line = _strip_tags(c)
        key = line.lower()
        if _THIRD_PARTY_RE.search(key):  # embedded maps / widgets / themes carry their own notices
            continue
        if line and key not in seen and len(line) > 6:
            seen.add(key)
            footer.append(line)
        if len(footer) >= 2:
            break
    if footer:
        parts.append("Footer: " + " | ".join(footer))
    return "\n\n".join(parts).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()
