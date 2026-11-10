"""DEHAL v2 - deterministicka verifikacijska jezgra.

Pravila (predaja 2026-11-07, canvas dehal-v2-arhitektura):
- Verdikti: APPROVE / BLOCK / ESCALATE, fail-closed.
- LLM smije SAMO predloziti ESCALATE; grounding ima veto.
- fetch/now su IZVAN jezgre: snapshot i evaluation_time dolaze kao parametri.
- FLAG u dokazima -> ESCALATE.
- Svaki verdikt nosi SHA-256 provenanciju.

Status: NEPROVJERENO dok testove ne izvrsi netko tko ih nije pisao.
"""

from __future__ import annotations

import hashlib
from typing import List, Literal, Optional, TypedDict

CORE_VERSION = "DEHAL-v2.0.0"

Verdict = Literal["APPROVE", "BLOCK", "ESCALATE"]


class Evidence(TypedDict):
    id: str
    content: str
    sha256: str
    retrieved_at: str
    flags: List[str]


class CoreInput(TypedDict, total=False):
    claim: str
    snapshot: List[Evidence]        # fetch je izvan jezgre
    evaluation_time: str            # now() je izvan jezgre
    llm_proposal: Optional[str]     # jedina dozvoljena vrijednost: "ESCALATE"


class VerdictOutput(TypedDict):
    verdict: Verdict
    reasons: List[str]
    provenance_sha256: str
    evaluation_time: str
    core_version: str


def _canonical_sha256(parts: List[str]) -> str:
    canonical = "\u241f".join(parts).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def dehal_evaluate(inp: CoreInput) -> VerdictOutput:
    reasons: List[str] = []

    # 0) Fail-closed validacija ulaza
    claim = inp.get("claim")
    evaluation_time = inp.get("evaluation_time")
    snapshot = inp.get("snapshot")
    if not isinstance(claim, str) or not evaluation_time or not isinstance(snapshot, list):
        return {
            "verdict": "BLOCK",
            "reasons": ["R_INVALID_INPUT"],
            "provenance_sha256": "",
            "evaluation_time": str(evaluation_time or ""),
            "core_version": CORE_VERSION,
        }

    # 1) Grounding (deterministicki, bez LLM-a)
    if len(snapshot) == 0:
        grounding: Verdict = "BLOCK"
        reasons.append("R_NO_EVIDENCE_FAIL_CLOSED")
    elif any(ev.get("flags") for ev in snapshot):
        grounding = "ESCALATE"
        reasons.append("R_FLAG_ESCALATE")
    elif any(str(ev.get("content", "")).startswith("CONTRADICTS:") for ev in snapshot):
        grounding = "BLOCK"
        reasons.append("R_CONTRADICTION")
    else:
        norm = claim.strip().lower()
        supported = any(norm in str(ev.get("content", "")).lower() for ev in snapshot)
        grounding = "APPROVE" if supported else "ESCALATE"
        reasons.append("R_SUPPORTED_BY_EVIDENCE" if supported else "R_UNSUPPORTED_ESCALATE")

    # 2) LLM prijedlog: samo ESCALATE je valjan; nikad ne pobedjuje BLOCK (grounding veto)
    verdict = grounding
    llm_proposal = inp.get("llm_proposal")
    if llm_proposal is not None:
        if llm_proposal == "ESCALATE":
            if grounding != "BLOCK":
                verdict = "ESCALATE"
                reasons.append("R_LLM_ESCALATE_ACCEPTED")
            else:
                reasons.append("R_LLM_ESCALATE_VETOED_BY_GROUNDING")
        else:
            reasons.append("R_LLM_PROPOSAL_REJECTED_ONLY_ESCALATE_ALLOWED")

    # 3) SHA-256 provenancija (samo parametri, bez poziva vremena)
    ev_hashes = sorted(str(ev.get("sha256", "")) for ev in snapshot)
    provenance = _canonical_sha256([CORE_VERSION, evaluation_time, claim.strip(), "|".join(ev_hashes)])

    return {
        "verdict": verdict,
        "reasons": reasons,
        "provenance_sha256": provenance,
        "evaluation_time": evaluation_time,
        "core_version": CORE_VERSION,
    }
