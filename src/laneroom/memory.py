"""Long-term memory: the shipper's procurement mandate and summaries of past approved allocations.

Stored as a small JSON file (data/memory/store.json, git-ignored). Short-term memory
(the conversation and the paused graph) lives in the LangGraph checkpointer.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import config

MANDATES = ("balanced", "cost-first", "service-first")
DEFAULT_PROFILE = {
    "mandate": "balanced",  # balanced | cost-first | service-first
    "preferred_metrics": ["acceptance_pct", "on_time_pct", "rate_per_mile"],
    "incumbent": "",  # optional: the carrier that holds the lane today
}
_LOCK = threading.Lock()


class MemoryStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or config.MEMORY_PATH)

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {"users": {}}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_user(self, user_id: str) -> dict:
        with _LOCK:
            user = self._load()["users"].get(user_id, {})
        profile = {**DEFAULT_PROFILE, **user.get("profile", {})}
        if profile["mandate"] not in MANDATES:
            profile["mandate"] = DEFAULT_PROFILE["mandate"]
        return {"profile": profile, "memos": user.get("memos", [])}

    def save_profile(self, user_id: str, profile: dict) -> None:
        with _LOCK:
            data = self._load()
            user = data["users"].setdefault(user_id, {})
            user["profile"] = {**DEFAULT_PROFILE, **user.get("profile", {}), **profile}
            self._save(data)

    def add_memo(self, user_id: str, question: str, summary: str, allocation: dict) -> None:
        with _LOCK:
            data = self._load()
            user = data["users"].setdefault(user_id, {})
            memos = user.setdefault("memos", [])
            memos.append({
                "question": question, "summary": summary, "allocation": allocation,
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            })
            user["memos"] = memos[-10:]
            self._save(data)

    def clear(self, user_id: str) -> None:
        with _LOCK:
            data = self._load()
            data["users"].pop(user_id, None)
            self._save(data)
