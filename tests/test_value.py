"""Business value model: drivers add up, the award mix is honest (can be negative), assumptions move the result."""
from dataclasses import replace

from laneroom import scorecard, value


def _judge(lane_id: str, shares: dict[str, float]) -> dict:
    return {"allocation": [{"company": c, "share": s, "lane": scorecard.summary(lane_id, c)} for c, s in shares.items()]}


PLAN = {"lane_id": "DAL-ATL", "lane": "Dallas, TX to Atlanta, GA", "loads": 500}


def test_drivers_add_up_to_net_savings_and_roi():
    v = value.evaluate(PLAN, _judge("DAL-ATL", {"J.B. Hunt": 45, "C.H. Robinson": 20, "Armada": 15,
                                                "BlueGrace Logistics": 10, "Edge Logistics": 10}))
    assert v["annual_loads"] == 26000 and v["miles"] == 782  # real road miles from the committed OSRM geometry
    assert abs(sum(d["value"] for d in v["drivers"]) - v["run_cost"] - v["net_savings"]) < 1
    assert abs(v["roi_pct"] - v["net_savings"] / v["investment"] * 100) < 1e-6
    assert {d["key"] for d in v["drivers"]} == {"review", "backhaul", "onboarding", "mix"}
    assert v["synthetic"] is True


def test_award_mix_is_zero_for_an_even_split_and_negative_when_paying_for_service():
    carriers = scorecard.lanes()["DAL-ATL"]["carriers"]
    even = value.evaluate(PLAN, _judge("DAL-ATL", {c: 100 / len(carriers) for c in carriers}))
    assert abs(next(d for d in even["drivers"] if d["key"] == "mix")["value"]) < 1
    # all-in on the dearest, best-service carrier costs more than an even split: shown as a negative driver
    premium = value.evaluate(PLAN, _judge("DAL-ATL", {"J.B. Hunt": 60, **{c: 40 / (len(carriers) - 1) for c in carriers
                                                                          if c != "J.B. Hunt"}}))
    mix = next(d for d in premium["drivers"] if d["key"] == "mix")
    assert mix["value"] < 0 and "service premium" in mix["detail"]


def test_ltl_rates_are_not_compared_with_truckload_in_the_mix():
    plan = {"lane_id": "CHI-NWK", "lane": "Chicago, IL to Newark, NJ", "loads": 300}
    carriers = scorecard.lanes()["CHI-NWK"]["carriers"]
    v = value.evaluate(plan, _judge("CHI-NWK", {c: 100 / len(carriers) for c in carriers}))
    assert v["mix_excluded"] == ["Old Dominion"]


def test_assumptions_move_the_result():
    j = _judge("DAL-ATL", {"J.B. Hunt": 45, "C.H. Robinson": 20, "Armada": 15, "BlueGrace Logistics": 10,
                           "Edge Logistics": 10})
    base = value.evaluate(PLAN, j)
    no_backhaul = value.evaluate(PLAN, j, replace(value.Assumptions(), backhaul_share_pct=0))
    assert no_backhaul["net_savings"] < base["net_savings"]
    pricier = value.evaluate(PLAN, j, replace(value.Assumptions(), platform_cost_per_year=100000))
    assert pricier["roi_pct"] < base["roi_pct"]
    assert value.weekly_loads("DAL-ATL", None) > 0  # falls back to the lane's scorecard volume
