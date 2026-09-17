"""ICP description -> 4-8 weighted criteria (smart model), cached by description hash."""

from __future__ import annotations

import hashlib
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.llm import call_llm, smart_llm
from app.graph.prompts import COMPILE_ICP_SYSTEM, COMPILE_ICP_USER
from app.graph.schemas import CriteriaList
from app.models import IcpProfile


def description_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).lower().encode()).hexdigest()


def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return s[:48] or "criterion"


def clean_criteria(raw: list[dict]) -> list[dict]:
    """Slugify + dedupe keys, clamp weights, normalise polarity. Used for LLM output and user edits."""
    out: list[dict] = []
    seen: set[str] = set()
    for c in raw:
        key = _slug(str(c.get("key") or c.get("label") or ""))
        base, n = key, 2
        while key in seen:
            key, n = f"{base}_{n}", n + 1
        seen.add(key)
        try:
            weight = max(1, min(5, int(c.get("weight") or 1)))
        except (TypeError, ValueError):
            weight = 1
        out.append(
            {
                "key": key,
                "label": str(c.get("label") or key.replace("_", " ")).strip()[:80],
                "weight": weight,
                "test": str(c.get("test") or "").strip()[:400],
                "polarity": "negative" if str(c.get("polarity", "")).lower() == "negative" else "positive",
            }
        )
    return out[:8]


async def compile_criteria(description: str, *, sem=None) -> list[dict]:
    runnable = smart_llm().with_structured_output(CriteriaList)
    messages = [("system", COMPILE_ICP_SYSTEM), ("human", COMPILE_ICP_USER.format(description=description.strip()))]
    out: CriteriaList = await call_llm(runnable, messages, sem)
    return clean_criteria([c.model_dump() for c in out.criteria])


async def ensure_compiled(icp: IcpProfile, db: AsyncSession, *, force: bool = False) -> IcpProfile:
    """Compile when criteria are empty or the description changed (hash mismatch). No-op otherwise."""
    h = description_hash(icp.description_text)
    if not force and icp.criteria and icp.description_hash == h:
        return icp
    icp.criteria = await compile_criteria(icp.description_text)
    icp.description_hash = h
    await db.commit()
    await db.refresh(icp)
    return icp
