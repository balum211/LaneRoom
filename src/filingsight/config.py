"""Central settings. Everything can be overridden with environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional: load a local .env when python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
EVAL_DIR = DATA_DIR / "eval"
INDEX_DIR = Path(os.getenv("FS_INDEX_DIR", ROOT / ".index"))


@dataclass(frozen=True)
class Filing:
    """One source document in the corpus."""

    company: str
    ticker: str
    form: str
    fiscal_year: int
    file: str
    # The 10-K body ends where the Exhibit Index starts. Pages after it are
    # exhibits (credit agreements, indentures) that only add retrieval noise.
    body_last_page: int
    # Financial years that the filing reports figures for (current + 2 prior).
    covered_years: tuple[int, ...] = field(default=())
    # True for documents that are not public filings (Armada's synthetic profile).
    synthetic: bool = False
    # Leading pages that hold the table of contents (Item headings there are not section starts).
    toc_pages: int = 4


FILINGS: tuple[Filing, ...] = (
    # Public carriers: FY2025 Form 10-K from SEC EDGAR (HTML printed to PDF).
    Filing("J.B. Hunt", "JBHT", "10-K", 2025, "jbht_2025.pdf", body_last_page=63, covered_years=(2023, 2024, 2025)),
    Filing("C.H. Robinson", "CHRW", "10-K", 2025, "chrw_2025.pdf", body_last_page=108, covered_years=(2023, 2024, 2025)),
    Filing("Old Dominion", "ODFL", "10-K", 2025, "odfl_2025.pdf", body_last_page=98, covered_years=(2023, 2024, 2025)),
    # Armada is privately held and files nothing with the SEC. This is a SYNTHETIC, clearly labelled
    # provider profile written for the demo (data/raw/armada_profile_synthetic.html).
    Filing("Armada", "ARMADA", "Profile (synthetic)", 2025, "armada_profile_synthetic.pdf", body_last_page=5,
           covered_years=(2024, 2025), synthetic=True, toc_pages=1),
)

COMPANIES = tuple(f.company for f in FILINGS)
SYNTHETIC_COMPANIES = tuple(f.company for f in FILINGS if f.synthetic)

# Ways people name each provider in a request (tickers, short names, common typos such as "ODLF").
# "LEPV" is how the brief named Armada; it is not a ticker for Armada (Armada is private).
ALIASES: dict[str, str] = {
    "J.B. Hunt": r"j\.?\s?b\.?\s?hunt|jbht|hunt",
    "C.H. Robinson": r"c\.?\s?h\.?\s?robinson|chrw|robinson",
    "Old Dominion": r"old dominion|odfl|odlf",
    "Armada": r"armada|lepv",
}


def company_pattern(company: str):
    import re

    return re.compile(rf"(?<![a-z])({ALIASES.get(company, re.escape(company))})(?![a-z])", re.I)


def companies_in(text: str) -> list[str]:
    """Providers named in a request, in knowledge-base order."""
    return [c for c in COMPANIES if company_pattern(c).search(text or "")]


COVERED_YEARS = sorted({y for f in FILINGS for y in f.covered_years})


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


# Chunking. all-MiniLM-L6-v2 truncates at 256 word-pieces (~1,000 characters of
# 10-K prose), so chunks are sized to fit inside the embedding window.
FIXED_CHUNK_SIZE = _env_int("FS_FIXED_CHUNK_SIZE", 900)
FIXED_CHUNK_OVERLAP = _env_int("FS_FIXED_CHUNK_OVERLAP", 150)
SEMANTIC_BREAKPOINT_PERCENTILE = _env_float("FS_SEMANTIC_PERCENTILE", 85)
SEMANTIC_MAX_CHARS = _env_int("FS_SEMANTIC_MAX_CHARS", 1100)
SEMANTIC_MIN_CHARS = _env_int("FS_SEMANTIC_MIN_CHARS", 200)

# Retrieval
CANDIDATES_K = _env_int("FS_CANDIDATES_K", 20)  # per retriever, before fusion
TOP_K = _env_int("FS_TOP_K", 5)  # chunks handed to the LLM
RRF_K = _env_int("FS_RRF_K", 60)
# Weighted RRF. 10-K questions lean on exact figures and names, so BM25 gets
# more say than dense similarity (tuned in eval/run_retrieval_eval.py).
DENSE_WEIGHT = _env_float("FS_DENSE_WEIGHT", 1.0)
BM25_WEIGHT = _env_float("FS_BM25_WEIGHT", 1.0)

# Reranker: "local" (no download, runs anywhere), "cross-encoder"
# (sentence-transformers ms-marco model), or "llm" (uses the chat model).
RERANKER = os.getenv("FS_RERANKER", "local")
CROSS_ENCODER_MODEL = os.getenv("FS_CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

# "I don't know" gate: if the best reranked chunk scores below this, refuse.
MIN_CONFIDENCE = _env_float("FS_MIN_CONFIDENCE", 0.60)  # local reranker scale
MIN_CONFIDENCE_CE = _env_float("FS_MIN_CONFIDENCE_CE", 0.05)  # cross-encoder sigmoid scale

# Default strategy used by the app (the evaluation picks the winner).
DEFAULT_CHUNKING = os.getenv("FS_CHUNKING", "semantic")

# LLM (OpenAI-compatible). Nebius is the default provider for the course.
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_BASE_URL = os.getenv("FS_LLM_BASE_URL", "https://api.studio.nebius.com/v1/" if NEBIUS_API_KEY else "")
LLM_MODEL = os.getenv("FS_LLM_MODEL", "meta-llama/Llama-3.3-70B-Instruct" if NEBIUS_API_KEY else "gpt-4.1-mini")
JUDGE_MODEL = os.getenv("FS_JUDGE_MODEL", LLM_MODEL)
LLM_TIMEOUT = _env_float("FS_LLM_TIMEOUT", 60)

# Latency budget from the one-liner (seconds, end to end).
LATENCY_BUDGET_S = _env_float("FS_LATENCY_BUDGET_S", 8)


def llm_api_key() -> str:
    return NEBIUS_API_KEY or OPENAI_API_KEY


def llm_available() -> bool:
    return bool(llm_api_key())
