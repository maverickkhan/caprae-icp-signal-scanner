"""Process-wide circuit breaker for archive.org: after a 429/5xx, skip Wayback calls for a while."""

import logging
import time

log = logging.getLogger("icp.wayback")

_cooldown_until = 0.0
COOLDOWN_S = 600.0


def available() -> bool:
    return time.monotonic() >= _cooldown_until


def trip(reason: str) -> None:
    global _cooldown_until
    if available():
        log.info("archive.org unavailable (%s); skipping Wayback for %.0fs", reason, COOLDOWN_S)
    _cooldown_until = time.monotonic() + COOLDOWN_S


def check(status_code: int) -> bool:
    """Record a response status; returns True if the response is usable."""
    if status_code == 429 or status_code >= 500:
        trip(f"http {status_code}")
        return False
    return True
