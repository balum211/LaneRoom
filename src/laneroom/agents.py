"""The LaneRoom agents. Each node reads and writes the shared LangGraph state.

Every agent has two implementations:
* LLM mode (when NEBIUS_API_KEY or OPENAI_API_KEY is set): the chat model plans, argues and writes.
* Offline mode: deterministic agents that need no key. The demo, the tests and CI all run end to end
  with no API cost, and any LLM failure falls back to these.

Evidence ids: ``E#`` = a 10-K (or synthetic Armada profile) passage with a page; ``S##`` = a row of the
synthetic shipper scorecard. Claims cite one id each and the Verifier checks them against it.
"""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from filingsight.chunking import split_units
from filingsight.config import companies_in

from . import config, prompts, scorecard
from .guardrails import check_input, check_output
from .memory import MemoryStore
from .metrics import extract_metrics, fmt_value, lane_metrics
from .tools import search_filings

TOPICS = (
    ("capacity", "capacity, fleet size, tractors, trailers, containers, terminals, service centers and network reach"),
    ("cost", "pricing, rate per mile, revenue per load, cost structure, purchased transportation and fuel surcharge"),
    ("financial", "financial health, operating income, operating ratio, cash flow, liquidity and debt"),
    ("service", "service quality, on-time delivery, cargo claims, customer service, technology and tender acceptance"),
    ("risk", "risk factors including driver shortage, insurance and claims, customer concentration and freight cycle"),
)
SIDES = ("cost", "service")
SIDE_TITLES = {"cost": "Cost advocate", "service": "Resilience advocate"}
PREFIX = {"cost": "C", "service": "R"}

_COST = re.compile(r"\b(pric\w*|rates?|cost\w*|efficien\w*|productiv\w*|lower\w*|saving\w*|scale|asset[- ]light|"
                   r"flexib\w*|revenue per \w+|yield\w*|margin\w*|competitive\w*|technolog\w*|automat\w*|procure\w*|"
                   r"optimi\w*|variable|purchased transportation|density|utiliz\w*)\b", re.I)
_SERVICE = re.compile(r"\b(on-time|service\w*|reliab\w*|capacity|safety|quality|claims?|customers?|terminals?|"
                      r"service centers?|fleet|invest\w*|dedicated|network|equipment|trailers|tractors|containers|"
                      r"doors|cash|liquidity|balance sheet|record|improv\w*|increas\w*|grew|growth|strong\w*)\b", re.I)
_RISK = re.compile(r"\b(shortage\w*|declin\w*|decreas\w*|loss(es)?|risks?|advers\w*|concentrat\w*|insufficient|"
                   r"volatil\w*|unable|litigation|accidents?|cyber\w*|disrupt\w*|fail\w*|limit\w*|lower|weak\w*|"
                   r"self-insured|unaudited|not audited|relied|fell|drawn)\b", re.I)
_HEDGE = re.compile(r"\b(could|might|may|if we|cannot|no assurance)\b", re.I)
_JUNK = re.compile(r"(for more information|see (the )?(section|note|part|item)|refer to|incorporated (herein )?by reference|"
                   r"forward-looking statements|table of contents|synthetic profile|not an sec filing)", re.I)
_CONNECTOR = re.compile(r"^(further|additionally|in addition|however|accordingly|as a result|these|this|such|also|moreover)\b", re.I)
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_LOADS = re.compile(r"(?<![A-Za-z\d])(\d[\d,]*)\s*(?:weekly\s+|per\s+week\s+)?(?:loads|shipments)", re.I)


def _faulty_text(company: str) -> str:
    return f"{company} accepted 100% of tenders at $1.15 per mile on this lane in every quarter of 2025, so it should take all loads."


# ---------------------------------------------------------------- helpers
def _use_llm(state: dict) -> bool:
    return config.llm_enabled(state.get("mode"))


def _trace(node: str, summary: str, t0: float, **extra) -> dict:
    from .llm import take_usage

    entry = {"node": node, "summary": summary, "ms": round((time.perf_counter() - t0) * 1000), **take_usage(), **extra}
    return {"trace": [entry]}


def _norm(text: str) -> str:
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def _evidence_map(state: dict) -> dict[str, dict]:
    return {e["id"]: e for e in state.get("evidence", [])}


def cite_label(e: dict) -> str:
    if e.get("source") == "scorecard":
        return f"Synthetic shipper scorecard, row {e['id']} ({e['item_title']})"
    doc = "Armada profile (SYNTHETIC, self-reported)" if e.get("synthetic") else f"{e['company']} 10-K FY{config.FISCAL_YEAR}"
    return f"{doc}, Item {e['item']} {e['item_title']}, p.{e['page']}"


def _format_evidence(evidence: list[dict], max_chars: int = 800) -> str:
    return "\n\n".join(f"[{e['id']}] {e['company']} | {cite_label(e)}\n{e['text'][:max_chars]}" for e in evidence)


def _companies(state: dict) -> list[str]:
    return state.get("plan", {}).get("companies") or list(config.COMPANIES)


def _short(text: str, n: int = 140) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"


def _all_claims(state: dict) -> list[dict]:
    return state.get("cost_claims", []) + state.get("service_claims", [])


# ---------------------------------------------------------------- guard
def input_guard(state: dict) -> dict:
    t0 = time.perf_counter()
    result = check_input(state.get("question", ""))
    user = MemoryStore().get_user(state.get("user_id", "default"))
    update = {"guard": result, "refused": not result["allowed"], "refusal_reason": result["reason"],
              "profile": {**user["profile"], **(state.get("profile") or {})}, "past_memos": user["memos"][-3:],
              "attempts": 0, "review": {}, "final": False}
    summary = "Request allowed" if result["allowed"] else f"Blocked: {result['reason']}"
    if result["notes"]:
        summary += " · " + " ".join(result["notes"])
    return {**update, **_trace("guard", summary, t0)}


