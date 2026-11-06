import pytest

from laneroom import scorecard
from laneroom.agents import _round_shares, allocate
from laneroom.metrics import extract_metrics, fmt_value, row_numbers
from laneroom.tools import compute_change, get_page, lane_scorecard, parse_number, search_filings


def test_parse_number_and_row_numbers():
    assert parse_number("$(1,009.4)") == -1009.4
    assert row_numbers("Net earnings | $598,282 $570,886 $728,287") == [598282, 570886, 728287]
    assert row_numbers("Operating ratio | 75.2% | 73.4%") == [75.2, 73.4]


def test_compute_change():
    assert compute_change(12087.2, 11999.1)["pct"] == -0.7


@pytest.mark.parametrize("company,key,fy24,fy25", [
    ("J.B. Hunt", "revenue", 12087.2, 11999.1),
    ("J.B. Hunt", "op_cash_flow", 1483.16, 1678.27),
    ("C.H. Robinson", "revenue", 17724.96, 16232.76),
    ("C.H. Robinson", "net_income", 465.69, 587.08),
    ("Old Dominion", "op_income", 1544.0, 1361.05),
    ("Old Dominion", "operating_ratio", 73.4, 75.2),
    ("Armada", "revenue", 389.0, 412.6),
])
def test_quant_reads_filing_tables(company, key, fy24, fy25):
    m = {(x["company"], x["key"]): x for x in extract_metrics()}[(company, key)]
    assert m["fy2024"] == pytest.approx(fy24, abs=0.06) and m["fy2025"] == pytest.approx(fy25, abs=0.06)
    assert m["page"] > 0 and m["row_text"]
    assert m["synthetic"] == (company == "Armada")


def test_fmt_value():
    assert fmt_value(11999.1, "$M") == "$12.00B" and fmt_value(75.2, "%") == "75.2%" and fmt_value(2.3, "$/mi") == "$2.30/mi"


def test_scorecard_lanes_and_summary():
    assert set(scorecard.lanes()) == {"DAL-ATL", "LTL-NAT", "PEAK-NAT", "CHI-LAX"}
    assert scorecard.detect_lane("LTL national contract") == "LTL-NAT"
    assert scorecard.detect_lane("Peak season surge capacity") == "PEAK-NAT"
    s = scorecard.summary("DAL-ATL", "J.B. Hunt")
    assert s["tenders_offered"] == 10400 and 90 < s["acceptance_pct"] < 96 and len(s["rows"]) == 4
    rows = lane_scorecard("DAL-ATL", "jbht")
    assert len(rows) == 4 and all("accepted" in r["text"] for r in rows)


def test_allocation_respects_caps_and_floor():
    shares = _round_shares(allocate({"A": 0.9, "B": 0.3, "C": 0.5}, {"A": 60, "B": 60, "C": 25}, 10))
    assert sum(shares.values()) == 100 and shares["A"] <= 60 and shares["C"] <= 25 and shares["B"] >= 10


def test_search_returns_citations_for_requested_company():
    hits = search_filings("LTL service center network capacity", company="ODFL", k=3)
    assert hits and all(h["company"] == "Old Dominion" and h["page"] > 0 and h["chunk_id"] for h in hits)


def test_armada_evidence_is_flagged_synthetic():
    hits = search_filings("tractors trailers partner carriers", company="Armada", k=2)
    assert hits and all(h["synthetic"] for h in hits)


def test_get_page_text():
    assert "75.2%" in get_page("Old Dominion", 48)
