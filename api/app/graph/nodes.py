"""LangGraph nodes. LLM nodes: extract (fast), judge (fast), note (smart). Everything else is deterministic."""

from __future__ import annotations

import asyncio
import logging
import re
import time

from langchain_core.runnables import RunnableConfig
from langgraph.types import Send

from app.graph.llm import call_llm, fast_llm, is_rate_limit, smart_llm
from app.graph.prompts import (
    EXTRACT_SYSTEM,
    EXTRACT_USER,
    JUDGE_SYSTEM,
    JUDGE_USER,
    NOTE_SYSTEM,
    NOTE_USER,
)
from app.graph.schemas import FACT_CATEGORIES, FactList, JudgmentList, OutreachNote
from app.graph.state import ExtractInput, ScanState
from app.services.enrich import enrich
from app.services.fetcher import fetch_page, make_client
from app.services.grounding import ground_in_pages, normalize, numbers_present
from app.services.planner import plan_pages
from app.services.scoring import compute_score
from app.services.signals import regex_signals
from app.services.textextract import content_hash

log = logging.getLogger("icp.graph")

_MARKER_RE = re.compile(r"\[F(\d+)\]")
_WS_MARK_RE = re.compile(r"\s*\[F\d+\]")

MAX_FACTS = 40
MAX_JUDGE_FACTS = 30
MAX_NOTE_FACTS = 12


def _sem(config: RunnableConfig):
    return (config.get("configurable") or {}).get("sem")


# ---------------------------------------------------------------- plan_and_fetch
async def plan_and_fetch(state: ScanState) -> dict:
    t0 = time.perf_counter()
    domain = state["domain"]
    async with make_client() as client:
        enrich_task = asyncio.create_task(enrich(client, domain))
        plan = await plan_pages(client, domain)
        pages: list[dict] = []
        seen_hashes: set[str] = set()
        fallback = False
        for url in plan.urls:
            r = plan.home if url == plan.home_url else await fetch_page(client, domain, url)
            if not r.usable:
                continue
            h = content_hash(r.text)
            if h in seen_hashes:  # SPA / catch-all routes serving the same document
                continue
            seen_hashes.add(h)
            fallback = fallback or r.via == "wayback"
            # Link to what was actually quoted: the archived copy when the live page failed.
            display = f"https://web.archive.org/web/2/{url}" if r.via == "wayback" else url
            pages.append({"url": url, "text": r.text, "via": r.via, "status_code": r.status_code, "display_url": display})
        try:
            enrichments = await asyncio.wait_for(enrich_task, timeout=20)
        except Exception as e:  # noqa: BLE001
            log.info("enrich failed for %s: %s", domain, e)
            enrichments = {}
    reachable = None if plan.home.outcome == "robots" else (plan.home.cached or plan.home.status_code is not None)
    return {
        "pages": pages,
        "pages_fetched": len(pages),
        "fallback_used": fallback,
        "reachable": reachable,
        "enrichments": enrichments,
        "raw_facts": [],
        "timings": {**state.get("timings", {}), "fetch": round(time.perf_counter() - t0, 2)},
    }


def fan_out_extract(state: ScanState):
    pages = state.get("pages") or []
    if not pages:
        return "ground_merge"
    return [Send("extract", ExtractInput(domain=state["domain"], url=p["url"], text=p["text"])) for p in pages]


