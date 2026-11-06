import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("LR_MEMORY_PATH", str(Path(tempfile.mkdtemp()) / "memory.json"))
os.environ.setdefault("LR_AGENT_MODE", "offline")
os.environ.setdefault("LR_TRACE_DIR", tempfile.mkdtemp())
os.environ.setdefault("LR_FEEDBACK_PATH", str(Path(tempfile.mkdtemp()) / "feedback.jsonl"))
