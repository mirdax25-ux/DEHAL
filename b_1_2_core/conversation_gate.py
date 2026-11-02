from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class ConstraintRecord:
    constraint_id: str
    kind: str
    value: str
    active: bool = True
    satisfied: bool = False
    source_turn_id: str | None = None
    priority: int = 0
    supersedes: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("constraint_id", "kind", "value"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be non-empty string")
        if type(self.active) is not bool:
            raise TypeError("constraint.active must be bool")
        if type(self.satisfied) is not bool:
            raise TypeError("constraint.satisfied must be bool")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise TypeError("constraint.priority must be int")
        for field_name in ("source_turn_id", "supersedes"):
            value = getattr(self, field_name)
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise ValueError(f"{field_name} must be non-empty when supplied")


@dataclass(frozen=True)
class ConversationContract:
    goal_id: str
    referent_id: str
    candidate_goal_id: str
    candidate_referent_id: str
    constraints: tuple[ConstraintRecord, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "goal_id",
            "referent_id",
            "candidate_goal_id",
            "candidate_referent_id",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be non-empty string")
        if not isinstance(self.constraints, tuple):
            raise TypeError("constraints must be tuple")
        if any(not isinstance(item, ConstraintRecord) for item in self.constraints):
            raise TypeError("constraints must contain ConstraintRecord values")
        ids = [item.constraint_id for item in self.constraints]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate constraint_id")


@dataclass(frozen=True)
class ConversationGateResult:
    approved: bool
    reason: str
    failed_constraint_ids: tuple[str, ...]
    contract_sha256: str


def canonical_conversation_contract_sha256(contract: ConversationContract) -> str:
    payload = {
        "goal_id": contract.goal_id,
        "referent_id": contract.referent_id,
        "candidate_goal_id": contract.candidate_goal_id,
        "candidate_referent_id": contract.candidate_referent_id,
        "constraints": [
            {
                "constraint_id": item.constraint_id,
                "kind": item.kind,
                "value": item.value,
                "active": item.active,
                "satisfied": item.satisfied,
                "source_turn_id": item.source_turn_id,
                "priority": item.priority,
                "supersedes": item.supersedes,
            }
            for item in sorted(
                contract.constraints,
                key=lambda value: (value.priority, value.constraint_id),
            )
        ],
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def evaluate_conversation_contract(
    contract: ConversationContract,
) -> ConversationGateResult:
    if not isinstance(contract, ConversationContract):
        raise TypeError("contract must be ConversationContract")

    digest = canonical_conversation_contract_sha256(contract)

    if contract.candidate_goal_id != contract.goal_id:
        return ConversationGateResult(
            approved=False,
            reason="goal_mismatch",
            failed_constraint_ids=(),
            contract_sha256=digest,
        )

    if contract.candidate_referent_id != contract.referent_id:
        return ConversationGateResult(
            approved=False,
            reason="referent_mismatch",
            failed_constraint_ids=(),
            contract_sha256=digest,
        )

    failed = tuple(
        item.constraint_id
        for item in sorted(
            contract.constraints,
            key=lambda value: (-value.priority, value.constraint_id),
        )
        if item.active and not item.satisfied
    )
    if failed:
        return ConversationGateResult(
            approved=False,
            reason="active_constraint_failed",
            failed_constraint_ids=failed,
            contract_sha256=digest,
        )

    return ConversationGateResult(
        approved=True,
        reason="conversation_contract_satisfied",
        failed_constraint_ids=(),
        contract_sha256=digest,
    )