# ---------------------------------------------------------------- extract (per page, fast model)
async def extract(inp: ExtractInput, config: RunnableConfig) -> dict:
    runnable = fast_llm().with_structured_output(FactList)
    messages = [
        ("system", EXTRACT_SYSTEM.format(categories=", ".join(FACT_CATEGORIES))),
        ("human", EXTRACT_USER.format(domain=inp["domain"], url=inp["url"], text=inp["text"])),
    ]
    # Deterministic backstop first: ownership / affiliation / founding phrases are too important to leave to sampling.
    signals = regex_signals(inp["text"], inp["url"])
    try:
        out: FactList = await call_llm(runnable, messages, _sem(config), config=config)
    except Exception as e:  # noqa: BLE001
        if is_rate_limit(e):
            # Quota exhausted: the scan must end as status=error (not cached), never as "done with no evidence".
            raise
        log.warning("extract failed for %s: %s", inp["url"], e)  # a malformed page/answer must not sink the scan
        return {"raw_facts": signals}
    facts = signals + [
        {
            "category": f.category if f.category in FACT_CATEGORIES else "other",
            "fact": f.fact.strip()[:300],
            "evidence_quote": f.evidence_quote.strip()[:400],
            "source_url": inp["url"],
            "confidence": float(f.confidence),
        }
        for f in (out.facts if out else [])
        if f.fact and f.evidence_quote
    ]
    return {"raw_facts": facts}


# ---------------------------------------------------------------- ground_merge (deterministic)
def ground_merge(state: ScanState) -> dict:
    pages = {p["url"]: p["text"] for p in state.get("pages") or []}
    display = {p["url"]: p.get("display_url") or p["url"] for p in state.get("pages") or []}
    seen: set[str] = set()
    facts: list[dict] = []
    for f in state.get("raw_facts") or []:
        key = normalize(f["fact"])
        if not key or key in seen:
            continue
        seen.add(key)
        g, url = ground_in_pages(f["evidence_quote"], f.get("source_url"), pages)
        if g != "none" and not numbers_present(normalize(f["fact"]), normalize(f["evidence_quote"])):
            g = "none"  # the paraphrase introduces a number the quote does not contain
        src = url or f.get("source_url")
        facts.append({**f, "grounding": g, "source_url": display.get(src, src)})
    # grounded first, then by confidence; cap
    facts.sort(key=lambda f: ({"exact": 0, "fuzzy": 1, "none": 2}[f["grounding"]], -f["confidence"]))
    facts = facts[:MAX_FACTS]
    for i, f in enumerate(facts, start=1):
        f["id"] = i
    return {"facts": facts}


# ---------------------------------------------------------------- enrich_facts (deterministic)
def enrich_facts(state: ScanState) -> dict:
    facts = list(state.get("facts") or [])
    e = state.get("enrichments") or {}
    next_id = len(facts) + 1
    rdap = e.get("rdap") or {}
    if rdap.get("ok") and rdap.get("registered"):
        facts.append(
            {
                "id": next_id,
                "category": "domain_record",
                "fact": f"Domain {state['domain']} was registered on {rdap['registered']} ({rdap.get('domain_age_years', '?')} years ago).",
                "evidence_quote": f"registration: {rdap['registered']}",
                "source_url": rdap.get("source"),
                "confidence": 1.0,
                "grounding": "record",
            }
        )
        next_id += 1
    wb = e.get("wayback") or {}
    if wb.get("ok") and wb.get("first_capture"):
        approx = bool(wb.get("approx"))
        facts.append(
            {
                "id": next_id,
                "category": "domain_record",
                "fact": (
                    f"Earliest Wayback Machine snapshot found: {wb['first_capture']} (approximate)."
                    if approx
                    else f"The website was first archived by the Wayback Machine on {wb['first_capture']}."
                ),
                "evidence_quote": f"{'earliest snapshot found' if approx else 'first capture'}: {wb['first_capture']}",
                "source_url": wb.get("source"),
                "confidence": 0.8 if approx else 1.0,
                "grounding": "record",
            }
        )
    return {"facts": facts}


# ---------------------------------------------------------------- judge (fast model, one call)
GROUNDED_STATES = ("exact", "fuzzy", "record")


def _grounded(facts: list[dict]) -> list[dict]:
    return [f for f in facts if f.get("grounding") in GROUNDED_STATES]


