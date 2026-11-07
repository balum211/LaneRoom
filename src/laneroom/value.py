"""Business value of the AI tender committee for one lane: ROI, net savings, payback and the benefits behind them.

Where the value comes from (each driver is a line in the result, with its own editable assumption):

1. **Review time** - a manual lane review means procurement and legal reading carrier 10-Ks and building the case,
   which takes weeks of elapsed time. The committee does the reading, maths and fact-checking in about a minute and
   leaves a person to review and approve.
2. **Backhaul and spot tenders decided in minutes** - backhaul and spot offers expire in minutes to hours. A slow
   process misses most of them; the committee can evaluate a carrier the same hour, so more discounted loads are won.
3. **New carriers onboarded fast** - adding a carrier to the comparison is one more document, not a new project, so
   the shipper can keep more qualified carriers bidding, which puts pressure on rates.
4. **Award mix (landed cost)** - the committee's split vs. an even split across the lane's carriers. A quoted rate is
   not what a load costs: rejected tenders go to the spot market at a premium, plus cargo claims and late
   deliveries. This driver can be NEGATIVE: a balanced or service-first mandate buys reliability, and that premium is
   shown as a cost, not hidden.
5. **Fewer errors and less bias** - every claim cites a 10-K page or scorecard row and a Verifier rejects unsupported
   ones. This is reported as quality (verified claims, avoided late and spot loads), not as dollars.

All carrier figures come from the SYNTHETIC lane scorecard, so every result is illustrative: the method is real,
the numbers are demo data. Every assumption is a field of `Assumptions` and can be changed in the app.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields

from . import maps, scorecard

WEEKS = 52


@dataclass
class Assumptions:
    # review effort
    runs_per_year: int = 12                 # lane re-awards / reviews per year (monthly)
    manual_review_hours: float = 40.0       # procurement + legal hours per manual review (10-K reading, model, memo)
    manual_cycle_days: float = 30.0         # elapsed calendar days for a manual review
    ai_review_hours: float = 1.5            # human review and approval time with the committee
    analyst_rate: float = 85.0              # USD per fully loaded hour
    # backhaul / spot speed
    backhaul_share_pct: float = 10.0        # share of the lane's loads offered as backhaul / spot opportunities
    backhaul_discount_pct: float = 15.0     # discount vs contract linehaul on a backhaul load
    capture_manual_pct: float = 30.0        # opportunities a days-long process still catches in time
    capture_ai_pct: float = 80.0            # opportunities caught when a decision takes minutes
    # carrier onboarding
    competition_saving_pct: float = 1.0     # rate pressure on contract linehaul from keeping more qualified carriers bidding
    # landed cost
    spot_premium_pct: float = 20.0          # spot rate vs the lane's average contract rate, when a tender is rejected
    late_cost_per_load: float = 250.0       # expediting, re-delivery and retailer on-time penalties per late load
    network_haul_miles: float = 650.0       # average length of haul for network lanes (LTL, peak)
    # cost of running the committee
    platform_cost_per_year: float = 25000.0  # subscription, integration, hosting and support allocated to this lane
    llm_cost_per_run: float = 0.05          # LLM tokens per run (0 with offline agents)


LABELS = {
    "runs_per_year": "Lane reviews per year", "manual_review_hours": "Manual review hours (procurement + legal)",
    "manual_cycle_days": "Manual review elapsed days", "ai_review_hours": "Human review hours with the committee",
    "analyst_rate": "Analyst cost per hour ($)", "backhaul_share_pct": "Backhaul / spot opportunities (% of loads)",
    "backhaul_discount_pct": "Backhaul discount (%)", "capture_manual_pct": "Opportunities caught manually (%)",
    "capture_ai_pct": "Opportunities caught with the committee (%)",
    "competition_saving_pct": "Rate pressure from more carriers bidding (%)",
    "spot_premium_pct": "Spot premium on rejected tenders (%)", "late_cost_per_load": "Cost of a late load ($)",
    "network_haul_miles": "Average haul for network lanes (mi)", "platform_cost_per_year": "Platform cost per year ($)",
    "llm_cost_per_run": "LLM cost per run ($)",
}
assert set(LABELS) == {f.name for f in fields(Assumptions)}


def lane_miles(lane_id: str, a: Assumptions) -> float:
    routes = maps.LANE_ROUTES.get(lane_id, [])
    if len(routes) == 1:
        road = maps.road_leg(*routes[0])
        return float(road["miles"]) if road else float(maps.miles(*routes[0]))
    return a.network_haul_miles


def weekly_loads(lane_id: str, plan_loads: int | None) -> int:
    """Loads per week: the request's number, else the lane's 2025 tender volume from the scorecard."""
    if plan_loads:
        return int(plan_loads)
    offered = sum(r["tenders_offered"] for r in scorecard.lane_rows(lane_id))
    return max(1, round(offered / WEEKS))


def landed_cost(m: dict, miles: float, spot_rate: float, a: Assumptions) -> float:
    """Expected cost of one load given to this carrier: rejected tenders go to spot, plus claims and late loads."""
    acc = m["acceptance_pct"] / 100
    linehaul = miles * (acc * m["rate_per_mile"] + (1 - acc) * spot_rate)
    return linehaul * (1 + m["claims_pct"] / 100) + (1 - m["on_time_pct"] / 100) * a.late_cost_per_load


def _blend(shares: dict[str, float], metrics: dict[str, dict], cost: dict[str, float], spot_load: float) -> dict:
    used = sum(shares.values())
    w = lambda k: sum(s * metrics[c][k] for c, s in shares.items()) / (used or 1)  # noqa: E731
    return {"cost_per_load": sum(s / 100 * cost[c] for c, s in shares.items()) + max(0.0, 100 - used) / 100 * spot_load,
            "contract_rate": w("rate_per_mile"), "acceptance_pct": w("acceptance_pct"), "on_time_pct": w("on_time_pct"),
            "claims_pct": w("claims_pct"), "max_share": max(shares.values() or [0])}


def evaluate(plan: dict, judge: dict, a: Assumptions | None = None, run_seconds: float | None = None) -> dict:
    """Business value of the committee's award for one lane (all money in USD per year)."""
    a = a or Assumptions()
    lane_id = plan.get("lane_id", "")
    metrics = {}
    for r in judge.get("allocation", []):
        m = r.get("lane") or scorecard.summary(lane_id, r["company"])
        if m:
            metrics[r["company"]] = m
    if not metrics:
        return {}
    miles = lane_miles(lane_id, a)
    loads_wk = weekly_loads(lane_id, plan.get("loads"))
    annual_loads = loads_wk * WEEKS
    avg_rate = sum(m["rate_per_mile"] for m in metrics.values()) / len(metrics)
    spot_rate = avg_rate * (1 + a.spot_premium_pct / 100)
    cost = {c: landed_cost(m, miles, spot_rate, a) for c, m in metrics.items()}
    spot_load = miles * spot_rate * 1.004 + 0.12 * a.late_cost_per_load  # spot capacity: ~88% on time, small claims

    shares = {r["company"]: r["share"] for r in judge.get("allocation", []) if r["company"] in metrics}
    ai = _blend(shares, metrics, cost, spot_load)
    even = _blend({c: 100 / len(metrics) for c in metrics}, metrics, cost, spot_load)
    # The award-mix driver only compares like with like: an LTL carrier's rate per mile (a share of a trailer) is not
    # the cost of a truckload, so carriers priced far from the lane's median rate are left out of that comparison.
    rates = sorted(m["rate_per_mile"] for m in metrics.values())
    median = rates[len(rates) // 2]
    comparable = [c for c, m in metrics.items() if 0.6 * median <= m["rate_per_mile"] <= 1.6 * median]
    excluded = [c for c in metrics if c not in comparable]
    cmp_shares = {c: shares.get(c, 0.0) for c in comparable}
    cmp_total = sum(cmp_shares.values())
    if cmp_total > 0 and len(comparable) > 1:
        mix_ai = _blend({c: s / cmp_total * 100 for c, s in cmp_shares.items()}, metrics, cost, spot_load)
        mix_even = _blend({c: 100 / len(comparable) for c in comparable}, metrics, cost, spot_load)
        mix_loads = annual_loads * cmp_total / 100
        mix_value = (mix_even["cost_per_load"] - mix_ai["cost_per_load"]) * mix_loads
    else:
        mix_value = 0.0
    linehaul_spend = annual_loads * miles * ai["contract_rate"]

    hours_saved = a.runs_per_year * (a.manual_review_hours - a.ai_review_hours)
    drivers = [
        {"key": "review", "name": "Review time (procurement + legal)", "value": hours_saved * a.analyst_rate,
         "detail": f"{hours_saved:,.0f} hours a year; {a.manual_cycle_days:.0f} days → minutes per review"},
        {"key": "backhaul", "name": "Backhaul / spot tenders decided in minutes",
         "value": annual_loads * a.backhaul_share_pct / 100 * (a.capture_ai_pct - a.capture_manual_pct) / 100
         * miles * ai["contract_rate"] * a.backhaul_discount_pct / 100,
         "detail": f"{annual_loads * a.backhaul_share_pct / 100 * (a.capture_ai_pct - a.capture_manual_pct) / 100:,.0f} "
                   f"more discounted loads caught a year"},
        {"key": "onboarding", "name": "New carriers onboarded fast (more bidders)",
         "value": linehaul_spend * a.competition_saving_pct / 100,
         "detail": f"{a.competition_saving_pct:g}% rate pressure on ${linehaul_spend / 1e6:,.1f}M contract linehaul"},
        {"key": "mix", "name": "Award mix vs an even split (landed cost)",
         "value": mix_value,
         "detail": ("lower landed cost per load" if mix_value >= 0
                    else "service premium: the mandate buys higher acceptance and on-time")
         + (f"; {', '.join(excluded)} left out (rate per mile not comparable to truckload)" if excluded else "")},
    ]
    gross = sum(d["value"] for d in drivers)
    run_cost = a.platform_cost_per_year + a.runs_per_year * a.llm_cost_per_run
    net = gross - run_cost
    invest = run_cost + a.runs_per_year * a.ai_review_hours * a.analyst_rate
    return {
        "lane_id": lane_id, "lane": plan.get("lane", ""), "miles": miles, "loads_per_week": loads_wk,
        "annual_loads": annual_loads, "linehaul_spend": linehaul_spend, "spot_rate": spot_rate,
        "drivers": drivers, "gross_benefit": gross, "run_cost": run_cost, "net_savings": net,
        "net_savings_pct": net / (even["cost_per_load"] * annual_loads) * 100,
        "roi_pct": net / invest * 100 if invest else 0.0, "investment": invest,
        "payback_days": invest / (gross / 365) if gross > 0 else None,
        "committee": ai, "even_split": even, "mix_excluded": excluded,
        "benefits": {
            "acceptance_uplift": ai["acceptance_pct"] - even["acceptance_pct"],
            "on_time_uplift": ai["on_time_pct"] - even["on_time_pct"],
            "late_loads_avoided": (ai["on_time_pct"] - even["on_time_pct"]) / 100 * annual_loads,
            "spot_loads_avoided": (ai["acceptance_pct"] - even["acceptance_pct"]) / 100 * annual_loads,
            "max_share": ai["max_share"], "hours_saved": hours_saved,
            "cycle": f"{run_seconds:.0f} s" if run_seconds else "< 1 min",
            "manual_cycle": f"{a.manual_cycle_days:.0f} days",
        },
        "assumptions": asdict(a), "synthetic": True,
    }


def headline(v: dict) -> str:
    return (f"Net savings ${v['net_savings']:,.0f} a year · ROI {v['roi_pct']:,.0f}% · payback "
            f"{v['payback_days']:.0f} days" if v.get("payback_days") is not None else
            f"Net savings ${v['net_savings']:,.0f} a year · ROI {v['roi_pct']:,.0f}%")