# ---------------------------------------------------------------- planner
def _offline_plan(question: str, companies: list[str]) -> list[dict]:
    topics = []
    for key, desc in TOPICS[: config.MAX_TOPICS]:
        for c in companies:
            topics.append({"topic": key, "company": c, "question": f"{c} {desc}"})
    return topics


def plan_lane(question: str) -> dict:
    """Which lane, which providers and how many loads the request is about."""
    lane_id = scorecard.detect_lane(question)
    lane = scorecard.lanes()[lane_id]
    named = companies_in(question)
    companies = named or list(lane["carriers"])
    if len(named) == 1:
        # "Should Armada keep a share of the lane?" is a question about the split, so every carrier on the
        # lane stays in the comparison (plus the named one if it has no history there).
        companies = list(lane["carriers"]) + [c for c in named if c not in lane["carriers"]]
    m = _LOADS.search(question)
    loads = int(m.group(1).replace(",", "")) if m else None
    off_lane = [c for c in companies if c not in lane["carriers"]]
    return {"lane_id": lane_id, "lane": lane["lane"], "mode": lane["mode"], "companies": companies,
            "lane_carriers": list(lane["carriers"]), "off_lane": off_lane, "loads": loads,
            "is_comparison": len(companies) > 1}


def planner(state: dict) -> dict:
    t0 = time.perf_counter()
    from .tools import get_index

    get_index()  # warm the index once before the parallel agents start
    q = state["question"]
    plan = plan_lane(q)
    companies = plan["companies"]
    topics, how = None, "offline"
    if _use_llm(state):
        try:
            data = prompts_call_planner(q, plan)
            topics = [t for t in data if t.get("company") in companies and t.get("question")][: 3 * len(companies) + 4]
            how = "llm"
        except Exception as exc:  # fall back, never crash the run
            how = f"offline (LLM failed: {type(exc).__name__})"
    if not topics:
        topics = _offline_plan(q, companies)
    for i, t in enumerate(topics, 1):
        t["id"] = f"T{i}"
    plan["topics"] = topics
    loads = f" · {plan['loads']:,} loads/week" if plan["loads"] else ""
    return {"plan": plan, **_trace("planner", f"lane {plan['lane']}{loads} · {len(topics)} sub-questions across "
                                              f"{', '.join(companies)} [{how}]", t0)}


def prompts_call_planner(question: str, plan: dict) -> list[dict]:
    from .llm import chat_json

    system = prompts.PLANNER_SYSTEM.format(lane=plan["lane"], mode=plan["mode"], companies=", ".join(plan["companies"]),
                                           n=min(12, 3 * len(plan["companies"])))
    data = chat_json(system, f"Request: {question}")
    return data.get("topics", []) if isinstance(data, dict) else data


# ---------------------------------------------------------------- researcher
def researcher(state: dict) -> dict:
    t0 = time.perf_counter()
    plan = state["plan"]
    topics = plan["topics"]

    via = "in-process tools"
    results = None
    if state.get("via_mcp", config.RESEARCH_VIA_MCP):
        try:
            from .tools import search_many_via_mcp

            reqs = [{"query": t["question"], "company": t["company"], "k": config.EVIDENCE_PER_TOPIC, "topic": t["topic"]}
                    for t in topics]
            results = list(zip(topics, search_many_via_mcp(reqs)))
            via = "MCP server"
        except Exception as exc:
            via = f"in-process tools (MCP failed: {type(exc).__name__})"
    if results is None:
        def run(t):
            return t, search_filings(t["question"], company=t["company"], k=config.EVIDENCE_PER_TOPIC, topic=t["topic"])

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(run, topics))
    results, retried = _research_again(state, results)
    evidence, seen = [], set()
    for _, hits in results:
        for e in hits:
            if e["chunk_id"] in seen:
                continue
            seen.add(e["chunk_id"])
            e["id"] = f"E{len(evidence) + 1}"
            evidence.append(e)
    pages = len({(e["company"], e["page"]) for e in evidence})
    rows = scorecard.evidence(plan["lane_id"], plan["companies"])
    for r in rows:
        r["id"] = r["row"]
    again = f" · {retried} weak result(s) re-searched with a reformulated query" if retried else ""
    return {"evidence": evidence + rows,
            **_trace("researcher", f"{len(topics)} searches via {via}{again} · {len(evidence)} passages from {pages} pages"
                                   f" + {len(rows)} scorecard rows", t0, research_retries=retried)}


_STOP = re.compile(r"\b(what|which|how|why|is|are|was|were|do|does|did|the|a|an|of|to|in|on|for|and|or|its|their|based|"
                   r"should|would|could|vs\.?|versus|10-?ks?|fy\s?2025|compare|between|including)\b", re.I)


def _reformulate(t: dict, state: dict) -> str:
    """Rewrite a sub-question whose first search came back weak (agentic RAG: decide to search again)."""
    if _use_llm(state):
        try:
            from .llm import chat

            q = chat(prompts.REFORMULATE_SYSTEM, f"Company: {t['company']}\nSub-question: {t['question']}", temperature=0.0)
            q = q.strip().strip('"').splitlines()[0]
            if 3 <= len(q) <= 300:
                return q
        except Exception:
            pass
    hint = dict(TOPICS).get(t.get("topic", ""), "")
    keywords = " ".join(w for w in _STOP.sub(" ", t["question"]).split() if len(w) > 2 and w.lower() not in hint.lower())
    return f"{t['company']} 10-K {keywords} {hint}".strip()


def _research_again(state: dict, results: list) -> tuple[list, int]:
    """Re-search any sub-question with too few hits or a low top score, then keep the best passages."""
    weak = [i for i, (_, hits) in enumerate(results)
            if len(hits) < config.RESEARCH_RETRY_MIN_HITS or max((e["score"] for e in hits), default=0) < config.RESEARCH_RETRY_MIN_SCORE]
    results = list(results)
    for i in weak:
        t, hits = results[i]
        more = search_filings(_reformulate(t, state), company=t["company"], k=config.EVIDENCE_PER_TOPIC, topic=t["topic"])
        merged = {e["chunk_id"]: e for e in hits + more}
        results[i] = (t, sorted(merged.values(), key=lambda e: -e["score"])[: config.EVIDENCE_PER_TOPIC])
    return results, len(weak)