def _fact_lines(facts: list[dict], with_category: bool = True) -> str:
    lines = []
    for f in facts:
        cat = f" | {f['category']}" if with_category else ""
        lines.append(f"{f['id']}{cat} | {f['fact']} | \"{f['evidence_quote']}\" | {f.get('source_url') or ''}")
    return "\n".join(lines) if lines else "(none)"


async def judge(state: ScanState, config: RunnableConfig) -> dict:
    criteria = state.get("criteria") or []
    # Public-record facts (RDAP/Wayback) are appended last; keep them ahead of the cap.
    grounded = sorted(_grounded(state.get("facts") or []), key=lambda f: 0 if f.get("category") == "domain_record" else 1)[:MAX_JUDGE_FACTS]
    by_id = {f["id"]: f for f in grounded}
    if not criteria:
        return {"judgments": [], "verdicts": {}}
    if not grounded:
        return {
            "judgments": [{"criterion_key": c["key"], "verdict": "unknown", "fact_ids": [], "reasoning": "No verified facts available."} for c in criteria],
            "verdicts": {c["key"]: "unknown" for c in criteria},
        }
    e = state.get("enrichments") or {}
    records = []
    if (e.get("rdap") or {}).get("ok"):
        records.append(f"domain registered {e['rdap'].get('registered')}")
    if (e.get("wayback") or {}).get("ok"):
        records.append(f"first web archive capture {e['wayback'].get('first_capture')}")
    crit_lines = "\n".join(f"- {c['key']} (weight {c['weight']}, {c['polarity']}): {c['test']}" for c in criteria)
    messages = [
        ("system", JUDGE_SYSTEM),
        (
            "human",
            JUDGE_USER.format(
                name=state.get("company_name") or state["domain"],
                domain=state["domain"],
                pages=", ".join(p["url"] for p in state.get("pages") or []) or "(none)",
                records="; ".join(records) or "unknown",
                criteria=crit_lines,
                facts=_fact_lines(grounded),
            ),
        ),
    ]
    try:
        out: JudgmentList = await call_llm(fast_llm().with_structured_output(JudgmentList), messages, _sem(config), config=config)
        got = {j.criterion_key: j for j in out.judgments}
    except Exception as e:  # noqa: BLE001 - judging failure => everything unknown, never a guess
        if is_rate_limit(e):
            raise  # quota: fail the scan so it is retried later instead of caching "unknown everywhere"
        log.warning("judge failed for %s: %s", state["domain"], e)
        got = {}
    judgments: list[dict] = []
    verdicts: dict[str, str] = {}
    for c in criteria:
        j = got.get(c["key"])
        verdict, ids, reasoning = ("unknown", [], "Not judged.") if j is None else (j.verdict, [i for i in j.fact_ids if i in by_id], j.reasoning)
        # Hard rule: a met/not_met verdict must cite a grounded fact, or it is downgraded to unknown.
        if verdict != "unknown" and not ids:
            verdict, reasoning = "unknown", f"Downgraded: no verified fact cited. ({reasoning})"[:300]
        first = by_id.get(ids[0]) if ids else None
        judgments.append(
            {
                "criterion_key": c["key"],
                "verdict": verdict,
                "fact_ids": ids,
                "reasoning": reasoning[:300],
                "evidence_quote": first["evidence_quote"] if first else None,
                "source_url": first.get("source_url") if first else None,
                "grounding": first["grounding"] if first else "none",
            }
        )
        verdicts[c["key"]] = verdict
    return {"judgments": judgments, "verdicts": verdicts}


# ---------------------------------------------------------------- score (deterministic)
def score_node(state: ScanState) -> dict:
    return {"score": compute_score(state.get("criteria") or [], state.get("verdicts") or {})}


# ---------------------------------------------------------------- note (smart model)
_BIGNUM_RE = re.compile(r"\b(\d{2,}|million|billion|thousand|%)", re.I)


