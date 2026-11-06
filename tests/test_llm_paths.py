"""LLM-mode agents with a fake chat model: JSON parsing, citation checks and fallbacks."""
import json

import pytest

from laneroom import agents, config
from laneroom.llm import parse_json


def test_parse_json_tolerates_fences_and_chatter():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Sure! Here it is: {"claims": []} hope that helps') == {"claims": []}


@pytest.fixture
def fake_llm(monkeypatch):
    replies = {}

    def fake_chat(system, user, temperature=0.2):
        for key, reply in replies.items():
            if key in system:
                return reply
        raise RuntimeError("no fake reply")

    import laneroom.llm as llm_mod

    monkeypatch.setattr(llm_mod, "chat", fake_chat)
    monkeypatch.setattr(config, "llm_enabled", lambda mode=None: True)
    return replies


def _state():
    ev = [{"id": "E1", "company": "Old Dominion", "page": 48, "item": "7", "item_title": "MD&A", "topic": "financial",
           "text": "Our operating ratio was 75.2% in 2025, and revenue per hundredweight increased 3.9%.", "score": 0.9}]
    return {"question": "LTL contract?", "evidence": ev, "lane_metrics": [],
            "plan": {"companies": ["Old Dominion"], "lane": "National LTL contract", "mode": "LTL", "lane_id": "LTL-NAT"},
            "profile": {"mandate": "balanced"}}


def test_llm_claims_are_verified_and_bad_ones_rejected(fake_llm):
    fake_llm["Cost advocate"] = json.dumps({"claims": [
        {"company": "Old Dominion", "stance": "for", "text": "ODFL ran a 75.2% operating ratio.", "evidence_id": "E1",
         "quote": "operating ratio was 75.2%"},
        {"company": "Old Dominion", "stance": "for", "text": "Revenue per hundredweight rose 9.9%.", "evidence_id": "E1",
         "quote": "increased 9.9%"}]})
    fake_llm["fact-checker"] = json.dumps({"results": [{"id": "C1", "supported": True}]})
    state = _state()
    state.update(agents.cost_advocate(state))
    state["service_claims"] = []
    out = agents.verifier(state)
    statuses = [c["status"] for c in out["cost_claims"]]
    assert statuses == ["supported", "unsupported"]
    assert all(c["by"] == "llm" for c in out["cost_claims"])


def test_llm_failure_falls_back_to_offline(fake_llm):
    state = _state()
    out = agents.service_advocate(state)  # no fake reply for the Resilience advocate -> exception -> offline
    assert "offline" in out["trace"][0]["summary"]
