"""LaneRoom's carrier knowledge base as an MCP server.

Exposes the same tools the Researcher and Quant agents use, so any MCP client (Claude Desktop, Cursor,
the MCP Inspector, another agent) can search the carrier 10-Ks and the lane scorecard with citations.

Run:  python -m laneroom.mcp_server          (stdio transport)
Test: npx @modelcontextprotocol/inspector python -m laneroom.mcp_server
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make `src/` importable when run as a file

from mcp.server.fastmcp import FastMCP  # noqa: E402

from laneroom import tools  # noqa: E402
from laneroom.metrics import extract_metrics  # noqa: E402

mcp = FastMCP("laneroom-carriers")


@mcp.tool()
def search_filings(query: str, company: str | None = None, k: int = 5) -> list[dict]:
    """Search the J.B. Hunt, C.H. Robinson and Old Dominion FY2025 10-Ks and the SYNTHETIC profiles of the private providers (Armada, Edge Logistics, First Star, BlueGrace Logistics).
    Returns passages with provider, page, 10-K Item and text.

    Args:
        query: what to look for, e.g. "intermodal capacity" or "LTL on-time service".
        company: optional filter: "J.B. Hunt", "C.H. Robinson", "Old Dominion", "Armada", "Edge Logistics", "First Star" or "BlueGrace Logistics" (tickers work too).
        k: number of passages (1-10).
    """
    k = max(1, min(int(k), 10))
    return [{key: e[key] for key in ("chunk_id", "company", "page", "item", "item_title", "header", "text", "score", "synthetic")}
            for e in tools.search_filings(query, company=company, k=k)]


@mcp.tool()
def get_page(company: str, page: int) -> str:
    """Return the full text of one document page, e.g. company="Old Dominion", page=48."""
    return tools.get_page(company, page) or f"No indexed text for {company} p.{page}."


@mcp.tool()
def list_companies() -> list[dict]:
    """List the providers in the knowledge base, their documents and whether the document is synthetic."""
    return tools.list_companies()


@mcp.tool()
def lane_scorecard(lane: str, carrier: str | None = None) -> list[dict]:
    """Rows of the SYNTHETIC shipper scorecard: tenders offered/accepted, on-time %, rate per mile, claims %.

    Args:
        lane: DAL-ATL, LTL-NAT, PEAK-NAT, CHI-LAX, or a description such as "Dallas to Atlanta dry van".
        carrier: optional provider filter.
    """
    return [{k: e[k] for k in ("row", "company", "item_title", "text")} for e in tools.lane_scorecard(lane, carrier)]


@mcp.tool()
def key_metrics(company: str | None = None) -> list[dict]:
    """FY2025 vs FY2024 financial figures read from each provider's tables, with page citations."""
    rows = extract_metrics([tools.canonical_company(company)] if company else None)
    return [{k: m[k] for k in ("company", "label", "unit", "fy2024", "fy2025", "yoy_pct", "page", "synthetic")} for m in rows]


@mcp.tool()
def compute_change(old: float, new: float) -> dict:
    """Absolute and percent change between two values (for year-over-year math)."""
    return tools.compute_change(old, new)


if __name__ == "__main__":
    mcp.run()