# ---------------------------------------------------------------- quant
def quant(state: dict) -> dict:
    t0 = time.perf_counter()
    plan = state["plan"]
    fin = extract_metrics(_companies(state))
    lane = lane_metrics(plan["lane_id"], _companies(state))
    return {"metrics": fin, "lane_metrics": lane,
            **_trace("quant", f"{len(fin)} financial metrics from filing tables · {len(lane)} carriers scored on "
                              f"{plan['lane']} (acceptance, on-time, rate/mile, claims)", t0)}


# ---------------------------------------------------------------- advocates
def _sentence_score(sentence: str, side: str, item: str) -> tuple[float, str]:
    """(score, stance) for a filing sentence from one advocate's point of view."""
    risk = len(_RISK.findall(sentence)) + 0.5 * len(_HEDGE.findall(sentence))
    if side == "cost":
        if item == "1A":
            return 0.0, "for"
        score = len(_COST.findall(sentence)) - 1.0 * risk
        stance = "for"
    else:
        if item == "1A" or (risk >= 2 and len(_SERVICE.findall(sentence)) <= 1):
            score, stance = risk + (0.5 if item == "1A" else 0.0), "against"
        else:
            score, stance = len(_SERVICE.findall(sentence)) - 1.0 * risk, "for"
    if score <= 0:
        return 0.0, stance
    score += 1.0 if re.search(r"\d\s?%|\$\s?\d", sentence) else (0.4 if _NUMBER.search(sentence) else 0.0)
    score -= 0.75 if _CONNECTOR.search(sentence) else 0.0
    return max(score, 0.0), stance


def _filing_candidates(evidence: list[dict], side: str) -> list[dict]:
    out = []
    for e in evidence:
        if e.get("source") == "scorecard":
            continue
        for s in split_units(e["text"]):
            s = s.strip()
            if (not (60 <= len(s) <= 360) or "|" in s or s.endswith((":", ";")) or s.startswith(("•", "-", "("))
                    or _JUNK.search(s)):
                continue
            score, stance = _sentence_score(s, side, e.get("item", ""))
            if score > 0:
                out.append({"score": score + e["score"] * 0.5, "sentence": s, "evidence": e, "stance": stance})
    out.sort(key=lambda c: -c["score"])
    return out


def _scorecard_claims(state: dict, side: str) -> list[dict]:
    """Two claims per advocate straight from the lane scorecard (the strongest, most checkable evidence)."""
    lm = {m["carrier"]: m for m in state.get("lane_metrics", [])}
    ev = _evidence_map(state)
    if not lm:
        return []
    out = []
    if side == "cost":
        cheap = min(lm.values(), key=lambda m: m["rate_per_mile"])
        row = min((ev[r] for r in cheap["rows"] if r in ev), key=lambda e: _row_value(e, "rate"), default=None)
        if row:
            out.append(("for", cheap["carrier"], f"{cheap['carrier']} is the lowest-cost option on this lane. ", row,
                        _rate_span(row)))
        dear = max(lm.values(), key=lambda m: m["rate_per_mile"])
        row = ev.get(dear["q4_row"])
        if row and dear["carrier"] != cheap["carrier"]:
            out.append(("against", dear["carrier"], f"{dear['carrier']} is the most expensive carrier on this lane. ", row,
                        _rate_span(row)))
    else:
        best = max(lm.values(), key=lambda m: (m["q4_acceptance_pct"], m["on_time_pct"]))
        row = ev.get(best["q4_row"])
        if row:
            out.append(("for", best["carrier"], f"{best['carrier']} held up best in peak season. ", row, _accept_span(row)))
        worst = min(lm.values(), key=lambda m: m["q4_acceptance_pct"])
        row = ev.get(worst["q4_row"])
        if row and worst["carrier"] != best["carrier"]:
            out.append(("against", worst["carrier"], f"{worst['carrier']} is the weakest in peak season. ", row, _accept_span(row)))
    return [{"stance": st, "company": c, "text": lead + e["text"], "quote": span, "evidence_id": e["id"], "topic": "scorecard"}
            for st, c, lead, e, span in out]


def _row_value(e: dict, what: str) -> float:
    m = re.search(r"rate \$(\d+\.\d+)", e["text"]) if what == "rate" else re.search(r"\(([\d.]+)% acceptance\)", e["text"])
    return float(m.group(1)) if m else 0.0


def _rate_span(e: dict) -> str:
    m = re.search(r"rate \$\d+\.\d+ per mile", e["text"])
    return m.group(0) if m else ""


def _accept_span(e: dict) -> str:
    m = re.search(r"accepted [\d,]+ of [\d,]+ tenders \([\d.]+% acceptance\)", e["text"])
    return m.group(0) if m else ""


