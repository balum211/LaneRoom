"""Input, evidence and output guardrails.

* Input: refuse prompt injection, empty or oversized requests, off-topic requests and providers outside
  the knowledge base; flag stock buy/sell questions (LaneRoom allocates freight, it does not pick stocks).
* Evidence: strip instruction-like lines that a document could smuggle into an agent prompt.
* Output: no stock buy/sell instructions in the memo, and a disclaimer is always appended.
"""
from __future__ import annotations

import re

from filingsight import config as fs_config

MAX_QUESTION_CHARS = 600

_INJECTION = re.compile(
    r"(ignore (all |any )?(previous|prior|above) (instructions|prompts?)|disregard (the )?(system|previous)|"
    r"system prompt|you are now|developer mode|jailbreak|reveal your (prompt|instructions)|act as (an? )?(unfiltered|dan))",
    re.I,
)
_ADVICE = re.compile(r"\b(should i (buy|sell|short|invest)|buy or sell|price target|will (the )?stock (go|rise|fall)|"
                     r"guarantee(d)? return|(buy|sell) (the )?(stock|shares))\b", re.I)
_LOGISTICS_HINT = re.compile(
    r"\b(tender|allocat|award|lane|load|freight|carrier|3pl|shipper|ship|truck|ltl|ftl|dry van|reefer|intermodal|"
    r"capacity|surge|peak|season|on[- ]time|rate|per mile|cost|claims?|service|reliab|resilien|contract|rfp|bid|"
    r"broker|asset|dedicated|logistic|supply chain|network|terminal|fleet|driver|risk|financial|health|compare|"
    r"vs|versus|incumbent|backup|primary|weekly|national|dallas|atlanta|chicago|los angeles|transport)\w*",
    re.I,
)
# Common carriers and 3PLs people may ask about that are NOT in the knowledge base.
_OTHER_COMPANIES = re.compile(
    r"\b(schneider|knight[- ]swift|swift|werner|landstar|xpo|saia|fedex|united parcel|estes|r\+l carriers|ryder|heartland|"
    r"echo global|tql|total quality logistics|uber freight|convoy|arcbest|yellow|tforce|ch2m|maersk|dhl|"
    r"expeditors|gxo|amazon freight|tesla|apple)\b",
    re.I,
)
_EVIDENCE_INJECTION = re.compile(r"(?im)^.*(ignore (all |any )?(previous|prior) instructions|system prompt|you are an ai).*$")
_OUTPUT_ADVICE = re.compile(
    r"\b(you should (buy|sell|short) (the )?(stock|shares)|we recommend (buying|selling) (the )?(stock|shares)|"
    r"strong (buy|sell)|(buy|sell) (the|this) stock|guaranteed returns?)\b",
    re.I,
)


def check_input(question: str) -> dict:
    """Return {"allowed": bool, "reason": str, "notes": [str]}."""
    q = (question or "").strip()
    notes: list[str] = []
    if not q:
        return {"allowed": False, "reason": "Please describe the lane or tender you want the committee to review.", "notes": notes}
    if len(q) > MAX_QUESTION_CHARS:
        return {"allowed": False, "reason": f"Please keep the request under {MAX_QUESTION_CHARS} characters.", "notes": notes}
    if _INJECTION.search(q):
        return {"allowed": False, "reason": "That request looks like an attempt to override LaneRoom's instructions, so it was blocked.", "notes": notes}
    known = fs_config.companies_in(q)
    others = sorted({m.group(0).title() for m in _OTHER_COMPANIES.finditer(q)})
    corpus = ", ".join(fs_config.COMPANIES)
    if others and not known:
        return {"allowed": False,
                "reason": f"{', '.join(others)} is not in LaneRoom's knowledge base yet. It currently covers {corpus}.",
                "notes": notes}
    if others:
        notes.append(f"{', '.join(others)} is not in the knowledge base; the committee compares {', '.join(known)} only.")
    if not known and not _LOGISTICS_HINT.search(q):
        return {"allowed": False,
                "reason": f"LaneRoom answers freight tender and carrier-selection questions about {corpus}.",
                "notes": notes}
    if _ADVICE.search(q):
        notes.append("LaneRoom does not give stock advice. It recommends a freight tender allocation instead.")
    if any(c in fs_config.SYNTHETIC_COMPANIES for c in (known or fs_config.COMPANIES)):
        notes.append("Armada is privately held: its evidence is a synthetic, self-reported profile, not an SEC filing.")
    return {"allowed": True, "reason": "", "notes": notes}


def sanitize_evidence_text(text: str) -> str:
    return _EVIDENCE_INJECTION.sub("[line removed by guardrail]", text)


def check_output(memo: str) -> tuple[str, list[str]]:
    """Soften stock-advice language and make sure the disclaimer is present."""
    from .config import DISCLAIMER

    flags: list[str] = []
    if _OUTPUT_ADVICE.search(memo):
        flags.append("Removed stock buy/sell language from the memo.")
        memo = _OUTPUT_ADVICE.sub("[freight assessment only, not investment advice]", memo)
    if DISCLAIMER not in memo:
        memo = memo.rstrip() + f"\n\n---\n*{DISCLAIMER}*\n"
    return memo, flags
