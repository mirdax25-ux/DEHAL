from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from .engine import (
    ALGORITHM_VERSION,
    AnswerabilityStatus,
    AuthorityScope,
    Claim,
    ClaimType,
    Directness,
    Evidence,
    EvidenceOrigin,
    Policy,
    RiskLevel,
    SourceRole,
    verify_claim,
    verify_compound,
)

SCHEMA_VERSION = 3


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must be object")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{path} must be list")
    return value


def _required(obj: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in obj:
        raise ValueError(f"missing required field: {path}.{key}")
    return obj[key]


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{path} must be non-empty string")
    return value


def _optional_string(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _string(value, path)


def _bool(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{path} must be bool")
    return value


def _int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{path} must be int")
    return value


def _datetime(value: Any, path: str) -> datetime:
    raw = _string(value, path)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{path} must be ISO 8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{path} must be timezone-aware")
    return parsed


def _enum(enum_type, value: Any, path: str):
    raw = _string(value, path)
    try:
        return enum_type(raw)
    except ValueError as exc:
        raise ValueError(f"invalid {path}: {raw}") from exc


def _claim(raw: Any, path: str = "claim") -> Claim:
    obj = _mapping(raw, path)
    return Claim(
        claim_id=_string(_required(obj, "id", path), f"{path}.id"),
        text=_string(_required(obj, "text", path), f"{path}.text"),
        claim_type=_enum(ClaimType, _required(obj, "type", path), f"{path}.type"),
        risk=_enum(RiskLevel, obj.get("risk", RiskLevel.LOW.value), f"{path}.risk"),
        consequential=_bool(obj.get("consequential", True), f"{path}.consequential"),
        authority_scope=_enum(
            AuthorityScope,
            obj.get("authority_scope", AuthorityScope.EXTERNAL_FACT.value),
            f"{path}.authority_scope",
        ),
        answerability=_enum(
            AnswerabilityStatus,
            obj.get("answerability", AnswerabilityStatus.ANSWERABLE.value),
            f"{path}.answerability",
        ),
    )


def _evidence(raw: Any, path: str) -> Evidence:
    obj = _mapping(raw, path)
    return Evidence(
        source_id=_string(_required(obj, "source_id", path), f"{path}.source_id"),
        supports=_bool(_required(obj, "supports", path), f"{path}.supports"),
        observed_at=_datetime(_required(obj, "observed_at", path), f"{path}.observed_at"),
        directness=_enum(Directness, _required(obj, "directness", path), f"{path}.directness"),
        post_action=_bool(obj.get("post_action", False), f"{path}.post_action"),
        eligible=_bool(obj.get("eligible", True), f"{path}.eligible"),
        evidence_id=_optional_string(obj.get("evidence_id"), f"{path}.evidence_id"),
        source_role=_enum(
            SourceRole,
            obj.get("source_role", SourceRole.EXTERNAL.value),
            f"{path}.source_role",
        ),
        source_ref=_optional_string(obj.get("source_ref"), f"{path}.source_ref"),
        content_sha256=_optional_string(
            obj.get("content_sha256"),
            f"{path}.content_sha256",
        ),
        origin=_enum(
            EvidenceOrigin,
            obj.get("origin", EvidenceOrigin.EXTERNAL_SOURCE.value),
            f"{path}.origin",
        ),
        authority_scope=_enum(
            AuthorityScope,
            obj.get("authority_scope", AuthorityScope.EXTERNAL_FACT.value),
            f"{path}.authority_scope",
        ),
    )


def _policy(raw: Any) -> Policy:
    path = "policy"
    obj = _mapping(raw, path)
    return Policy(
        version=_string(_required(obj, "version", path), "policy.version"),
        max_age_seconds=_int(_required(obj, "max_age_seconds", path), "policy.max_age_seconds"),
        reject_future_evidence=_bool(
            obj.get("reject_future_evidence", True),
            "policy.reject_future_evidence",
        ),
        require_independent_action_evidence=_bool(
            obj.get("require_independent_action_evidence", True),
            "policy.require_independent_action_evidence",
        ),
        medium_risk_min_independent_sources=_int(
            obj.get("medium_risk_min_independent_sources", 2),
            "policy.medium_risk_min_independent_sources",
        ),
        require_runtime_provenance=_bool(
            obj.get("require_runtime_provenance", False),
            "policy.require_runtime_provenance",
        ),
    )


def _result_dict(result) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "classification": result.classification.value,
        "verdict": result.verdict.value,
        "reason": result.reason,
        "receipt": result.receipt,
        "failure_record": result.failure_record,
    }


def verify_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    obj = _mapping(payload, "payload")
    claim = _claim(_required(obj, "claim", "payload"))
    evidence_raw = _list(_required(obj, "evidence", "payload"), "payload.evidence")
    evidence = tuple(
        _evidence(item, f"evidence[{index}]")
        for index, item in enumerate(evidence_raw)
    )
    policy = _policy(_required(obj, "policy", "payload"))
    evaluation_time = _datetime(
        _required(obj, "evaluation_time", "payload"),
        "payload.evaluation_time",
    )
    human_approved = _bool(obj.get("human_approved", False), "payload.human_approved")
    return _result_dict(
        verify_claim(
            claim,
            evidence,
            policy=policy,
            evaluation_time=evaluation_time,
            human_approved=human_approved,
        )
    )


def verify_compound_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    obj = _mapping(payload, "payload")
    claims_raw = _list(_required(obj, "claims", "payload"), "payload.claims")
    claims = tuple(_claim(item, f"claims[{index}]") for index, item in enumerate(claims_raw))
    claim_ids = {claim.claim_id for claim in claims}

    evidence_map_raw = _mapping(
        _required(obj, "evidence_by_claim", "payload"),
        "payload.evidence_by_claim",
    )
    unknown_evidence_ids = set(evidence_map_raw) - claim_ids
    if unknown_evidence_ids:
        raise ValueError(
            "evidence_by_claim contains unknown claim id: "
            + ", ".join(sorted(unknown_evidence_ids))
        )

    evidence_by_claim = {
        claim_id: tuple(
            _evidence(item, f"evidence_by_claim.{claim_id}[{index}]")
            for index, item in enumerate(
                _list(evidence_map_raw.get(claim_id, []), f"evidence_by_claim.{claim_id}")
            )
        )
        for claim_id in claim_ids
    }

    approvals_raw = _mapping(obj.get("human_approvals", {}), "payload.human_approvals")
    unknown_approval_ids = set(approvals_raw) - claim_ids
    if unknown_approval_ids:
        raise ValueError(
            "human_approvals contains unknown claim id: "
            + ", ".join(sorted(unknown_approval_ids))
        )
    approvals = {
        claim_id: _bool(value, f"human_approvals.{claim_id}")
        for claim_id, value in approvals_raw.items()
    }

    policy = _policy(_required(obj, "policy", "payload"))
    evaluation_time = _datetime(
        _required(obj, "evaluation_time", "payload"),
        "payload.evaluation_time",
    )
    result = verify_compound(
        claims,
        evidence_by_claim,
        policy=policy,
        evaluation_time=evaluation_time,
        human_approvals=approvals,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "verdict": result.verdict.value,
        "results": [_result_dict(item) for item in result.results],
    }
