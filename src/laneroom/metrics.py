"""Quant agent's extraction layer.

1. Financial health: key FY2025 vs FY2024 figures read from each carrier's own 10-K tables (and from the
   synthetic Armada profile, flagged as such). Each spec names the page and row label; values are parsed
   from the indexed text at run time, so every number carries a page citation.
2. Lane service: tender acceptance, on-time %, rate per mile and claims % for the lane, from the
   (synthetic) shipper scorecard, with row citations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from filingsight import config as fs_config

from . import scorecard
from .tools import _docs_by_page, compute_change

_CELL_NUM = re.compile(r"\(?-?\$?\s?\d[\d,]*(?:\.\d+)?\)?")


@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    company: str
    page: int
    row: str  # line must start with this label
    unit: str  # "$M" or "%"
    scale: float = 1.0  # multiply to convert into the unit (thousands -> millions = 0.001)
    higher_is_better: bool = True
    idx_cur: int = 0  # position of the FY2025 value among the row's numbers (filers list the latest year first)
    idx_prev: int = 1


_K = 0.001  # 10-K tables are "in thousands"
SPECS: tuple[MetricSpec, ...] = (
    # J.B. Hunt: Consolidated Statements of Earnings p.44, Cash Flows p.46 (in thousands)
    MetricSpec("revenue", "Operating revenues", "J.B. Hunt", 44, "Total operating revenues |", "$M", _K),
    MetricSpec("op_income", "Operating income", "J.B. Hunt", 44, "Operating income |", "$M", _K),
    MetricSpec("net_income", "Net earnings", "J.B. Hunt", 44, "Net earnings |", "$M", _K),
    MetricSpec("op_cash_flow", "Operating cash flow", "J.B. Hunt", 46, "Net cash provided by operating activities |", "$M", _K),
    # C.H. Robinson: MD&A p.43 and Statements p.66 / p.68 (in thousands)
    MetricSpec("revenue", "Total revenues", "C.H. Robinson", 66, "Total revenues |", "$M", _K),
    MetricSpec("op_income", "Operating income", "C.H. Robinson", 43, "Operating income |", "$M", _K),
    MetricSpec("net_income", "Net income", "C.H. Robinson", 66, "Net income |", "$M", _K),
    MetricSpec("op_cash_flow", "Operating cash flow", "C.H. Robinson", 68, "Net cash provided by operating activities |", "$M", _K),
    # Old Dominion: Statements p.63 / p.67 (in thousands), operating ratio from MD&A p.48
    MetricSpec("revenue", "Revenue from operations", "Old Dominion", 63, "Revenue from operations |", "$M", _K),
    MetricSpec("op_income", "Operating income", "Old Dominion", 63, "Operating income |", "$M", _K),
    MetricSpec("net_income", "Net income", "Old Dominion", 63, "Net income |", "$M", _K),
    MetricSpec("op_cash_flow", "Operating cash flow", "Old Dominion", 67, "Net cash provided by operating activities |", "$M", _K),
    MetricSpec("operating_ratio", "Operating ratio", "Old Dominion", 48, "Operating ratio |", "%", higher_is_better=False),
    # Armada: SYNTHETIC self-reported profile p.5 (in millions)
    MetricSpec("revenue", "Revenue (self-reported)", "Armada", 5, "Revenue (in millions) |", "$M"),
    MetricSpec("op_income", "Operating income (self-reported)", "Armada", 5, "Operating income (in millions) |", "$M"),
    MetricSpec("op_cash_flow", "Operating cash flow (self-reported)", "Armada", 5,
               "Net cash provided by operating activities (in millions) |", "$M"),
    MetricSpec("operating_ratio", "Operating ratio (self-reported)", "Armada", 5, "Operating ratio |", "%", higher_is_better=False),
)


def row_numbers(line: str) -> list[float]:
    """Numbers in a table row after its label: '$598,282 $570,886' -> [598282, 570886]; '(1.3)' -> -1.3."""
    cells = line.split("|", 1)[1] if "|" in line else line
    out = []
    for raw in _CELL_NUM.findall(cells):
        digits = re.sub(r"[^\d.]", "", raw)
        if not digits or digits == ".":
            continue
        val = float(digits)
        out.append(-val if raw.strip().startswith("(") or "-" in raw else val)
    return out


def _find_row(spec: MetricSpec) -> tuple[str, dict] | None:
    for doc in _docs_by_page().get((spec.company, spec.page), []):
        for line in doc.page_content.split("\n"):
            if line.startswith(spec.row):
                meta = {"chunk_id": doc.metadata["chunk_id"], "page": spec.page, "row_text": line.strip(),
                        "item": doc.metadata.get("item", "")}
                return line, meta
    return None


def extract_metric(spec: MetricSpec) -> dict | None:
    found = _find_row(spec)
    if not found:
        return None
    line, meta = found
    nums = row_numbers(line)
    if len(nums) <= max(spec.idx_cur, spec.idx_prev):
        return None
    cur, prev = round(nums[spec.idx_cur] * spec.scale, 2), round(nums[spec.idx_prev] * spec.scale, 2)
    change = compute_change(prev, cur)
    improved = (cur > prev) == spec.higher_is_better
    return {
        "key": spec.key, "label": spec.label, "company": spec.company, "unit": spec.unit,
        "fy2025": cur, "fy2024": prev, "yoy_pct": change["pct"], "improved": improved,
        "synthetic": spec.company in fs_config.SYNTHETIC_COMPANIES, "source": "filing", **meta,
    }


def extract_metrics(companies: list[str] | None = None) -> list[dict]:
    out = []
    for spec in SPECS:
        if companies and spec.company not in companies:
            continue
        m = extract_metric(spec)
        if m:
            out.append(m)
    # Derived: operating margin = operating income / revenue (both cited rows)
    by = {(m["company"], m["key"]): m for m in out}
    for c in dict.fromkeys(m["company"] for m in out):
        rev, op = by.get((c, "revenue")), by.get((c, "op_income"))
        if rev and op and rev["fy2025"] and rev["fy2024"]:
            cur, prev = round(op["fy2025"] / rev["fy2025"] * 100, 1), round(op["fy2024"] / rev["fy2024"] * 100, 1)
            out.append({"key": "op_margin", "label": "Operating margin (derived)", "company": c, "unit": "%",
                        "fy2025": cur, "fy2024": prev, "yoy_pct": round(cur - prev, 1), "improved": cur > prev,
                        "synthetic": rev["synthetic"], "source": "derived", "page": op["page"], "item": op["item"],
                        "chunk_id": op["chunk_id"], "row_text": f"{op['row_text']}  ÷  {rev['row_text']}"})
    return out


LANE_KEYS = (("acceptance_pct", "Tender acceptance", "%", True), ("on_time_pct", "On-time", "%", True),
             ("rate_per_mile", "Rate per mile", "$/mi", False), ("claims_pct", "Claims", "%", False))


def lane_metrics(lane_id: str, carriers: list[str]) -> list[dict]:
    """Full-year 2025 scorecard figures per carrier on the lane, plus the Q4 (peak) acceptance."""
    out = []
    for c in carriers:
        s = scorecard.summary(lane_id, c)
        if s:
            out.append(s)
    return out


def fmt_value(value: float, unit: str) -> str:
    if unit == "$M":
        sign = "-" if value < 0 else ""
        v = abs(value)
        return f"{sign}${v / 1000:,.2f}B" if v >= 1000 else f"{sign}${v:,.1f}M"
    if unit == "%":
        return f"{value:,.1f}%"
    if unit == "$/mi":
        return f"${value:,.2f}/mi"
    if unit == "$":
        return f"${value:,.2f}"
    return f"{value:,}"
