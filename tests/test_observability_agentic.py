from laneroom import agents, config, llm
from laneroom.graph import LaneRoom
from laneroom.observability import load_feedback, run_totals


def test_take_usage_resets_and_prices():
    llm._add_usage(1_000_000, 500_000)
    u = llm.take_usage()
    assert u["llm_calls"] == 1 and u["tokens_in"] == 1_000_000 and u["tokens_out"] == 500_000
    assert u["cost_usd"] == round(config.PRICE_IN_PER_M + 0.5 * config.PRICE_OUT_PER_M, 6)
    assert llm.take_usage()["llm_calls"] == 0


def test_trace_entries_carry_usage_and_totals_sum():
    trace = agents._trace("planner", "x", 0.0)["trace"]
    assert {"llm_calls", "tokens_in", "tokens_out", "cost_usd"} <= trace[0].keys()
    t = run_totals([{"ms": 10, "llm_calls": 1, "tokens_in": 5, "tokens_out": 7, "cost_usd": 0.1},
                    {"ms": 5, "llm_calls": 2, "tokens_in": 1, "tokens_out": 1, "cost_usd": 0.2}])
    assert t == {"ms": 15, "llm_calls": 3, "tokens_in": 6, "tokens_out": 8, "cost_usd": 0.3}


def test_offline_reformulation_keeps_company_and_topic_words():
    q = agents._reformulate({"company": "Old Dominion", "topic": "financial", "question": "How does Old Dominion fund its fleet?"},
                            {"mode": "offline"})
    assert q.startswith("Old Dominion 10-K") and "fleet" in q and "liquidity" in q


def test_weak_results_are_researched_again():
    t = {"company": "J.B. Hunt", "topic": "capacity", "question": "J.B. Hunt zzz qqq"}
    weak = [{"chunk_id": "a", "score": 0.1}]
    results, retried = agents._research_again({"mode": "offline"}, [(t, weak)])
    assert retried == 1
    hits = results[0][1]
    assert len(hits) >= 2 and hits[0]["score"] >= 0.5


def test_review_decisions_are_logged_for_regression_evals():
    room = LaneRoom()
    room.run("LTL national contract: ODFL vs CHRW", mode="offline")
    rows = load_feedback()
    assert rows and rows[-1]["action"] == "approve" and rows[-1]["question"].startswith("LTL national")
    assert (config.TRACE_DIR / "runs.jsonl").exists()