def _pick_offline(state: dict, side: str, n: int, exclude: set[str] | None = None, with_scorecard: bool = True) -> list[dict]:
    exclude = exclude or set()
    picked: list[dict] = []
    if with_scorecard:
        for c in _scorecard_claims(state, side):
            if _norm(c["quote"]) + c["evidence_id"] not in exclude:
                exclude.add(_norm(c["quote"]) + c["evidence_id"])
                picked.append({**c, "kind": "scorecard"})
    companies = _companies(state)
    cands = _filing_candidates(state.get("evidence", []), side)
    pools = {c: [x for x in cands if x["evidence"]["company"] == c] for c in companies}
    used_topics: set = set()
    against_used = 0
    while len(picked) < n and any(pools.values()):
        for c in companies:
            pool = pools[c]

            def ok(x):
                # the Resilience advocate files at most two "against" points from risk factors
                return _norm(x["sentence"]) not in exclude and not (x["stance"] == "against" and against_used >= 2)

            idx = next((i for i, x in enumerate(pool) if (c, x["evidence"]["topic"]) not in used_topics and ok(x)), None)
            if idx is None:
                idx = next((i for i, x in enumerate(pool) if ok(x)), None)
            if idx is None:
                pools[c] = []
                continue
            x = pool.pop(idx)
            exclude.add(_norm(x["sentence"]))
            used_topics.add((c, x["evidence"]["topic"]))
            against_used += x["stance"] == "against"
            picked.append({"stance": x["stance"], "company": c, "text": x["sentence"], "quote": x["sentence"],
                           "evidence_id": x["evidence"]["id"], "topic": x["evidence"]["topic"], "kind": "filing"})
            if len(picked) >= n:
                break
    return [{**c, "id": f"{PREFIX[side]}{i}", "side": side, "status": "pending", "by": "offline"}
            for i, c in enumerate(picked[:n], 1)]


def _llm_claims(state: dict, side: str, n: int) -> list[dict]:
    from .llm import chat_json

    companies = _companies(state)
    balance = (f"Cover every provider ({', '.join(companies)}) with at least one claim each, and use at least two "
               f"scorecard rows (S ids)." if len(companies) > 1 else f"All claims are about {companies[0]}.")
    system = prompts.CLAIMS_SYSTEM.format(side_title=SIDE_TITLES[side], side_desc=prompts.SIDE_DESC[side], n=n, balance=balance)
    profile = state.get("profile", {})
    plan = state["plan"]
    user = (f"Request: {state['question']}\nLane: {plan['lane']} ({plan['mode']})\nShipper mandate: {profile.get('mandate')}\n\n"
            f"Evidence:\n{_format_evidence(state['evidence'])}")
    data = chat_json(system, user, temperature=0.3)
    claims = data.get("claims", []) if isinstance(data, dict) else data
    return [{
        "id": f"{PREFIX[side]}{i}", "side": side, "company": c.get("company", ""), "topic": "",
        "stance": "against" if str(c.get("stance", "for")).lower().startswith("against") else "for",
        "text": c.get("text", "").strip(), "quote": c.get("quote", "").strip(), "evidence_id": c.get("evidence_id", "").strip(" []"),
        "status": "pending", "by": "llm", "kind": "scorecard" if str(c.get("evidence_id", "")).strip(" []").startswith("S") else "filing",
    } for i, c in enumerate(claims[:n], 1) if c.get("text")]


def _make_claims(state: dict, side: str) -> tuple[list[dict], str]:
    n = config.CLAIMS_PER_SIDE
    if _use_llm(state):
        try:
            claims = _llm_claims(state, side, n)
            if claims:
                return claims, "llm"
        except Exception as exc:
            return _pick_offline(state, side, n), f"offline (LLM failed: {type(exc).__name__})"
    return _pick_offline(state, side, n), "offline"


def _faulty_claim(state: dict) -> dict:
    company = _companies(state)[0]
    ev = next((e for e in state.get("evidence", []) if e["company"] == company and e.get("source") == "scorecard"),
              next((e for e in state.get("evidence", []) if e["company"] == company), state["evidence"][0]))
    return {"id": "C0", "side": "cost", "stance": "for", "company": company, "topic": "stress test", "kind": "scorecard",
            "text": _faulty_text(company), "quote": "accepted 100% of tenders at $1.15 per mile", "evidence_id": ev["id"],
            "status": "pending", "by": "stress test"}


def cost_advocate(state: dict) -> dict:
    t0 = time.perf_counter()
    claims, how = _make_claims(state, "cost")
    if state.get("inject_faulty"):
        claims = [_faulty_claim(state)] + claims
    return {"cost_claims": claims, **_trace("cost", f"{len(claims)} claims for the lowest-cost allocation [{how}]", t0)}


def service_advocate(state: dict) -> dict:
    t0 = time.perf_counter()
    claims, how = _make_claims(state, "service")
    return {"service_claims": claims, **_trace("service", f"{len(claims)} claims for a resilient, high-service allocation [{how}]", t0)}


# ---------------------------------------------------------------- rebuttal
def rebuttal(state: dict) -> dict:
    t0 = time.perf_counter()
    costs, services = state.get("cost_claims", []), state.get("service_claims", [])
    how = "offline"
    result = None
    if _use_llm(state) and costs and services:
        try:
            from .llm import chat_json

            ids = {c["evidence_id"] for c in costs + services}
            ev = [e for e in state["evidence"] if e["id"] in ids]
            user = ("Cost advocate claims:\n" + json.dumps(costs, indent=1) + "\n\nResilience advocate claims:\n"
                    + json.dumps(services, indent=1) + "\n\nEvidence:\n" + _format_evidence(ev, 500))
            data = chat_json(prompts.REBUTTAL_SYSTEM, user, temperature=0.4)
            result = {"service_rebuttal": data["service_rebuttal"], "cost_response": data["cost_response"]}
            how = "llm"
        except Exception as exc:
            how = f"offline (LLM failed: {type(exc).__name__})"
    if result is None:
        real_costs = [c for c in costs if c["by"] != "stress test"] or costs
        if not (real_costs and services):
            result = {"service_rebuttal": "", "cost_response": ""}
        else:
            c1 = real_costs[0]
            s1 = next((s for s in services if s["company"] == c1["company"] and s["stance"] == "against"),
                      next((s for s in services if s["kind"] == "scorecard"), services[0]))
            c2 = next((c for c in real_costs[1:] if c["company"] != s1["company"] and c["stance"] == "for"), real_costs[-1])
            result = {
                "service_rebuttal": (f"The cheapest rate only matters if the truck shows up. The Cost case leans on "
                                     f"\"{_short(c1['quote'])}\" [{c1['evidence_id']}], but the record also shows "
                                     f"\"{_short(s1['quote'])}\" [{s1['evidence_id']}]."),
                "cost_response": (f"Service risk is real, which is why no carrier gets the whole lane. A split still "
                                  f"captures savings: \"{_short(c2['quote'])}\" [{c2['evidence_id']}]."),
            }
    return {"rebuttal": result, **_trace("rebuttal", f"one rebuttal round [{how}]", t0)}


