"""Domain normalization used for import dedupe and cache keys."""

import re
from urllib.parse import urlsplit

_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)


def normalize_domain(raw: str | None) -> str | None:
    """'HTTPS://www.Acme.com:443/about/' -> 'acme.com'. Returns None if no usable host."""
    if not raw:
        return None
    s = raw.strip().strip("\"'").lower()
    if not s:
        return None
    if not _SCHEME_RE.match(s):
        s = "http://" + s
    host = urlsplit(s).hostname or ""
    host = host.strip(".")
    if host.startswith("www."):
        host = host[4:]
    if "." not in host or " " in host:
        return None
    return host
