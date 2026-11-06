import asyncio
import os
import sys
from pathlib import Path

import pytest

mcp = pytest.importorskip("mcp")


def test_mcp_server_lists_and_calls_tools():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    src = str(Path(__file__).resolve().parents[1] / "src")

    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "laneroom.mcp_server"],
                                       env={**os.environ, "PYTHONPATH": src})
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                names = {t.name for t in (await s.list_tools()).tools}
                res = await s.call_tool("compute_change", {"old": 100, "new": 150})
                rows = await s.call_tool("lane_scorecard", {"lane": "DAL-ATL", "carrier": "Armada"})
                return names, res.content[0].text, rows

    names, text, rows = asyncio.run(run())
    assert {"search_filings", "get_page", "list_companies", "lane_scorecard", "key_metrics", "compute_change"} <= names
    assert "50" in text
    assert "Armada" in str(rows.content)
