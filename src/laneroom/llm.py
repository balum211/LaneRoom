"""Thin helpers around the chat model: one call, JSON parsing, and safe fallbacks."""
from __future__ import annotations

import json
import re
import threading
from typing import Any

from filingsight.llm import get_chat_model

from . import config

_JSON_BLOCK = re.compile(r"(\{.*\}|\[.*\])", re.S)

# Token usage per thread. Each LangGraph node runs in its own thread (the two advocates in parallel),
# so a node's _trace() can collect exactly the tokens its own LLM calls spent.
_usage = threading.local()


def _add_usage(tokens_in: int, tokens_out: int) -> None:
    _usage.calls = getattr(_usage, "calls", 0) + 1
    _usage.tokens_in = getattr(_usage, "tokens_in", 0) + tokens_in
    _usage.tokens_out = getattr(_usage, "tokens_out", 0) + tokens_out


def take_usage() -> dict:
    """Return and reset this thread's LLM usage: calls, tokens in/out and estimated USD cost."""
    calls, t_in, t_out = getattr(_usage, "calls", 0), getattr(_usage, "tokens_in", 0), getattr(_usage, "tokens_out", 0)
    _usage.calls = _usage.tokens_in = _usage.tokens_out = 0
    cost = (t_in * config.PRICE_IN_PER_M + t_out * config.PRICE_OUT_PER_M) / 1_000_000
    return {"llm_calls": calls, "tokens_in": t_in, "tokens_out": t_out, "cost_usd": round(cost, 6)}


def chat(system: str, user: str, temperature: float = 0.2) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage

    model = get_chat_model(temperature=temperature)
    reply = model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    meta = getattr(reply, "usage_metadata", None) or {}
    _add_usage(int(meta.get("input_tokens", 0)), int(meta.get("output_tokens", 0)))
    return str(reply.content)


def parse_json(text: str) -> Any:
    """Parse the first JSON object or array in a model reply (tolerates code fences and chatter)."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_BLOCK.search(text)
        if not m:
            raise
        return json.loads(m.group(1))


def chat_json(system: str, user: str, temperature: float = 0.2) -> Any:
    return parse_json(chat(system, user, temperature))
