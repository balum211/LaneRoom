from laneroom.agents import verify_claim
from laneroom.graph import LaneRoom

EV = {
    "S01": {"id": "S01", "company": "J.B. Hunt", "page": 0, "source": "scorecard",
            "text": "Dallas, TX to Atlanta, GA (Dry van truckload), Q1 2025: J.B. Hunt accepted 2,460 of 2,600 tenders "
                    "(94.6% acceptance), on-time 96.7%, rate $2.33 per mile, claims 0.14%."},
    "E1": {"id": "E1", "company": "Old Dominion", "page": 48, "text": "Our operating ratio was 75.2% in 2025."},
}


def test_verifier_accepts_supported_claims_from_rows_and_pages():
    assert verify_claim({"company": "J.B. Hunt", "text": "J.B. Hunt accepted 2,460 of 2,600 tenders.",
                         "quote": "accepted 2,460 of 2,600 tenders", "evidence_id": "S01"}, EV)[0]
    assert verify_claim({"company": "Old Dominion", "text": "ODFL ran a 75.2% operating ratio.",
                         "quote": "operating ratio was 75.2%", "evidence_id": "E1"}, EV)[0]


def test_verifier_rejects_wrong_number_quote_company_and_id():
    assert not verify_claim({"company": "J.B. Hunt", "text": "Rate was $1.15 per mile.", "quote": "", "evidence_id": "S01"}, EV)[0]
    assert not verify_claim({"company": "J.B. Hunt", "text": "x", "quote": "accepted 100% of tenders", "evidence_id": "S01"}, EV)[0]
    assert not verify_claim({"company": "Armada", "text": "x", "quote": "", "evidence_id": "S01"}, EV)[0]
    assert not verify_claim({"company": "J.B. Hunt", "text": "x", "quote": "", "evidence_id": "S99"}, EV)[0]


def test_committee_end_to_end_with_stress_test_and_human_review():
    room = LaneRoom()
    cfg = room.new_thread()
    nodes = [n for n, _ in room.start("Dallas→Atlanta dry van: allocate 500 weekly loads", cfg, mode="offline", inject_faulty=True)]
    assert {"planner", "researcher", "quant", "cost", "service", "rebuttal", "verifier", "revise", "judge", "writer"} <= set(nodes)
    assert room.waiting_for_review(cfg)  # graph paused for the human
    s = room.state(cfg)
    injected = [c for c in s["cost_claims"] if c["by"] == "stress test"]
    assert injected and injected[0]["status"] == "dropped"
    final = [c for c in s["cost_claims"] + s["service_claims"] if c["status"] != "dropped"]
    assert final and all(c["status"] == "supported" for c in final)
    alloc = {r["company"]: r for r in s["judge"]["allocation"]}
    assert set(alloc) == {"J.B. Hunt", "C.H. Robinson", "Armada"}
    assert sum(r["share"] for r in alloc.values()) == 100
    assert sum(r["loads"] for r in alloc.values()) == 500
    assert alloc["Armada"]["share"] <= 25  # synthetic-evidence cap
    assert max(r["share"] for r in alloc.values()) <= 60  # no single-carrier dependence
    assert "[S" in s["memo"] and "[E" in s["memo"] and "SYNTHETIC" in s["memo"]
    # reviewer asks for a change, then approves
    list(room.resume({"action": "revise", "notes": "lead with peak-season risk"}, cfg))
    assert "lead with peak-season risk" in room.state(cfg)["memo"]
    list(room.resume({"action": "approve"}, cfg))
    assert room.state(cfg)["final"]


def test_mandate_changes_the_allocation():
    room = LaneRoom()
    cost = room.run("Peak season surge capacity", mode="offline", profile={"mandate": "cost-first"})
    service = room.run("Peak season surge capacity", mode="offline", profile={"mandate": "service-first"})

    def share(s, c):
        return next(r["share"] for r in s["judge"]["allocation"] if r["company"] == c)

    assert share(service, "Old Dominion") > share(cost, "Old Dominion")


def test_guard_refuses_out_of_scope_carrier():
    s = LaneRoom().run("Should we give the lane to Schneider?", mode="offline")
    assert s["refused"] and "Schneider" in s["memo"]


def test_follow_up_reuses_thread_and_switches_lane():
    room = LaneRoom()
    cfg = room.new_thread()
    list(room.start("Dallas to Atlanta dry van tender", cfg, mode="offline"))
    list(room.resume({"action": "follow_up", "question": "LTL national contract: ODFL vs CHRW"}, cfg))
    s = room.state(cfg)
    assert s["plan"]["lane_id"] == "LTL-NAT" and s["plan"]["companies"] == ["C.H. Robinson", "Old Dominion"]
