"""LaneRoom Streamlit app: an AI tender committee recommends how to split a freight lane between carriers."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

# Chroma needs SQLite >= 3.35. Some hosted Linux images ship an older one; use pysqlite3 there if it is installed.
try:
    import sqlite3

    if sqlite3.sqlite_version_info < (3, 35, 0):
        __import__("pysqlite3")
        sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

from laneroom import config, ui  # noqa: E402
from laneroom.graph import NODE_LABELS, LaneRoom  # noqa: E402
from laneroom.memory import MANDATES, MemoryStore  # noqa: E402
from laneroom.metrics import fmt_value  # noqa: E402
from laneroom.observability import run_totals  # noqa: E402

st.set_page_config(page_title="LaneRoom · AI tender committee", page_icon="🚚", layout="wide")
st.markdown(ui.CSS + ui.MEMO_CSS + ui.BACKGROUND, unsafe_allow_html=True)

EXAMPLES = [
    ("Dallas→Atlanta 500 loads", "Dallas→Atlanta dry van: allocate 500 weekly loads", ":material/local_shipping:"),
    ("LTL: ODFL vs CHRW", "LTL national contract: ODFL vs CHRW", ":material/inventory_2:"),
    ("Peak surge", "Peak season surge capacity: who should get the extra Q4 loads?", ":material/bolt:"),
    ("Chicago→LA intermodal", "Chicago to Los Angeles intermodal: allocate 300 weekly loads between J.B. Hunt and C.H. Robinson",
     ":material/train:"),
]
METRIC_LABELS = {"acceptance_pct": "Tender acceptance %", "on_time_pct": "On-time %", "rate_per_mile": "Rate per mile",
                 "claims_pct": "Claims %"}


@st.cache_resource(show_spinner="Loading the carrier knowledge base…")
def get_room() -> LaneRoom:
    from laneroom.tools import get_index

    get_index()
    return LaneRoom()


room = get_room()
store = MemoryStore()
ss = st.session_state
ss.setdefault("thread", None)
ss.setdefault("trace", [])
ss.setdefault("question", EXAMPLES[0][1])

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown(ui.brand(), unsafe_allow_html=True)
    st.markdown("#### Shipper profile")
    user_id = st.text_input("Shipper / reviewer name", value="demo").strip() or "demo"
    user = store.get_user(user_id)
    mandate = st.selectbox("Procurement mandate", list(MANDATES), index=list(MANDATES).index(user["profile"]["mandate"]),
                           help="The Judge weights rate, acceptance, on-time, claims, peak capacity and financial health "
                                "differently for each mandate.")
    prefs = st.multiselect("Metrics to lead with", list(METRIC_LABELS), format_func=METRIC_LABELS.get,
                           default=[m for m in user["profile"]["preferred_metrics"] if m in METRIC_LABELS])
    carriers = ["(none)"] + list(config.COMPANIES)
    incumbent = st.selectbox("Incumbent carrier on the lane", carriers,
                             index=carriers.index(user["profile"].get("incumbent") or "(none)"),
                             help="The incumbent gets a small continuity bonus.")
    incumbent = "" if incumbent == "(none)" else incumbent
    if st.button("Save profile to memory", width="stretch"):
        store.save_profile(user_id, {"mandate": mandate, "preferred_metrics": prefs, "incumbent": incumbent})
        st.toast("Profile saved. The Judge and Writer will use it.", icon="🧠")

    st.markdown("#### Run options")
    llm_ok = config.llm_enabled("auto")
    mode = st.segmented_control("Agents", ["auto", "offline"], default="auto",
                                help="auto = LLM agents when an API key is set, otherwise offline agents.") or "auto"
    st.caption(f"Engine: **{config.llm_label() if llm_ok and mode == 'auto' else 'offline agents (no key needed)'}**")
    st.caption("Tracing: **LangSmith on**" if config.tracing_enabled()
               else "Tracing: **local run log** (set LANGSMITH_TRACING=true for LangSmith)")
    inject = st.toggle("Stress test: plant a false claim", value=False,
                       help="Adds a made-up Cost claim ('100% acceptance at $1.15 per mile') to show the Verifier catching it.")
    via_mcp = st.toggle("Researcher uses the MCP server", value=False,
                        help="Runs the knowledge base as an MCP server (stdio) and has the Researcher call it.")

    st.markdown("#### Data")
    st.caption("J.B. Hunt, C.H. Robinson and Old Dominion: FY2025 Form 10-K (SEC EDGAR). "
               "**Armada, Edge Logistics, First Star and BlueGrace Logistics** are privately held: **synthetic**, illustrative "
               "profiles, not data from those companies. The lane scorecard is **synthetic** demo data.")

    st.markdown("#### Memory")
    if user["memos"]:
        for m in reversed(user["memos"][-3:]):
            with st.container(border=True):
                st.caption(f"{m['date']}")
                st.markdown(f"**{m['question'][:70]}**")
                st.caption(m["summary"])
        if st.button("Clear my memory", width="stretch"):
            store.clear(user_id)
            st.rerun()
    else:
        st.caption("No approved awards yet. Approve one and it is remembered here.")


def route_deck(plan: dict, allocation: list[dict]):
    """pydeck ArcLayer of the lane on a dark basemap; None if pydeck is unavailable."""
    try:
        import pydeck as pdk
    except ImportError:
        return None
    from laneroom import maps

    awarded = [r for r in allocation if r.get("share", 0) > 0] or allocation
    routes = maps.LANE_ROUTES.get(plan.get("lane_id", ""), [])
    rows = []
    for i, (a, b) in enumerate(routes):
        legs = awarded if len(routes) == 1 else [awarded[i % len(awarded)]] if awarded else []
        for j, r in enumerate(legs):
            hexc = maps.PROVIDERS.get(r["company"], maps.FALLBACK)["color"].lstrip("#")
            rgb = [int(hexc[k:k + 2], 16) for k in (0, 2, 4)]
            rows.append({"from": a, "to": b, "carrier": r["company"], "share": r["share"], "src": list(maps.CITIES[a]),
                         "dst": list(maps.CITIES[b]), "color": rgb, "width": 2 + r["share"] / 8,
                         "height": 0.25 + 0.18 * j})
    cities = [{"name": c, "pos": list(maps.CITIES[c])} for c in {c for r in routes for c in r}]
    layers = [
        pdk.Layer("ArcLayer", rows, get_source_position="src", get_target_position="dst", get_source_color="color",
                  get_target_color="color", get_width="width", get_height="height", pickable=True),
        pdk.Layer("ScatterplotLayer", cities, get_position="pos", get_radius=26000, get_fill_color=[234, 246, 255],
                  get_line_color=[4, 19, 27], line_width_min_pixels=2, stroked=True),
        pdk.Layer("TextLayer", cities, get_position="pos", get_text="name", get_size=13, get_color=[201, 220, 230],
                  get_pixel_offset=[0, -16]),
    ]
    view = pdk.ViewState(latitude=37.5, longitude=-95.5, zoom=3.15, pitch=35)
    return pdk.Deck(layers=layers, initial_view_state=view, map_provider="carto", map_style="dark",
                    tooltip={"text": "{carrier}: {share}% · {from} → {to}"})


def run_stream(gen, box) -> None:
    for node, update in gen:
        if node == "__interrupt__":
            continue
        for t in (update or {}).get("trace", []):
            ss.trace.append(t)
            icon = ui.ICONS.get(t["node"], "•")
            box.markdown(f"{icon} **{NODE_LABELS.get(t['node'], t['node'])}** · {t['summary']}")
            box.update(label=f"{icon} {NODE_LABELS.get(t['node'], t['node'])} done")


# ---------------------------------------------------------------- main
st.markdown(ui.hero(), unsafe_allow_html=True)
tab_room, tab_eval, tab_how, tab_course = st.tabs(["Committee", "Evaluation", "How it works", "Course map"])

with tab_room:
    st.markdown(ui.section("lightning", "Pick a scenario or write your own"), unsafe_allow_html=True)
    cols = st.columns(len(EXAMPLES))
    for col, (label, ex, ico) in zip(cols, EXAMPLES):
        if col.button(label, width="stretch", help=ex, icon=ico):
            ss.question = ex
    q_col, b_col = st.columns([4.3, 1.7], vertical_alignment="bottom")
    with q_col:
        question = st.text_area("Your tender request", key="question", height=80, label_visibility="collapsed")
    with b_col:
        go = st.button("Convene committee", type="primary", width="stretch", icon=":material/gavel:")

    if go:
        ss.thread = room.new_thread()
        ss.trace = []
        with st.status("The tender committee is in session…", expanded=True) as box:
            t0 = time.perf_counter()
            run_stream(room.start(question, ss.thread, user_id=user_id, mode=mode, inject_faulty=inject, via_mcp=via_mcp,
                                  profile={"mandate": mandate, "preferred_metrics": prefs, "incumbent": incumbent}), box)
            tot = run_totals(ss.trace)
            box.update(label=f"✅ Committee finished in {time.perf_counter() - t0:.1f}s · {tot['llm_calls']} LLM calls · "
                             f"{tot['tokens_in'] + tot['tokens_out']:,} tokens · ${tot['cost_usd']:.4f}",
                       state="complete", expanded=False)

    if not ss.thread:
        st.markdown(ui.section("truck", "Carrier roster: who can bid on your lanes"), unsafe_allow_html=True)
        st.markdown(ui.roster(config.COMPANIES), unsafe_allow_html=True)
        st.markdown(ui.road("I-20 · DAL → ATL · 500 loads / wk"), unsafe_allow_html=True)

    if ss.thread:
        state = room.state(ss.thread)
        st.markdown(ui.pipeline(ss.trace), unsafe_allow_html=True)

        if state.get("refused"):
            st.error(state.get("memo", "Request blocked."), icon="⛔")
        elif state.get("memo"):
            for note in state.get("guard", {}).get("notes", []):
                st.info(note, icon="🛡️")
            st.markdown(ui.verdict(state.get("judge", {})), unsafe_allow_html=True)
            st.markdown(ui.lane_card(state.get("judge", {}), state.get("plan", {})), unsafe_allow_html=True)

            t_debate, t_metrics, t_map, t_memo, t_evidence, t_trace = st.tabs(
                ["Debate", "Scorecard & metrics", "Network map", "Memo", "Evidence", "Agent log"])
            all_claims = state.get("cost_claims", []) + state.get("service_claims", [])
            with t_debate:
                dropped = [c for c in all_claims if c["status"] == "dropped"]
                if dropped:
                    replaced_by = {c.get("revision_of"): c["id"] for c in all_claims if c.get("revision_of")}
                    st.markdown(ui.caught(dropped, replaced_by), unsafe_allow_html=True)
                left, right = st.columns(2, gap="large")
                costs = [c for c in state.get("cost_claims", []) if c["status"] != "dropped"]
                services = [c for c in state.get("service_claims", []) if c["status"] != "dropped"]
                with left:
                    st.markdown(ui.side_header("cost", "Cost advocate", len(costs)) + "".join(ui.claim(c) for c in costs),
                                unsafe_allow_html=True)
                with right:
                    st.markdown(ui.side_header("service", "Resilience advocate", len(services))
                                + "".join(ui.claim(c) for c in services), unsafe_allow_html=True)
                reb = state.get("rebuttal") or {}
                if reb.get("service_rebuttal"):
                    st.markdown(ui.rebuttal(reb), unsafe_allow_html=True)
            with t_metrics:
                st.markdown(ui.lane_grid(state.get("lane_metrics", [])), unsafe_allow_html=True)
                st.caption("Synthetic shipper scorecard (data/scorecard/shipper_scorecard_synthetic.csv): tenders offered "
                           "and accepted, on-time %, rate per mile and claims % per quarter of 2025. Not real carrier data.")
                st.markdown(ui.metric_grid(state.get("metrics", []), fmt_value), unsafe_allow_html=True)
                st.caption("Financial health read by the Quant agent straight from each 10-K's tables. The page chip is the "
                           "source page. Private providers' figures come from synthetic, illustrative profiles.")
            with t_map:
                deck = route_deck(state.get("plan", {}), state.get("judge", {}).get("allocation", []))
                if deck is not None:
                    st.pydeck_chart(deck, height=460)
                st.caption("Real geography (pydeck arcs on a CARTO basemap). Arc width follows each carrier's share; colours "
                           "match the badges. Lanes are schematic metro-to-metro routes, not actual carrier networks.")
            with t_memo:
                with st.container(key="memo_paper"):
                    st.markdown(state["memo"])
                st.download_button("Download memo (.md)", state["memo"], file_name="laneroom_tender_memo.md")
            with t_evidence:
                ev = {e["id"]: e for e in state.get("evidence", [])}
                cited = []
                for c in all_claims:
                    if c["evidence_id"] in ev and c["evidence_id"] not in cited:
                        cited.append(c["evidence_id"])
                st.caption(f"{len(cited)} sources cited out of {len(ev)} retrieved (filing passages E# and scorecard rows S##). "
                           "Expand one to read the exact text.")
                from laneroom.agents import cite_label

                for eid in cited + [e for e in ev if e not in cited]:
                    e = ev[eid]
                    star = "⭐ " if eid in cited else ""
                    with st.expander(f"{star}{eid} · {e['company']} · {cite_label(e)}"):
                        st.text(e["text"])
            with t_trace:
                st.markdown(ui.usage_strip(run_totals(ss.trace)), unsafe_allow_html=True)
                for t in ss.trace:
                    tokens = t.get("tokens_in", 0) + t.get("tokens_out", 0)
                    usage = f" · {tokens:,} tok · ${t.get('cost_usd', 0):.4f}" if t.get("llm_calls") else ""
                    st.markdown(f"{ui.ICONS.get(t['node'], '•')} **{NODE_LABELS.get(t['node'], t['node'])}** · "
                                f"{t['summary']} <span style='color:#64818F;font-family:Geist Mono,monospace'>({t['ms']} ms{usage})</span>",
                                unsafe_allow_html=True)
                st.caption("Each finished run is also appended to data/traces/runs.jsonl, and every review decision to "
                           "data/eval/feedback.jsonl for regression evals.")

            if room.waiting_for_review(ss.thread):
                st.markdown(ui.review_header(), unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3, gap="medium")
                with c1:
                    st.markdown("**Award it**")
                    if st.button("Approve allocation", type="primary", width="stretch"):
                        with st.status("Saving to memory…") as box:
                            run_stream(room.resume({"action": "approve"}, ss.thread), box)
                        st.rerun()
                with c2:
                    notes = st.text_input("Ask the Writer for changes", placeholder="e.g. lead with peak-season risk")
                    if st.button("Revise memo", width="stretch", disabled=not notes):
                        with st.status("Writer revising…") as box:
                            run_stream(room.resume({"action": "revise", "notes": notes}, ss.thread), box)
                        st.rerun()
                with c3:
                    follow = st.text_input("Follow up question", placeholder="e.g. LTL national contract: ODFL vs CHRW")
                    if st.button("Ask follow up", width="stretch", disabled=not follow):
                        with st.status("Committee reconvening…", expanded=True) as box:
                            run_stream(room.resume({"action": "follow_up", "question": follow}, ss.thread), box)
                        st.rerun()
            elif state.get("final"):
                st.success("Allocation approved and saved to your long-term memory.", icon="💾")

with tab_eval:
    summary = config.RESULTS_DIR / "summary.md"
    if summary.exists():
        st.markdown(summary.read_text(encoding="utf-8"))
    else:
        st.info("Run `python eval/run_eval.py` to generate the evaluation report.")

with tab_how:
    arch = ROOT / "docs" / "ARCHITECTURE.md"
    if arch.exists():
        st.markdown(arch.read_text(encoding="utf-8"))

with tab_course:
    coverage = ROOT / "docs" / "COURSE_COVERAGE.md"
    if coverage.exists():
        st.markdown(coverage.read_text(encoding="utf-8"))

st.markdown(ui.footer(), unsafe_allow_html=True)
