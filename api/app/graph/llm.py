"""Gemini clients (models from env), per-scan concurrency gate, tenacity backoff on rate limits."""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any

from langchain_core.exceptions import ModelConnectionError, ModelRateLimitError, ModelTimeoutError
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, stop_after_delay, wait_exponential

try:  # google-genai raises these under langchain's wrappers on some paths
    from google.genai.errors import ServerError as _GenaiServerError
except Exception:  # noqa: BLE001
    _GenaiServerError = ()  # type: ignore[assignment]

from app.config import get_settings

log = logging.getLogger("icp.llm")

SCAN_LLM_CONCURRENCY = 2


def _chat(model: str) -> ChatGoogleGenerativeAI:
    s = get_settings()
    if not model:
        raise RuntimeError("GEMINI_FAST_MODEL / GEMINI_SMART_MODEL must be set")
    return ChatGoogleGenerativeAI(model=model, temperature=0, google_api_key=s.google_api_key, max_retries=0)


@lru_cache
def fast_llm() -> ChatGoogleGenerativeAI:
    return _chat(get_settings().gemini_fast_model)


@lru_cache
def smart_llm() -> ChatGoogleGenerativeAI:
    return _chat(get_settings().gemini_smart_model)


def model_versions() -> dict[str, str]:
    s = get_settings()
    return {"fast": s.gemini_fast_model, "smart": s.gemini_smart_model}


def is_rate_limit(exc: BaseException) -> bool:
    """429 / RESOURCE_EXHAUSTED, plus transient 503 'overloaded' and connection blips."""
    if isinstance(exc, (ModelRateLimitError, ModelConnectionError, ModelTimeoutError)):
        return True
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code in (429, 503):
        return True
    if _GenaiServerError and isinstance(exc, _GenaiServerError):
        return True
    msg = str(exc).upper()
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "QUOTA" in msg or "RATE LIMIT" in msg or "OVERLOADED" in msg or "503" in msg


def new_semaphore() -> asyncio.Semaphore:
    return asyncio.Semaphore(SCAN_LLM_CONCURRENCY)


async def call_llm(runnable: Runnable, inputs: Any, sem: asyncio.Semaphore | None, *, config: dict | None = None) -> Any:
    """Invoke under the per-scan semaphore; exponential backoff only on 429 / RESOURCE_EXHAUSTED."""
    retrying = AsyncRetrying(
        retry=retry_if_exception(is_rate_limit),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        stop=stop_after_attempt(5) | stop_after_delay(45),  # bounded: a scan must finish inside one request
        reraise=True,
        before_sleep=lambda rs: log.warning("rate limited; retry %s in %.0fs", rs.attempt_number, rs.next_action.sleep),
    )
    async for attempt in retrying:
        with attempt:
            if sem is None:
                return await runnable.ainvoke(inputs, config=config)
            async with sem:
                return await runnable.ainvoke(inputs, config=config)
    raise RuntimeError("unreachable")