def _validate_note(out: OutreachNote, allowed: set[int], facts: list[dict]) -> str | None:
    ids = list(dict.fromkeys(out.fact_ids))
    if len(ids) != 2:
        return f"fact_ids must contain exactly two distinct ids, got {out.fact_ids}"
    bad = [i for i in ids if i not in allowed]
    if bad:
        return f"fact ids {bad} are not verified facts; use only ids from the list"
    cited_text = normalize(" ".join(f"{f['fact']} {f['evidence_quote']}" for f in facts if f["id"] in ids))
    for tok in _BIGNUM_RE.findall(_MARKER_RE.sub("", out.note)):
        if normalize(tok) not in cited_text.split() and tok != "%":
            return f"the note mentions '{tok}', which is not in the two cited facts; remove figures that are not in the facts"
    markers = {int(m) for m in _MARKER_RE.findall(out.note)}
    if set(ids) != markers:
        return f"the note must reference both facts inline with markers like [F{ids[0]}] and [F{ids[1]}] (found {sorted(markers)})"
    body = _MARKER_RE.sub("", out.note)
    sentences = [s for s in body.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    if not (3 <= len(sentences) <= 5):
        return f"note must be exactly 4 sentences, got {len(sentences)}"
    if "[" in body or "]" in body:
        return "note must not contain placeholders in brackets (only [F<id>] markers are allowed)"
    return None


def strip_markers(note: str | None) -> str | None:
    return _WS_MARK_RE.sub(" ", note).replace(" .", ".").replace(" ,", ",").strip() if note else note


async def note_node(state: ScanState, config: RunnableConfig) -> dict:
    grounded = _grounded(state.get("facts") or [])
    negative_keys = {c["key"] for c in state.get("criteria") or [] if c.get("polarity") == "negative"}
    red_flags = [j["criterion_key"] for j in state.get("judgments") or [] if j["verdict"] == "met" and j["criterion_key"] in negative_keys]
    if red_flags:
        # A present "avoid" criterion means this lead should not get a pitch at all.
        return {"note": None, "note_fact_ids": [], "note_status": "red_flag"}
    if len(grounded) < 2:
        return {"note": None, "note_fact_ids": [], "note_status": "skipped"}
    met = [j["criterion_key"] for j in state.get("judgments") or [] if j["verdict"] == "met"]
    cited = {i for j in state.get("judgments") or [] for i in j.get("fact_ids", [])}
    # Prefer facts the judge relied on, then the rest; keep the prompt short.
    ordered = sorted(grounded, key=lambda f: (0 if f["id"] in cited else 1, f["id"]))[:MAX_NOTE_FACTS]
    allowed = {f["id"] for f in ordered}
    feedback = ""
    for attempt in range(2):
        messages = [
            ("system", NOTE_SYSTEM),
            (
                "human",
                NOTE_USER.format(
                    icp_name=state.get("icp_name", "ICP"),
                    name=state.get("company_name") or state["domain"],
                    domain=state["domain"],
                    met=", ".join(met) or "(none yet)",
                    facts=_fact_lines(ordered, with_category=False),
                    feedback=feedback,
                ),
            ),
        ]
        try:
            out: OutreachNote = await call_llm(smart_llm().with_structured_output(OutreachNote), messages, _sem(config), config=config)
        except Exception as e:  # noqa: BLE001
            if is_rate_limit(e):
                raise
            log.warning("note generation failed: %s", e)
            return {"note": None, "note_fact_ids": [], "note_status": "unverified"}
        if out is None:
            feedback = "\nYour previous answer was empty. Return the note and fact_ids.\n"
            continue
        err = _validate_note(out, allowed, ordered)
        if err is None:
            return {"note": out.note.strip(), "note_fact_ids": list(dict.fromkeys(out.fact_ids)), "note_status": "ok"}
        feedback = f"\nYour previous answer was rejected: {err}. Fix it.\n"
        log.info("note attempt %d rejected: %s", attempt + 1, err)
    return {"note": None, "note_fact_ids": [], "note_status": "unverified"}
