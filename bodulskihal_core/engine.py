from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable, Mapping, Sequence

from .runtime_provenance import RuntimeProvenance, current_runtime_provenance

ALGORITHM_VERSION = "2.1.2"


class ClaimType(str, Enum):
    UNCLASSIFIED = "unclassified"
    OBSERVATION = "observation"
    INFERENCE = "inference"
    ESTIMATE = "estimate"
    ACTION_STATE = "action_state"
    RISK_SENSITIVE = "risk_sensitive"


class Classification(str, Enum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    ESTIMATE = "ESTIMATE"
    UNKNOWN = "UNKNOWN"
    REFUTED = "REFUTED"
    CONFLICT = "CONFLICT"


class Verdict(str, Enum):
    APPROVE = "APPROVE"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Directness(str, Enum):
    DIRECT = "direct"
    INDIRECT = "indirect"


class SourceRole(str, Enum):
    EXECUTOR = "executor"
    VERIFIER = "verifier"
    EXTERNAL = "external"


class EvidenceOrigin(str, Enum):
    EXTERNAL_SOURCE = "external_source"
    TOOL_OBSERVATION = "tool_observation"
    COMPUTED_RESULT = "computed_result"
    MEMORY = "memory"
    USER_ASSERTION = "user_assertion"
    USER_SELF_REPORT = "user_self_report"
    USER_PREFERENCE = "user_preference"
    USER_INSTRUCTION = "user_instruction"


class AuthorityScope(str, Enum):
    EXTERNAL_FACT = "external_fact"
    SYSTEM_STATE = "system_state"
    USER_SELF_REPORT = "user_self_report"
    USER_PREFERENCE = "user_preference"
    USER_INSTRUCTION = "user_instruction"


class AnswerabilityStatus(str, Enum):
    ANSWERABLE = "answerable"
    PARTIALLY_ANSWERABLE = "partially_answerable"
    UNDERSPECIFIED = "underspecified"
    FALSE_PREMISE = "false_premise"
    CONTRADICTORY_INPUT = "contradictory_input"
    NEEDS_CLARIFICATION = "needs_clarification"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    claim_type: ClaimType
    risk: RiskLevel = RiskLevel.LOW
    consequential: bool = True
    authority_scope: AuthorityScope = AuthorityScope.EXTERNAL_FACT
    answerability: AnswerabilityStatus = AnswerabilityStatus.ANSWERABLE


@dataclass(frozen=True)
class Evidence:
    source_id: str
    supports: bool
    observed_at: datetime
    directness: Directness
    post_action: bool = False
    eligible: bool = True
    evidence_id: str | None = None
    source_role: SourceRole = SourceRole.EXTERNAL
    source_ref: str | None = None
    independence_group: str | None = None
    content_sha256: str | None = None
    origin: EvidenceOrigin = EvidenceOrigin.EXTERNAL_SOURCE
    authority_scope: AuthorityScope = AuthorityScope.EXTERNAL_FACT


@dataclass(frozen=True)
class Policy:
    version: str
    max_age_seconds: int
    reject_future_evidence: bool = True
    require_independent_action_evidence: bool = True
    medium_risk_min_independent_sources: int = 2
    require_runtime_provenance: bool = False


@dataclass(frozen=True)
class VerificationResult:
    claim: Claim
    classification: Classification
    verdict: Verdict
    reason: str
    receipt: dict
    failure_record: dict | None


@dataclass(frozen=True)
class CompoundResult:
    results: tuple[VerificationResult, ...]
    verdict: Verdict


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _effective_evidence_id(item: Evidence) -> str:
    return item.evidence_id or item.source_id


def _validate_human_approval(value: bool, *, field_name: str = "human_approved") -> None:
    if type(value) is not bool:
        raise TypeError(f"{field_name} must be bool")


def _validate_non_empty_string(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty string")


def _validate_provenance_inputs(
    claim: Claim, evidence: Sequence[Evidence], policy: Policy
) -> None:
    _validate_non_empty_string(claim.claim_id, "claim_id")
    _validate_non_empty_string(claim.text, "claim.text")
    _validate_non_empty_string(policy.version, "policy.version")
    if not isinstance(claim.authority_scope, AuthorityScope):
        raise TypeError("claim.authority_scope must be AuthorityScope")
    if not isinstance(claim.answerability, AnswerabilityStatus):
        raise TypeError("claim.answerability must be AnswerabilityStatus")
    for item in evidence:
        _validate_non_empty_string(item.source_id, "evidence.source_id")
        if not isinstance(item.origin, EvidenceOrigin):
            raise TypeError("evidence.origin must be EvidenceOrigin")
        if not isinstance(item.authority_scope, AuthorityScope):
            raise TypeError("evidence.authority_scope must be AuthorityScope")



def _validate_common_inputs(
    evidence: Sequence[Evidence], *, policy: Policy, evaluation_time: datetime
) -> None:
    if not _is_aware(evaluation_time):
        raise ValueError("evaluation_time must be timezone-aware")
    if policy.max_age_seconds < 0:
        raise ValueError("max_age_seconds must be non-negative")
    if policy.medium_risk_min_independent_sources < 1:
        raise ValueError("medium_risk_min_independent_sources must be at least 1")
    if type(policy.require_runtime_provenance) is not bool:
        raise TypeError("require_runtime_provenance must be bool")
    for item in evidence:
        if not _is_aware(item.observed_at):
            raise ValueError("observed_at must be timezone-aware")
        if item.evidence_id is not None and not item.evidence_id.strip():
            raise ValueError("evidence_id must be non-empty when supplied")
        if item.source_ref is not None and not item.source_ref.strip():
            raise ValueError("source_ref must be non-empty when supplied")
        if item.independence_group is not None and not item.independence_group.strip():
            raise ValueError("independence_group must be non-empty when supplied")
        if item.content_sha256 is not None:
            digest = item.content_sha256.lower()
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError("content_sha256 must be a 64-character hexadecimal SHA-256")


def _validate_evidence_gate_types(evidence: Sequence[Evidence]) -> None:
    for item in evidence:
        if type(item.supports) is not bool:
            raise TypeError("evidence.supports must be bool")
        if type(item.post_action) is not bool:
            raise TypeError("evidence.post_action must be bool")
        if type(item.eligible) is not bool:
            raise TypeError("evidence.eligible must be bool")


def _validate_evidence_identity(evidence: Sequence[Evidence]) -> None:
    ids = [_effective_evidence_id(item) for item in evidence]
    if len(ids) != len(set(ids)):
        raise ValueError(
            "duplicate evidence_id; duplicate source_id fallback identity is not allowed"
        )


def _is_fresh(item: Evidence, *, policy: Policy, evaluation_time: datetime) -> bool:
    age = (evaluation_time - item.observed_at).total_seconds()
    if policy.reject_future_evidence and age < 0:
        return False
    return 0 <= age <= policy.max_age_seconds


def _eligible_evidence(
    evidence: Sequence[Evidence], *, policy: Policy, evaluation_time: datetime
) -> tuple[Evidence, ...]:
    return tuple(
        item
        for item in evidence
        if item.eligible and _is_fresh(item, policy=policy, evaluation_time=evaluation_time)
    )


_USER_ORIGINS = {
    EvidenceOrigin.USER_ASSERTION,
    EvidenceOrigin.USER_SELF_REPORT,
    EvidenceOrigin.USER_PREFERENCE,
    EvidenceOrigin.USER_INSTRUCTION,
}


def _authority_allows(claim: Claim, item: Evidence) -> bool:
    if item.authority_scope is not claim.authority_scope:
        return False

    if claim.authority_scope in {AuthorityScope.EXTERNAL_FACT, AuthorityScope.SYSTEM_STATE}:
        return item.origin in {
            EvidenceOrigin.EXTERNAL_SOURCE,
            EvidenceOrigin.TOOL_OBSERVATION,
            EvidenceOrigin.COMPUTED_RESULT,
        }
    if claim.authority_scope is AuthorityScope.USER_PREFERENCE:
        return item.origin in {
            EvidenceOrigin.USER_PREFERENCE,
            EvidenceOrigin.USER_SELF_REPORT,
            EvidenceOrigin.TOOL_OBSERVATION,
        }
    if claim.authority_scope is AuthorityScope.USER_INSTRUCTION:
        return item.origin in {
            EvidenceOrigin.USER_INSTRUCTION,
            EvidenceOrigin.TOOL_OBSERVATION,
        }
    if claim.authority_scope is AuthorityScope.USER_SELF_REPORT:
        return item.origin in {
            EvidenceOrigin.USER_SELF_REPORT,
            EvidenceOrigin.TOOL_OBSERVATION,
        }
    return False


def _authorized_evidence(
    claim: Claim, evidence: Sequence[Evidence]
) -> tuple[Evidence, ...]:
    return tuple(item for item in evidence if _authority_allows(claim, item))


def _classify(claim: Claim, eligible: Sequence[Evidence]) -> Classification:
    if claim.answerability is AnswerabilityStatus.CONTRADICTORY_INPUT:
        return Classification.CONFLICT
    if claim.answerability is not AnswerabilityStatus.ANSWERABLE:
        return Classification.UNKNOWN
    if claim.claim_type is ClaimType.UNCLASSIFIED:
        return Classification.UNKNOWN

    supporting = tuple(item for item in eligible if item.supports)
    contradicting = tuple(item for item in eligible if not item.supports)
    if supporting and contradicting:
        return Classification.CONFLICT
    if contradicting:
        return Classification.REFUTED
    if not supporting:
        return Classification.UNKNOWN

    if claim.claim_type is ClaimType.INFERENCE:
        return Classification.INFERENCE
    if claim.claim_type is ClaimType.ESTIMATE:
        return Classification.ESTIMATE

    if not any(item.directness is Directness.DIRECT for item in supporting):
        return Classification.INFERENCE

    return Classification.FACT


def _has_direct_post_action_evidence(eligible: Sequence[Evidence]) -> bool:
    return any(
        item.supports
        and item.post_action
        and item.directness is Directness.DIRECT
        for item in eligible
    )


def _has_independent_post_action_evidence(eligible: Sequence[Evidence]) -> bool:
    return any(
        item.supports
        and item.post_action
        and item.directness is Directness.DIRECT
        and item.source_role in {SourceRole.VERIFIER, SourceRole.EXTERNAL}
        for item in eligible
    )


def _independent_supporting_source_count(eligible: Sequence[Evidence]) -> int:
    # Extra metadata may join known identities, never split the same provenance.
    # Connected components preserve overlap transitively, regardless of input order.
    parents: list[int] = []
    seen: dict[tuple[str, str], int] = {}

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for item in eligible:
        if not (
            item.supports
            and item.directness is Directness.DIRECT
            and item.source_role in {SourceRole.VERIFIER, SourceRole.EXTERNAL}
        ):
            continue
        index = len(parents)
        parents.append(index)
        identities = [("source", item.source_id.strip())]
        if item.source_ref is not None:
            identities.append(("ref", item.source_ref.strip()))
        if item.independence_group is not None:
            identities.append(("group", item.independence_group.strip()))
        if item.content_sha256 is not None:
            identities.append(("content", item.content_sha256.lower()))
        for identity in identities:
            previous = seen.setdefault(identity, index)
            parents[root(index)] = root(previous)

    return len({root(index) for index in range(len(parents))})


def _decide_verdict(
    claim: Claim,
    classification: Classification,
    eligible: Sequence[Evidence],
    *,
    policy: Policy,
    human_approved: bool,
    authority_rejected: bool = False,
    runtime_provenance_verified: bool = False,
) -> tuple[Verdict, str]:
    if policy.require_runtime_provenance and not runtime_provenance_verified:
        return Verdict.BLOCK, "runtime_provenance_unverified"

    if claim.answerability is AnswerabilityStatus.NEEDS_CLARIFICATION:
        return Verdict.ESCALATE, "answerability_needs_clarification"
    if claim.answerability is not AnswerabilityStatus.ANSWERABLE:
        return Verdict.BLOCK, f"answerability_{claim.answerability.value}"
    if claim.claim_type is ClaimType.UNCLASSIFIED:
        return Verdict.BLOCK, "unclassified_claim"

    if classification is Classification.CONFLICT:
        return Verdict.BLOCK, "eligible_contradiction"
    if classification is Classification.REFUTED:
        return Verdict.BLOCK, "claim_refuted_by_eligible_evidence"
    if classification is Classification.UNKNOWN:
        if authority_rejected:
            return Verdict.BLOCK, "insufficient_authorized_evidence"
        return Verdict.BLOCK, "insufficient_eligible_evidence"
    if classification is Classification.INFERENCE:
        return Verdict.BLOCK, "inference_not_fact"
    if classification is Classification.ESTIMATE:
        return Verdict.BLOCK, "estimate_not_fact"

    if claim.claim_type is ClaimType.ACTION_STATE:
        if not _has_direct_post_action_evidence(eligible):
            return Verdict.BLOCK, "missing_post_action_final_state_evidence"
        if (
            policy.require_independent_action_evidence
            and not _has_independent_post_action_evidence(eligible)
        ):
            return Verdict.BLOCK, "missing_independent_post_action_evidence"

    if (
        claim.risk is RiskLevel.MEDIUM
        and _independent_supporting_source_count(eligible)
        < policy.medium_risk_min_independent_sources
    ):
        return Verdict.ESCALATE, "additional_independent_evidence_required"

    if claim.risk is RiskLevel.HIGH and not human_approved:
        return Verdict.ESCALATE, "human_approval_required"

    return Verdict.APPROVE, "fact_with_required_gates"


def _iso(value: datetime) -> str:
    return value.isoformat()


def _make_failure_record(claim: Claim, verdict: Verdict, reason: str) -> dict | None:
    if verdict is Verdict.APPROVE:
        return None
    return {
        "record_type": "expected_gate",
        "claim_id": claim.claim_id,
        "failure_mode": reason,
        "root_cause": "verification_gate_not_satisfied",
        "guardrail": f"preserve_{verdict.value.lower()}_until_new_eligible_evidence_or_required_approval",
        "regression_test_required": False,
        "version_change_required": False,
    }


def make_failure_evolution_record(
    *,
    failure_mode: str,
    root_cause: str,
    guardrail: str,
    regression_test: str,
) -> dict:
    fields = {
        "failure_mode": failure_mode,
        "root_cause": root_cause,
        "guardrail": guardrail,
        "regression_test": regression_test,
    }
    for name, value in fields.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be non-empty")
    return {
        "record_type": "failure_evolution",
        "failure_mode": failure_mode.strip(),
        "root_cause": root_cause.strip(),
        "guardrail": guardrail.strip(),
        "regression_test": regression_test.strip(),
        "regression_test_required": True,
        "version_change_required": True,
    }


def canonical_receipt_sha256(receipt: Mapping) -> str:
    payload = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_sha256"
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _make_receipt(
    *,
    claim: Claim,
    policy: Policy,
    evaluation_time: datetime,
    all_evidence: Sequence[Evidence],
    eligible: Sequence[Evidence],
    classification: Classification,
    verdict: Verdict,
    reason: str,
    human_approved: bool,
    authority_rejected: Sequence[Evidence] = (),
    runtime_provenance: RuntimeProvenance | None = None,
) -> dict:
    eligible_ids = {_effective_evidence_id(item) for item in eligible}
    sorted_all = sorted(
        all_evidence,
        key=lambda item: (_effective_evidence_id(item), item.source_id),
    )

    supporting_sources = sorted(item.source_id for item in eligible if item.supports)
    contradicting_sources = sorted(item.source_id for item in eligible if not item.supports)
    supporting_evidence_ids = sorted(
        _effective_evidence_id(item) for item in eligible if item.supports
    )
    contradicting_evidence_ids = sorted(
        _effective_evidence_id(item) for item in eligible if not item.supports
    )
    if claim.risk is RiskLevel.HIGH:
        human_gate = "approved" if human_approved else "required"
    else:
        human_gate = "not_required"

    receipt = {
        "algorithm_version": ALGORITHM_VERSION,
        "policy_version": policy.version,
        "evaluation_time": _iso(evaluation_time),
        "claim": {
            "id": claim.claim_id,
            "text": claim.text,
            "type": claim.claim_type.value,
            "risk": claim.risk.value,
            "consequential": claim.consequential,
            "authority_scope": claim.authority_scope.value,
            "answerability": claim.answerability.value,
        },
        "classification": classification.value,
        "verdict": verdict.value,
        "reason": reason,
        "human_approved": human_approved,
        "runtime_provenance": (
            runtime_provenance.as_dict()
            if runtime_provenance is not None
            else current_runtime_provenance().as_dict()
        ),
        "gates": {
            "eligible_source_count": len(eligible),
            "supporting_sources": supporting_sources,
            "contradicting_sources": contradicting_sources,
            "supporting_evidence_ids": supporting_evidence_ids,
            "contradicting_evidence_ids": contradicting_evidence_ids,
            "contradiction_count": len(contradicting_evidence_ids),
            "authority_rejected_evidence_ids": sorted(
                _effective_evidence_id(item) for item in authority_rejected
            ),
            "post_action_verified": (
                _has_direct_post_action_evidence(eligible)
                if claim.claim_type is ClaimType.ACTION_STATE
                else None
            ),
            "independent_post_action_verified": (
                _has_independent_post_action_evidence(eligible)
                if claim.claim_type is ClaimType.ACTION_STATE
                else None
            ),
            "independent_supporting_source_count": _independent_supporting_source_count(eligible),
            "independent_supporting_group_count": _independent_supporting_source_count(eligible),
            "medium_risk_required_sources": (
                policy.medium_risk_min_independent_sources
                if claim.risk is RiskLevel.MEDIUM
                else None
            ),
            "human_gate": human_gate,
            "runtime_provenance_required": policy.require_runtime_provenance,
        },
        "evidence": [
            {
                "evidence_id": _effective_evidence_id(item),
                "source_id": item.source_id,
                "source_role": item.source_role.value,
                "source_ref": item.source_ref,
                "independence_group": item.independence_group,
                "content_sha256": (
                    item.content_sha256.lower()
                    if item.content_sha256 is not None
                    else None
                ),
                "origin": item.origin.value,
                "authority_scope": item.authority_scope.value,
                "supports": item.supports,
                "observed_at": _iso(item.observed_at),
                "directness": item.directness.value,
                "post_action": item.post_action,
                "caller_eligible": item.eligible,
                "eligible_at_evaluation": _effective_evidence_id(item) in eligible_ids,
            }
            for item in sorted_all
        ],
    }
    receipt["receipt_sha256"] = canonical_receipt_sha256(receipt)
    return receipt


def verify_claim(
    claim: Claim,
    evidence: Iterable[Evidence],
    *,
    policy: Policy,
    evaluation_time: datetime,
    human_approved: bool = False,
) -> VerificationResult:
    _validate_human_approval(human_approved)
    evidence_seq = tuple(evidence)
    _validate_provenance_inputs(claim, evidence_seq, policy)
    _validate_evidence_gate_types(evidence_seq)
    _validate_evidence_identity(evidence_seq)
    _validate_common_inputs(evidence_seq, policy=policy, evaluation_time=evaluation_time)

    fresh_eligible = _eligible_evidence(
        evidence_seq,
        policy=policy,
        evaluation_time=evaluation_time,
    )
    eligible = _authorized_evidence(claim, fresh_eligible)
    authority_rejected = tuple(
        item for item in fresh_eligible if item not in eligible
    )
    runtime_provenance = current_runtime_provenance()
    classification = _classify(claim, eligible)
    verdict, reason = _decide_verdict(
        claim,
        classification,
        eligible,
        policy=policy,
        human_approved=human_approved,
        authority_rejected=bool(authority_rejected),
        runtime_provenance_verified=runtime_provenance.verified,
    )
    receipt = _make_receipt(
        claim=claim,
        policy=policy,
        evaluation_time=evaluation_time,
        all_evidence=evidence_seq,
        eligible=eligible,
        classification=classification,
        verdict=verdict,
        reason=reason,
        human_approved=human_approved,
        authority_rejected=authority_rejected,
        runtime_provenance=runtime_provenance,
    )
    failure_record = _make_failure_record(claim, verdict, reason)
    return VerificationResult(
        claim=claim,
        classification=classification,
        verdict=verdict,
        reason=reason,
        receipt=receipt,
        failure_record=failure_record,
    )


def verify_compound(
    claims: Sequence[Claim],
    evidence_by_claim: Mapping[str, Iterable[Evidence]],
    *,
    policy: Policy,
    evaluation_time: datetime,
    human_approvals: Mapping[str, bool] | None = None,
) -> CompoundResult:
    if not claims:
        raise ValueError("at least one claim is required")
    claim_ids = [claim.claim_id for claim in claims]
    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("duplicate claim_id")

    approvals = human_approvals or {}
    for approval_claim_id, approval in approvals.items():
        _validate_human_approval(
            approval,
            field_name=f"human approval for {approval_claim_id}",
        )

    results = tuple(
        verify_claim(
            claim,
            evidence_by_claim.get(claim.claim_id, ()),
            policy=policy,
            evaluation_time=evaluation_time,
            human_approved=approvals.get(claim.claim_id, False),
        )
        for claim in claims
    )

    consequential = [result for result in results if result.claim.consequential]
    if any(result.verdict is Verdict.ESCALATE for result in consequential):
        overall = Verdict.ESCALATE
    elif any(result.verdict is not Verdict.APPROVE for result in consequential):
        overall = Verdict.BLOCK
    else:
        overall = Verdict.APPROVE

    return CompoundResult(results=results, verdict=overall)