# ---------------------------------------------------------------- verifier
def verify_claim(claim: dict, evidence: dict[str, dict]) -> tuple[bool, str]:
    ev = evidence.get(claim.get("evidence_id", ""))
    if not ev:
        return False, f"cites unknown evidence '{claim.get('evidence_id')}'"
    if claim.get("company") and claim["company"] != ev["company"]:
        return False, f"claim is about {claim['company']} but the source is about {ev['company']}"
    source = _norm(ev["text"])
    quote = _norm(claim.get("quote", ""))
    if quote and quote not in source:
        where = "scorecard row" if ev.get("source") == "scorecard" else "cited page"
        return False, f"quoted words do not appear in the {where}"
    digits_src = source.replace(",", "")
    for num in _NUMBER.findall(claim.get("text", "")):
        n = num.replace(",", "").rstrip(".")
        if len(n) >= 2 and n not in digits_src:
            return False, f"number {num} is not in the cited source"
    where = f"scorecard row {ev['id']}" if ev.get("source") == "scorecard" else (
        f"{'Armada synthetic profile' if ev.get('synthetic') else ev['company'] + ' 10-K'} p.{ev['page']}")
    return True, f"supported by {where}"


def verifier(state: dict) -> dict:
    t0 = time.perf_counter()
    ev = _evidence_map(state)
    costs = [dict(c) for c in state.get("cost_claims", [])]
    services = [dict(c) for c in state.get("service_claims", [])]
    pending = [c for c in costs + services if c["status"] == "pending"]
    for c in pending:
        ok, reason = verify_claim(c, ev)
        c["status"], c["reason"] = ("supported" if ok else "unsupported"), reason
    how = "rules"
    llm_checked = [c for c in pending if c["status"] == "supported" and c["by"] == "llm"]
    if llm_checked and _use_llm(state):
        try:
            from .llm import chat_json

            payload = [{"id": c["id"], "claim": c["text"], "evidence": ev[c["evidence_id"]]["text"][:900]} for c in llm_checked]
            data = chat_json(prompts.VERIFIER_SYSTEM, json.dumps(payload, indent=1), temperature=0.0)
            verdicts = {r["id"]: r for r in data.get("results", [])}
            for c in llm_checked:
                v = verdicts.get(c["id"])
                if v and not v.get("supported", True):
                    c["status"], c["reason"] = "unsupported", f"LLM judge: {v.get('reason', 'not supported')}"
            how = "rules + LLM judge"
        except Exception as exc:
            how = f"rules (LLM judge failed: {type(exc).__name__})"
    failed = [c for c in costs + services if c["status"] == "unsupported"]
    ok = sum(c["status"] == "supported" for c in costs + services)
    summary = f"{ok} supported, {len(failed)} unsupported [{how}]"
    if failed:
        summary += " · " + "; ".join(f"{c['id']}: {c['reason']}" for c in failed[:3])
    return {"cost_claims": costs, "service_claims": services, **_trace("verifier", summary, t0, failed=len(failed))}


def after_verifier(state: dict) -> str:
    failed = any(c["status"] == "unsupported" for c in _all_claims(state))
    if failed and state.get("attempts", 0) < config.MAX_VERIFY_RETRIES:
        return "revise"
    return "judge"


def revise(state: dict) -> dict:
    """Send rejected claims back to their advocate for a supported replacement."""
    t0 = time.perf_counter()
    attempt = state.get("attempts", 0) + 1
    out: dict[str, Any] = {"attempts": attempt}
    replaced = 0
    for side in SIDES:
        key = f"{side}_claims"
        claims = [dict(c) for c in state.get(key, [])]
        failed = [c for c in claims if c["status"] == "unsupported"]
        if not failed:
            continue
        keep = [c for c in claims if c["status"] != "unsupported"]
        new: list[dict] = []
        if _use_llm(state) and any(c["by"] == "llm" for c in failed):
            try:
                from .llm import chat_json

                system = prompts.REVISE_SYSTEM.format(side_title=SIDE_TITLES[side])
                user = ("Rejected claims:\n" + json.dumps([{k: c.get(k) for k in ("company", "stance", "text", "evidence_id", "quote", "reason")}
                                                          for c in failed], indent=1)
                        + "\n\nEvidence:\n" + _format_evidence(state["evidence"]))
                data = chat_json(system, user, temperature=0.2)
                new = [{"side": side, "company": c.get("company", ""), "topic": "", "text": c.get("text", ""),
                        "stance": "against" if str(c.get("stance", "for")).lower().startswith("against") else "for",
                        "quote": c.get("quote", ""), "evidence_id": c.get("evidence_id", "").strip(" []"),
                        "status": "pending", "by": "llm", "kind": "filing"} for c in data.get("claims", [])[: len(failed)]]
            except Exception:
                new = []
        if not new:
            exclude = {_norm(c["quote"]) for c in claims} | {_norm(c["quote"]) + c["evidence_id"] for c in claims}
            new = _pick_offline(state, side, len(failed), exclude=exclude, with_scorecard=False)
            for c in new:
                c["by"] = "offline (revised)"
        start = max([int(re.sub(r"\D", "", c["id"]) or 0) for c in claims] + [0]) + 1
        for i, c in enumerate(new):
            c["id"] = f"{PREFIX[side]}{start + i}"
            c["revision_of"] = failed[min(i, len(failed) - 1)]["id"]
        replaced += len(new)
        dropped = [{**c, "status": "dropped"} for c in failed]
        out[key] = keep + new + dropped
    return {**out, **_trace("revise", f"retry {attempt}/{config.MAX_VERIFY_RETRIES}: {replaced} rejected claims rewritten", t0)}


