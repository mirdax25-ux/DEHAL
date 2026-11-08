"""DEHAL v2 engine — veto hierarchy, no weighted fusion.

Evaluation order; first hard loss wins:
  1. hard errors            -> BLOCK
  2. price uncovered        -> BLOCK
  3. corrupt snapshot       -> ESCALATE (snapshot is not evidence, not a claim failure)
  4. quorum disagreement    -> ESCALATE
  5. raw_text contradiction-> ESCALATE
  6. observer conflict      -> ESCALATE (advisory only)
  7. otherwise              -> APPROVE
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime

from .hard import check_hard
from .grounding import price_covered, quorum_agrees, rounding_tolerance
from .semantic import NullObserver, raw_text_numbers_differ
from .snapshot import EvidenceSnapshot

DECISIONS = ("APPROVE", "BLOCK", "ESCALATE")


@dataclass(frozen=True)
class Verdict:
    decision: str
    reasons: tuple
    evidence_hashes: tuple
    evaluation_time: str
    claim_hash: str

    def to_json(self) -> str:
        """Byte-identical serialization: same inputs -> same bytes."""
        return json.dumps(
            {
                "decision": self.decision,
                "reasons": list(self.reasons),
                "evidence_hashes": list(self.evidence_hashes),
                "evaluation_time": self.evaluation_time,
                "claim_hash": self.claim_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def _claim_hash(claim: dict) -> str:
    return hashlib.sha256(
        json.dumps(claim, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def verify(claim: dict, snapshots: list, evaluation_time: datetime,
           observer=None) -> Verdict:
    """Deterministic verification of one structured claim against snapshots.

    The claim is an already-parsed dict (host responsibility). Snapshots are
    EvidenceSnapshot objects. evaluation_time is injected (never now()).
    """
    if observer is None:
        observer = NullObserver()

    hashes = tuple(s.sha256 for s in snapshots)
    chash = _claim_hash(claim)
    etime = evaluation_time.isoformat()

    def verdict(decision: str, reasons) -> Verdict:
        return Verdict(decision, tuple(reasons), hashes, etime, chash)

    # 1. hard errors
    hard_errors = check_hard(claim, evaluation_time)
    if hard_errors:
        return verdict("BLOCK", hard_errors)

    # 3a. corrupt snapshots (checked before grounding: corrupt != evidence)
    corrupt = [s.source_id for s in snapshots if s.is_corrupt()]
    if corrupt:
        return verdict("ESCALATE", ["corrupt_snapshot:" + sid for sid in corrupt])

    # 2. grounding veto
    tol = rounding_tolerance(claim.get("currency"))
    if not price_covered(snapshots, claim["price"], tol):
        return verdict("BLOCK", ["price_not_found_in_snapshots"])

    # 4. quorum
    if not quorum_agrees(snapshots, claim["price"], tol):
        return verdict("ESCALATE", ["source_disagreement"])

    # 5. deterministic raw-text contradiction
    if raw_text_numbers_differ(claim):
        return verdict("ESCALATE", ["raw_text_numbers_differ"])

    # 6. advisory observer (LLM if the host supplies one)
    obs = observer.observe(claim.get("raw_text", ""), claim)
    if obs.suggests_conflict:
        return verdict("ESCALATE", list(obs.notes) or ["observer_conflict"])

    # 7. approve
    return verdict("APPROVE", [])
