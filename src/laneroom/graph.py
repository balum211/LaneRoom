"""The LaneRoom tender committee as a LangGraph state machine.

    guard ──(blocked)──────────────────────────────────────────────► refuse
      │
    planner ──► researcher ─┐        (parallel)
            └─► quant ──────┤
                            ├─► cost ─────┐   (parallel advocates)
                            └─► service ──┤
                                          ▼
                                   rebuttal ─► verifier ──(unsupported, < 2 retries)──► revise ─► verifier
                                                   │
                                                   ▼
                                     judge (allocation %) ─► writer ─► human_review (interrupt)
                                                          ├─ approve ──► finalize (save to memory)
                                                          ├─ revise ───► writer
                                                          └─ follow_up ► guard (new question, memory kept)
"""
from __future__ import annotations

import operator
import time
import uuid
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from . import agents


class LaneState(TypedDict, total=False):
    question: str
    user_id: str
    mode: str  # "auto" | "offline"
    inject_faulty: bool
    via_mcp: bool
    profile: dict
    past_memos: list
    guard: dict
    refused: bool
    refusal_reason: str
    plan: dict
    evidence: list
    metrics: list
    lane_metrics: list
    cost_claims: list
    service_claims: list
    rebuttal: dict
    attempts: int
    judge: dict
    memo: str
    output_flags: list
    review: dict
    final: bool
    trace: Annotated[list, operator.add]


NODE_LABELS = {
    "guard": "Guardrail", "planner": "Planner", "researcher": "Researcher", "quant": "Quant",
    "cost": "Cost advocate", "service": "Resilience advocate", "rebuttal": "Rebuttal round", "verifier": "Verifier",
    "revise": "Revise (retry)", "judge": "Judge", "writer": "Writer", "human_review": "Human review",
    "finalize": "Finalize", "refuse": "Refuse",
}


def build_graph(checkpointer=None):
    g = StateGraph(LaneState)
    g.add_node("guard", agents.input_guard)
    g.add_node("refuse", agents.refuse)
    g.add_node("planner", agents.planner)
    g.add_node("researcher", agents.researcher)
    g.add_node("quant", agents.quant)
    g.add_node("cost", agents.cost_advocate)
    g.add_node("service", agents.service_advocate)
    g.add_node("rebuttal", agents.rebuttal)
    g.add_node("verifier", agents.verifier)
    g.add_node("revise", agents.revise)
    g.add_node("judge", agents.judge)
    g.add_node("writer", agents.writer)
    g.add_node("human_review", agents.human_review)
    g.add_node("finalize", agents.finalize)

    g.add_edge(START, "guard")
    g.add_conditional_edges("guard", lambda s: "refuse" if s.get("refused") else "planner",
                            {"refuse": "refuse", "planner": "planner"})
    g.add_edge("refuse", END)
    g.add_edge("planner", "researcher")
    g.add_edge("planner", "quant")
    g.add_edge(["researcher", "quant"], "cost")
    g.add_edge(["researcher", "quant"], "service")
    g.add_edge(["cost", "service"], "rebuttal")
    g.add_edge("rebuttal", "verifier")
    g.add_conditional_edges("verifier", agents.after_verifier, {"revise": "revise", "judge": "judge"})
    g.add_edge("revise", "verifier")
    g.add_edge("judge", "writer")
    g.add_edge("writer", "human_review")
    g.add_conditional_edges("human_review", agents.after_review,
                            {"writer": "writer", "guard": "guard", "finalize": "finalize"})
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())


class LaneRoom:
    """Convenience wrapper used by the app, the eval and the tests."""

    def __init__(self, checkpointer=None):
        self.graph = build_graph(checkpointer)

    @staticmethod
    def new_thread() -> dict:
        # run_name and tags label the run in LangSmith when LANGSMITH_TRACING=true
        return {"configurable": {"thread_id": str(uuid.uuid4())}, "run_name": "LaneRoom tender committee", "tags": ["laneroom"]}

    def stream(self, inputs: dict | Command, config: dict):
        """Yield (node, update) pairs as each agent finishes."""
        for chunk in self.graph.stream(inputs, config, stream_mode="updates"):
            for node, update in chunk.items():
                yield node, update

    def start(self, question: str, config: dict, **options) -> Any:
        return self.stream({"question": question, "trace": [], **options}, config)

    def resume(self, decision: dict, config: dict):
        return self.stream(Command(resume=decision), config)

    def state(self, config: dict) -> dict:
        return self.graph.get_state(config).values

    def waiting_for_review(self, config: dict) -> bool:
        return "human_review" in (self.graph.get_state(config).next or ())

    def run(self, question: str, approve: bool = True, **options) -> dict:
        """Run end to end (auto-approving the human review) and return the final state."""
        config = self.new_thread()
        t = time.perf_counter()
        for _ in self.start(question, config, **options):
            pass
        if approve and self.waiting_for_review(config):
            for _ in self.resume({"action": "approve"}, config):
                pass
        state = dict(self.state(config))
        state["elapsed_s"] = round(time.perf_counter() - t, 2)
        return state