# ---------------------------------------------------------------- judge (tender allocation)
MANDATE_WEIGHTS = {
    "balanced": {"acceptance": 0.25, "on_time": 0.20, "rate": 0.25, "claims": 0.10, "peak": 0.10, "financial": 0.10},
    "cost-first": {"acceptance": 0.15, "on_time": 0.10, "rate": 0.50, "claims": 0.05, "peak": 0.05, "financial": 0.15},
    "service-first": {"acceptance": 0.25, "on_time": 0.30, "rate": 0.10, "claims": 0.10, "peak": 0.15, "financial": 0.10},
}


def _minmax(values: dict[str, float], higher_better: bool = True) -> dict[str, float]:
    lo, hi = min(values.values()), max(values.values())
    if hi - lo < 1e-9:
        return {k: 0.75 for k in values}
    return {k: ((v - lo) / (hi - lo) if higher_better else (hi - v) / (hi - lo)) for k, v in values.items()}


def financial_health(company: str, metrics: list[dict]) -> dict:
    """0-1 health score from operating margin, its trend and operating cash flow (read from the filings)."""
    mets = {m["key"]: m for m in metrics if m["company"] == company}
    margin, ocf = mets.get("op_margin"), mets.get("op_cash_flow")
    if not margin:
        return {"score": 0.4, "note": "no financial statements available"}
    score = 0.35 + min(margin["fy2025"], 25) / 40 + (0.1 if margin["improved"] else 0.0) + (0.1 if ocf and ocf["fy2025"] > 0 else 0.0)
    synthetic = margin.get("synthetic", False)
    if synthetic:
        score -= 0.1  # self-reported, unaudited
    note = f"operating margin {margin['fy2025']}% ({'up' if margin['improved'] else 'down'} from {margin['fy2024']}%)"
    return {"score": round(max(0.0, min(1.0, score)), 3), "note": note + (", self-reported" if synthetic else "")}


def _round_shares(raw: dict[str, float], step: float = 5.0) -> dict[str, float]:
    """Round to `step`% and make the total exactly 100 (largest remainders win)."""
    if not raw:
        return {}
    total = sum(raw.values()) or 1
    scaled = {k: v / total * 100 / step for k, v in raw.items()}
    base = {k: int(v) for k, v in scaled.items()}
    left = int(round(100 / step)) - sum(base.values())
    for k in sorted(scaled, key=lambda k: -(scaled[k] - base[k]))[: max(left, 0)]:
        base[k] += 1
    return {k: v * step for k, v in base.items()}


def allocate(scores: dict[str, float], caps: dict[str, float], floor: float) -> dict[str, float]:
    """Split 100% in proportion to score², respecting per-carrier caps and a floor (water-filling)."""
    shares: dict[str, float] = {}
    free = dict(scores)
    budget = 100.0
    for _ in range(len(scores) + 1):
        weight = {k: max(v, 1e-6) ** 2 for k, v in free.items()}
        tot = sum(weight.values()) or 1
        trial = {k: budget * w / tot for k, w in weight.items()}
        trial = {k: max(v, floor) for k, v in trial.items()}
        over = {k: caps[k] for k, v in trial.items() if v > caps[k]}
        if not over:
            # floors may push the sum over budget: take the excess from the largest shares
            excess = sum(trial.values()) - budget
            for k in sorted(trial, key=lambda k: -trial[k]):
                if excess <= 0:
                    break
                cut = min(excess, trial[k] - floor)
                trial[k] -= cut
                excess -= cut
            shares.update(trial)
            break
        shares.update(over)
        budget -= sum(over.values())
        free = {k: v for k, v in free.items() if k not in over}
        if not free:
            break
    return shares


def score_lane(state: dict) -> list[dict]:
    plan = state["plan"]
    profile = state.get("profile", {})
    mandate = profile.get("mandate", "balanced")
    w = MANDATE_WEIGHTS.get(mandate, MANDATE_WEIGHTS["balanced"])
    lm = {m["carrier"]: m for m in state.get("lane_metrics", [])}
    companies = _companies(state)
    verified = [c for c in _all_claims(state) if c["status"] == "supported"]
    rows = []
    if lm:
        n_acc = _minmax({k: m["acceptance_pct"] for k, m in lm.items()})
        n_ot = _minmax({k: m["on_time_pct"] for k, m in lm.items()})
        n_rate = _minmax({k: m["rate_per_mile"] for k, m in lm.items()}, higher_better=False)
        n_claims = _minmax({k: m["claims_pct"] for k, m in lm.items()}, higher_better=False)
        n_peak = _minmax({k: m["q4_acceptance_pct"] for k, m in lm.items()})
    for c in companies:
        fin = financial_health(c, state.get("metrics", []))
        pros = sum(1 for x in verified if x["company"] == c and x["stance"] == "for")
        cons = sum(1 for x in verified if x["company"] == c and x["stance"] == "against")
        m = lm.get(c)
        row = {"company": c, "mandate": mandate, "financial": fin, "verified_for": pros, "verified_against": cons,
               "synthetic": c in config.SYNTHETIC_COMPANIES, "lane": m, "notes": []}
        if not m:
            row.update(score=0.0, qualified=False)
            row["notes"].append(f"no tender history on {plan['lane']}, so it cannot be scored on this lane")
        else:
            parts = {"acceptance": n_acc[c], "on_time": n_ot[c], "rate": n_rate[c], "claims": n_claims[c],
                     "peak": n_peak[c], "financial": fin["score"]}
            s = sum(w[k] * v for k, v in parts.items())
            s += max(-0.08, min(0.08, 0.02 * (pros - cons)))  # the debate nudges, the data decides
            if profile.get("incumbent") == c:
                s += 0.03
                row["notes"].append("incumbent on the lane (continuity bonus)")
            row.update(score=round(max(s, 0.02), 3), parts={k: round(v, 2) for k, v in parts.items()},
                       qualified=m["acceptance_pct"] >= config.MIN_ACCEPTANCE)
            if not row["qualified"]:
                row["notes"].append(f"acceptance {m['acceptance_pct']}% is below the {config.MIN_ACCEPTANCE:.0f}% "
                                    "floor, so backup only")
        rows.append(row)
    return rows


def judge(state: dict) -> dict:
    t0 = time.perf_counter()
    plan = state["plan"]
    rows = score_lane(state)
    qualified = {r["company"]: r["score"] for r in rows if r["qualified"]}
    caps = {}
    for r in rows:
        cap = config.MAX_SHARE if len(qualified) > 1 else 100.0
        if r["synthetic"]:
            cap = min(cap, config.SYNTHETIC_CAP)
            r["notes"].append(f"capped at {config.SYNTHETIC_CAP:.0f}%: evidence is a synthetic, unaudited profile")
        caps[r["company"]] = cap
    floor = config.MIN_SHARE if len(qualified) > 1 else 0.0
    raw = allocate(qualified, caps, floor) if qualified else {}
    shares = _round_shares(raw)
    for r in rows:
        r["share"] = shares.get(r["company"], 0.0)
        r["loads"] = round(r["share"] / 100 * plan["loads"]) if plan.get("loads") else None
        if r["share"] >= config.MAX_SHARE - 1e-6 and len(qualified) > 1:
            r["notes"].append(f"capped at {config.MAX_SHARE:.0f}% to avoid single-carrier dependence")
    ranked = sorted(rows, key=lambda r: (-r["share"], -r["score"]))
    for i, r in enumerate(ranked):
        r["role"] = "Primary" if i == 0 and r["share"] > 0 else ("Secondary" if r["share"] > 0 else "Backup / not awarded")
        r["score100"] = round(r["score"] * 100)
    split = " · ".join(f"{r['company']} {r['share']:.0f}%" for r in ranked if r["share"] > 0) or "no carrier qualifies"
    mandate = rows[0]["mandate"] if rows else "balanced"
    loads = f" of {plan['loads']:,} weekly loads" if plan.get("loads") else ""
    verdict = f"Award {plan['lane']}{loads}: {split} ({mandate} mandate)."
    return {"judge": {"allocation": ranked, "verdict": verdict, "lane": plan["lane"], "mode": plan["mode"],
                      "loads": plan.get("loads"), "mandate": mandate},
            **_trace("judge", verdict, t0)}


# ---------------------------------------------------------------- writer
def _lane_lines(state: dict) -> list[str]:
    lines = []
    for m in state.get("lane_metrics", []):
        rows = ", ".join(m["rows"])
        lines.append(f"| {m['carrier']} | {m['tenders_accepted']:,}/{m['tenders_offered']:,} ({m['acceptance_pct']}%) | "
                     f"{m['q4_acceptance_pct']}% [{m['q4_row']}] | {m['on_time_pct']}% | ${m['rate_per_mile']:.2f} | "
                     f"{m['claims_pct']}% | {rows} |")
    return lines


def _metric_lines(state: dict) -> list[str]:
    keys = ("revenue", "op_margin", "op_cash_flow", "operating_ratio", "net_income")
    mets = sorted([m for m in state.get("metrics", []) if m["key"] in keys],
                  key=lambda m: (m["company"], keys.index(m["key"])))
    lines = []
    for m in mets:
        pct = "" if m["yoy_pct"] is None or m["unit"] == "%" else f" ({m['yoy_pct']:+.0f}% YoY)"
        src = f"p.{m['page']}" + (" (synthetic profile)" if m.get("synthetic") else "")
        lines.append(f"| {m['company']} | {m['label']} | {fmt_value(m['fy2024'], m['unit'])} | "
                     f"{fmt_value(m['fy2025'], m['unit'])}{pct} | {src} |")
    return lines


