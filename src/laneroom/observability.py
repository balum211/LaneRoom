"""Run logs and the human feedback loop.

* Every finished run appends its agent trace (per node: time, LLM calls, tokens, cost) to
  ``data/traces/runs.jsonl``. LangSmith tracing turns on on top of this when LANGSMITH_TRACING=true.
* Every human review decision (approve, revise, follow up) is appended to ``data/eval/feedback.jsonl``.
  ``python eval/run_eval.py --feedback`` replays those requests as regression cases.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import config


def _append(path: Path, record: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass  # logging must never break a run


def run_totals(trace: list[dict]) -> dict:
    """Sum time, LLM calls, tokens and cost over a run's trace."""
    return {
        "ms": sum(t.get("ms", 0) for t in trace),
        "llm_calls": sum(t.get("llm_calls", 0) for t in trace),
        "tokens_in": sum(t.get("tokens_in", 0) for t in trace),
        "tokens_out": sum(t.get("tokens_out", 0) for t in trace),
        "cost_usd": round(sum(t.get("cost_usd", 0.0) for t in trace), 6),
    }


def log_run(state: dict) -> None:
    trace = state.get("trace", [])
    _append(config.TRACE_DIR / "runs.jsonl", {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "user_id": state.get("user_id", "default"),
        "mode": "llm" if config.llm_enabled(state.get("mode")) else "offline",
        "question": state.get("question", ""),
        "verdict": state.get("judge", {}).get("verdict", ""),
        "totals": run_totals(trace),
        "trace": trace,
    })


def log_feedback(state: dict, decision: dict) -> None:
    claims = state.get("cost_claims", []) + state.get("service_claims", [])
    _append(config.FEEDBACK_PATH, {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "user_id": state.get("user_id", "default"),
        "question": state.get("question", ""),
        "action": decision.get("action", "approve"),
        "notes": decision.get("notes") or decision.get("question") or "",
        "verdict": state.get("judge", {}).get("verdict", ""),
        "claims_verified": sum(c.get("status") == "supported" for c in claims),
        "claims_total": len(claims),
    })


def load_feedback(path: Path | None = None) -> list[dict]:
    path = path or config.FEEDBACK_PATH
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows
