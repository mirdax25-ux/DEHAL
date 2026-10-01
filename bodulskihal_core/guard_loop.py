from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable

from .engine import (
    Claim,
    Classification,
    Evidence,
    Policy,
    VerificationResult,
    Verdict,
    verify_claim,
)


GUARD_VERSION = "2.0.0"


class Realism(str, Enum):
    POSSIBLE = "possible"
    UNCERTAIN = "uncertain"
    IMPOSSIBLE = "impossible"


class GuardStage(str, Enum):
    SELF_CHECK = "self_check"
    VERIFICATION = "verification"


@dataclass(frozen=True)
class SelfCheck:
    realism: Realism
    known: tuple[str, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    assumptions_reviewed: bool
    unknowns_reviewed: bool


@dataclass(frozen=True)
class GuardResult:
    stage: GuardStage
    classification: Classification
    verdict: Verdict
    reason: str
    verification: VerificationResult | None
    receipt: dict


def _validate_self_check(check: SelfCheck) -> None:
    if not isinstance(check, SelfCheck):
        raise TypeError("self_check must be SelfCheck")
    if not isinstance(check.realism, Realism):
        raise TypeError("self_check.realism must be Realism")
    if type(check.assumptions_reviewed) is not bool:
        raise TypeError("assumptions_reviewed must be bool")
    if type(check.unknowns_reviewed) is not bool:
        raise TypeError("unknowns_reviewed must be bool")

    for field_name, values in (
        ("known", check.known),
        ("assumptions", check.assumptions),
        ("unknowns", check.unknowns),
    ):
        if not isinstance(values, tuple):
            raise TypeError(f"{field_name} must be tuple")
        if any(not isinstance(item, str) or not item.strip() for item in values):
            raise ValueError(f"{field_name} items must be non-empty strings")


def _self_check_payload(check: SelfCheck) -> dict:
    return {
        "realism": check.realism.value,
        "known": list(check.known),
        "assumptions": list(check.assumptions),
        "unknowns": list(check.unknowns),
        "assumptions_reviewed": check.assumptions_reviewed,
        "unknowns_reviewed": check.unknowns_reviewed,
    }


def _self_check_result(
    *,
    claim: Claim,
    check: SelfCheck,
    verdict: Verdict,
    reason: str,
) -> GuardResult:
    receipt = {
        "guard_version": GUARD_VERSION,
        "claim_id": claim.claim_id,
        "stage": GuardStage.SELF_CHECK.value,
        "self_check": _self_check_payload(check),
        "verification": None,
        "classification": Classification.UNKNOWN.value,
        "verdict": verdict.value,
        "reason": reason,
    }
    return GuardResult(
        stage=GuardStage.SELF_CHECK,
        classification=Classification.UNKNOWN,
        verdict=verdict,
        reason=reason,
        verification=None,
        receipt=receipt,
    )


def run_guard_loop(
    *,
    claim: Claim,
    evidence: Iterable[Evidence],
    self_check: SelfCheck,
    policy: Policy,
    evaluation_time: datetime,
    human_approved: bool = False,
) -> GuardResult:
    _validate_self_check(self_check)

    if self_check.realism is Realism.IMPOSSIBLE:
        return _self_check_result(
            claim=claim,
            check=self_check,
            verdict=Verdict.BLOCK,
            reason="self_check_impossible",
        )

    if self_check.realism is Realism.UNCERTAIN:
        return _self_check_result(
            claim=claim,
            check=self_check,
            verdict=Verdict.ESCALATE,
            reason="self_check_uncertain",
        )

    if not self_check.assumptions_reviewed:
        return _self_check_result(
            claim=claim,
            check=self_check,
            verdict=Verdict.ESCALATE,
            reason="assumptions_not_reviewed",
        )

    if not self_check.unknowns_reviewed:
        return _self_check_result(
            claim=claim,
            check=self_check,
            verdict=Verdict.ESCALATE,
            reason="unknowns_not_reviewed",
        )

    verification = verify_claim(
        claim,
        evidence,
        policy=policy,
        evaluation_time=evaluation_time,
        human_approved=human_approved,
    )

    receipt = {
        "guard_version": GUARD_VERSION,
        "claim_id": claim.claim_id,
        "stage": GuardStage.VERIFICATION.value,
        "self_check": _self_check_payload(self_check),
        "verification": {
            "classification": verification.classification.value,
            "verdict": verification.verdict.value,
            "reason": verification.reason,
            "receipt": verification.receipt,
        },
        "classification": verification.classification.value,
        "verdict": verification.verdict.value,
        "reason": verification.reason,
    }

    return GuardResult(
        stage=GuardStage.VERIFICATION,
        classification=verification.classification,
        verdict=verification.verdict,
        reason=verification.reason,
        verification=verification,
        receipt=receipt,
    )