def _offline_memo(state: dict) -> str:
    j = state["judge"]
    plan = state["plan"]
    costs = [c for c in state.get("cost_claims", []) if c["status"] == "supported"]
    services = [c for c in state.get("service_claims", []) if c["status"] == "supported"]
    reb = state.get("rebuttal", {})
    profile = state.get("profile", {})
    alloc = j["allocation"]
    primary = next((r for r in alloc if r["role"] == "Primary"), None)
    lines = ["## Tender recommendation memo", f"**Request:** {state['question']}", "",
             f"**Lane:** {plan['lane']} · {plan['mode']}" + (f" · {plan['loads']:,} loads per week" if plan.get("loads") else ""), "",
             "### Recommendation",
             f"{j['verdict']} "
             + (f"{primary['company']} is the primary carrier with a fit score of {primary['score100']}/100. " if primary else "")
             + f"The committee reviewed {len([e for e in state.get('evidence', []) if e.get('source') != 'scorecard'])} filing passages "
             f"and {len(state.get('lane_metrics', []))} carriers' lane scorecards, and kept {len(costs) + len(services)} verified claims. "
             f"Weights follow your **{profile.get('mandate', 'balanced')}** mandate.", "",
             "| Provider | Role | Allocation | Loads / week | Fit score | Verified for / against | Notes |",
             "|---|---|---|---|---|---|---|"]
    for r in alloc:
        loads = f"{r['loads']:,}" if r.get("loads") is not None else "n/a"
        lines.append(f"| {r['company']}{' *' if r['synthetic'] else ''} | {r['role']} | **{r['share']:.0f}%** | {loads} | "
                     f"{r['score100']} | {r['verified_for']} / {r['verified_against']} | {'; '.join(r['notes']) or '-'} |")
    if any(r["synthetic"] for r in alloc):
        lines.append("\n\\* Armada is privately held; its evidence is a synthetic, self-reported profile, not an SEC filing.")
    lines += ["", "### Lane scorecard, 2025 (synthetic shipper data)",
              "| Carrier | Tenders accepted / offered | Q4 peak acceptance | On-time | Rate per mile | Claims | Rows |",
              "|---|---|---|---|---|---|---|", *_lane_lines(state), ""]
    lines += ["### Financial health (FY2024 → FY2025, from the filings' tables)",
              "| Provider | Metric | FY2024 | FY2025 | Source |", "|---|---|---|---|---|", *_metric_lines(state), ""]

    def fmt(c):
        tag = "" if c["stance"] == "for" else " *(against)*"
        return f"- **{c['company']}**{tag}: {c['text']} [{c['evidence_id']}]"

    lines += ["### Cost case"] + [fmt(c) for c in costs] + [""]
    lines += ["### Resilience case"] + [fmt(c) for c in services] + [""]
    if reb.get("service_rebuttal"):
        lines += ["### Debate", f"- **Resilience rebuttal:** {reb['service_rebuttal']}", f"- **Cost response:** {reb['cost_response']}", ""]
    lines += ["### Risks and guardrails applied",
              f"- No carrier above {config.MAX_SHARE:.0f}% of the lane, and every qualified carrier keeps at least "
              f"{config.MIN_SHARE:.0f}% as backup capacity.",
              f"- Carriers below {config.MIN_ACCEPTANCE:.0f}% tender acceptance on the lane are backup only.",
              f"- Providers backed only by synthetic or unaudited data are capped at {config.SYNTHETIC_CAP:.0f}%.", ""]
    lines += ["### Open questions before award",
              "- Will each carrier commit to the awarded volume in writing, with a minimum tender acceptance in the contract?",
              "- What peak-season (Q4) surge capacity and surcharge does each carrier guarantee?",
              "- Can Armada provide audited financial statements and a certificate of insurance before award?"]
    if plan.get("off_lane"):
        lines.append(f"- {', '.join(plan['off_lane'])} has no tender history on this lane: run a pilot before awarding volume.")
    notes = state.get("review", {}).get("notes")
    if notes:
        lines += ["", "### Reviewer notes addressed", f"- {notes}"]
    past = state.get("past_memos") or []
    if past:
        last = past[-1]
        lines += ["", f"*Memory: your previous approved award ({last['date']}) was \"{_short(last['summary'], 110)}\".*"]
    return "\n".join(lines)


def _sources_section(memo: str, state: dict) -> str:
    ev = _evidence_map(state)
    cited = []
    for eid in re.findall(r"\[((?:E|S)\d+)\]", memo):
        if eid in ev and eid not in cited:
            cited.append(eid)
    if not cited:
        return memo
    rows = [f"- **{e}**: {cite_label(ev[e])}" for e in cited]
    return memo.rstrip() + "\n\n### Sources\n" + "\n".join(rows) + "\n"


def writer(state: dict) -> dict:
    t0 = time.perf_counter()
    how = "offline"
    memo = None
    if _use_llm(state):
        try:
            from .llm import chat

            verified = [c for c in _all_claims(state) if c["status"] == "supported"]
            ids = sorted({c["evidence_id"] for c in verified} | {r for m in state.get("lane_metrics", []) for r in m["rows"]})
            user = json.dumps({
                "request": state["question"], "lane": state["plan"]["lane"], "judge": state["judge"],
                "verified_claims": verified, "rebuttal": state.get("rebuttal"),
                "lane_scorecard_table": _lane_lines(state), "financial_table": _metric_lines(state),
                "shipper_profile": state.get("profile"), "past_memos": state.get("past_memos"),
                "reviewer_notes": state.get("review", {}).get("notes"), "allowed_evidence_ids": ids,
            }, indent=1, default=str)
            memo = chat(prompts.WRITER_SYSTEM, user, temperature=0.3)
            allowed = set(ids)
            memo = re.sub(r"\[((?:E|S)\d+)\]", lambda m: m.group(0) if m.group(1) in allowed else "", memo)
            how = "llm"
        except Exception as exc:
            memo, how = None, f"offline (LLM failed: {type(exc).__name__})"
    if not memo:
        memo = _offline_memo(state)
    memo = _sources_section(memo, state)
    memo, flags = check_output(memo)
    summary = f"memo drafted ({len(memo.split())} words) [{how}]" + (" · " + " ".join(flags) if flags else "")
    return {"memo": memo, "output_flags": flags, **_trace("writer", summary, t0)}


# ---------------------------------------------------------------- human review + finalize
def human_review(state: dict) -> dict:
    from langgraph.types import interrupt

    t0 = time.perf_counter()
    decision = interrupt({"memo": state.get("memo", ""), "verdict": state.get("judge", {}).get("verdict", "")})
    if not isinstance(decision, dict):
        decision = {"action": str(decision)}
    action = decision.get("action", "approve")
    from .observability import log_feedback

    log_feedback(state, decision)
    update: dict[str, Any] = {"review": decision}
    if action == "follow_up" and decision.get("question"):
        update.update({"question": decision["question"], "attempts": 0, "cost_claims": [], "service_claims": []})
    return {**update, **_trace("human_review", f"reviewer chose: {action}", t0)}


def after_review(state: dict) -> str:
    action = state.get("review", {}).get("action", "approve")
    return {"revise": "writer", "follow_up": "guard"}.get(action, "finalize")


def finalize(state: dict) -> dict:
    t0 = time.perf_counter()
    j = state.get("judge", {})
    MemoryStore().add_memo(state.get("user_id", "default"), state["question"], j.get("verdict", ""),
                           {r["company"]: r["share"] for r in j.get("allocation", [])})
    out = {"final": True, **_trace("finalize", "allocation approved and saved to long-term memory", t0)}
    from .observability import log_run

    log_run({**state, "trace": state.get("trace", []) + out["trace"]})
    return out


def refuse(state: dict) -> dict:
    t0 = time.perf_counter()
    return {"memo": f"**Request not processed.** {state.get('refusal_reason', '')}", "final": True,
            **_trace("refuse", "guardrail stopped the run", t0)}
