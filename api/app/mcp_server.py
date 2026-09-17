"""Local MCP server (stdio, mcp 2.x MCPServer) exposing the scanner to agents like Claude Desktop / Claude Code.

Run:  cd api && uv run --group mcp python -m app.mcp_server
Config (Claude Desktop / claude_desktop_config.json):
  {"mcpServers": {"icp-scanner": {"command": "uv", "args": ["run", "--group", "mcp", "--directory", "/abs/path/api", "python", "-m", "app.mcp_server"]}}}
"""

from __future__ import annotations

import warnings

from mcp.server.mcpserver import MCPServer
from sqlalchemy import select

from app.db import ensure_schema, get_session_factory
from app.graph.run import run_scan
from app.models import Company, IcpProfile
from app.presets import PRESET_ALIASES
from app.services.dedupe import normalize_domain

warnings.filterwarnings("ignore", message=".*fixed sampling defaults.*")

mcp = MCPServer("icp-signal-scanner", instructions="Scan a company's public website against an ICP and return evidence-grounded criterion verdicts.")


@mcp.tool()
async def list_icps() -> list[dict]:
    """List ICP profiles (id, name, description, compiled criteria)."""
    await ensure_schema()
    async with get_session_factory()() as db:
        rows = (await db.scalars(select(IcpProfile).order_by(IcpProfile.id))).all()
        return [{"id": r.id, "name": r.name, "description": r.description_text, "criteria": r.criteria} for r in rows]


@mcp.tool()
async def scan_company(domain: str, icp: str = "buybox", force: bool = False) -> dict:
    """Scan one company domain against an ICP ('buybox', 'sales', a profile name, or a numeric id).
    Returns score, coverage, per-criterion verdicts with verbatim source-linked quotes, verified facts and an outreach note.
    Cached for 7 days per (domain, ICP) unless force=True. Takes ~30-60s when fresh."""
    await ensure_schema()
    dom = normalize_domain(domain)
    if not dom:
        return {"error": f"not a valid domain: {domain!r}"}
    async with get_session_factory()() as db:
        company = (await db.scalars(select(Company).where(Company.domain == dom))).first()
        if company is None:
            company = Company(domain=dom, name=dom, source="mcp")
            db.add(company)
            await db.commit()
            await db.refresh(company)
        prof = None
        if icp.isdigit():
            prof = await db.get(IcpProfile, int(icp))
        if prof is None:
            prof = (await db.scalars(select(IcpProfile).where(IcpProfile.name == PRESET_ALIASES.get(icp, icp)))).first()
        if prof is None:
            return {"error": f"unknown ICP {icp!r}; try 'buybox' or 'sales'"}
        cid, iid = company.id, prof.id
    d = await run_scan(cid, iid, force=force)
    d.pop("timings", None)
    return d


if __name__ == "__main__":
    mcp.run(transport="stdio")
