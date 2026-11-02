from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .engine import Verdict, canonical_receipt_sha256


class ProjectState(str, Enum):
    ACTIVE = "active"
    FROZEN = "frozen"


@dataclass(frozen=True)
class LifecycleResult:
    state: ProjectState
    verdict: Verdict
    reason: str
    receipt: dict


def _non_empty(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty")
    return value.strip()


def _validate_bool(value: bool, name: str) -> None:
    if type(value) is not bool:
        raise TypeError(f"{name} must be bool")


def _validate_state(value: ProjectState) -> None:
    if not isinstance(value, ProjectState):
        raise TypeError("current_state must be ProjectState")


def _receipt(
    *,
    project_id: str,
    transition: str,
    from_state: ProjectState,
    to_state: ProjectState,
    checkpoint_digest: str | None,
    checkpoint_verified: bool | None,
    human_approved: bool | None,
    policy_version: str,
    reason: str,
    reopen_reason: str | None = None,
) -> dict:
    receipt = {
        "subsystem": "project_lifecycle",
        "policy_version": policy_version,
        "project_id": project_id,
        "transition": transition,
        "from_state": from_state.value,
        "to_state": to_state.value,
        "checkpoint_digest": checkpoint_digest,
        "checkpoint_verified": checkpoint_verified,
        "human_approved": human_approved,
        "reason": reason,
        "reopen_reason": reopen_reason,
    }
    receipt["receipt_sha256"] = canonical_receipt_sha256(receipt)
    return receipt


def freeze_project(
    *,
    project_id: str,
    current_state: ProjectState,
    checkpoint_digest: str,
    checkpoint_verified: bool,
    human_approved: bool,
    policy_version: str,
    current_checkpoint_digest: str | None = None,
) -> LifecycleResult:
    project_id = _non_empty(project_id, "project_id")
    checkpoint_digest = _non_empty(checkpoint_digest, "checkpoint_digest")
    policy_version = _non_empty(policy_version, "policy_version")
    _validate_state(current_state)
    _validate_bool(checkpoint_verified, "checkpoint_verified")
    _validate_bool(human_approved, "human_approved")
    if current_checkpoint_digest is not None:
        current_checkpoint_digest = _non_empty(
            current_checkpoint_digest,
            "current_checkpoint_digest",
        )

    if current_state is ProjectState.FROZEN:
        if current_checkpoint_digest == checkpoint_digest:
            reason = "already_frozen_same_checkpoint"
            return LifecycleResult(
                state=ProjectState.FROZEN,
                verdict=Verdict.APPROVE,
                reason=reason,
                receipt=_receipt(
                    project_id=project_id,
                    transition="freeze",
                    from_state=ProjectState.FROZEN,
                    to_state=ProjectState.FROZEN,
                    checkpoint_digest=checkpoint_digest,
                    checkpoint_verified=checkpoint_verified,
                    human_approved=human_approved,
                    policy_version=policy_version,
                    reason=reason,
                ),
            )

        reason = "frozen_checkpoint_mismatch"
        return LifecycleResult(
            state=ProjectState.FROZEN,
            verdict=Verdict.BLOCK,
            reason=reason,
            receipt=_receipt(
                project_id=project_id,
                transition="freeze",
                from_state=ProjectState.FROZEN,
                to_state=ProjectState.FROZEN,
                checkpoint_digest=checkpoint_digest,
                checkpoint_verified=checkpoint_verified,
                human_approved=human_approved,
                policy_version=policy_version,
                reason=reason,
            ),
        )

    if not checkpoint_verified:
        reason = "checkpoint_not_verified"
        return LifecycleResult(
            state=ProjectState.ACTIVE,
            verdict=Verdict.BLOCK,
            reason=reason,
            receipt=_receipt(
                project_id=project_id,
                transition="freeze",
                from_state=ProjectState.ACTIVE,
                to_state=ProjectState.ACTIVE,
                checkpoint_digest=checkpoint_digest,
                checkpoint_verified=False,
                human_approved=human_approved,
                policy_version=policy_version,
                reason=reason,
            ),
        )

    if not human_approved:
        reason = "human_approval_required_for_freeze"
        return LifecycleResult(
            state=ProjectState.ACTIVE,
            verdict=Verdict.ESCALATE,
            reason=reason,
            receipt=_receipt(
                project_id=project_id,
                transition="freeze",
                from_state=ProjectState.ACTIVE,
                to_state=ProjectState.ACTIVE,
                checkpoint_digest=checkpoint_digest,
                checkpoint_verified=True,
                human_approved=False,
                policy_version=policy_version,
                reason=reason,
            ),
        )

    reason = "verified_checkpoint_frozen"
    return LifecycleResult(
        state=ProjectState.FROZEN,
        verdict=Verdict.APPROVE,
        reason=reason,
        receipt=_receipt(
            project_id=project_id,
            transition="freeze",
            from_state=ProjectState.ACTIVE,
            to_state=ProjectState.FROZEN,
            checkpoint_digest=checkpoint_digest,
            checkpoint_verified=True,
            human_approved=True,
            policy_version=policy_version,
            reason=reason,
        ),
    )


def authorize_mutation(
    *,
    project_id: str,
    current_state: ProjectState,
    policy_version: str,
) -> LifecycleResult:
    project_id = _non_empty(project_id, "project_id")
    policy_version = _non_empty(policy_version, "policy_version")
    _validate_state(current_state)

    if current_state is ProjectState.FROZEN:
        reason = "project_frozen_controlled_reopen_required"
        verdict = Verdict.BLOCK
    else:
        reason = "project_active"
        verdict = Verdict.APPROVE

    return LifecycleResult(
        state=current_state,
        verdict=verdict,
        reason=reason,
        receipt=_receipt(
            project_id=project_id,
            transition="mutation_gate",
            from_state=current_state,
            to_state=current_state,
            checkpoint_digest=None,
            checkpoint_verified=None,
            human_approved=None,
            policy_version=policy_version,
            reason=reason,
        ),
    )


def reopen_project(
    *,
    project_id: str,
    current_state: ProjectState,
    checkpoint_digest: str,
    reopen_reason: str,
    human_approved: bool,
    policy_version: str,
) -> LifecycleResult:
    project_id = _non_empty(project_id, "project_id")
    checkpoint_digest = _non_empty(checkpoint_digest, "checkpoint_digest")
    reopen_reason = _non_empty(reopen_reason, "reopen_reason")
    policy_version = _non_empty(policy_version, "policy_version")
    _validate_state(current_state)
    _validate_bool(human_approved, "human_approved")

    if current_state is not ProjectState.FROZEN:
        reason = "invalid_reopen_transition"
        return LifecycleResult(
            state=current_state,
            verdict=Verdict.BLOCK,
            reason=reason,
            receipt=_receipt(
                project_id=project_id,
                transition="reopen",
                from_state=current_state,
                to_state=current_state,
                checkpoint_digest=checkpoint_digest,
                checkpoint_verified=True,
                human_approved=human_approved,
                policy_version=policy_version,
                reason=reason,
                reopen_reason=reopen_reason,
            ),
        )

    if not human_approved:
        reason = "human_approval_required_for_reopen"
        return LifecycleResult(
            state=ProjectState.FROZEN,
            verdict=Verdict.ESCALATE,
            reason=reason,
            receipt=_receipt(
                project_id=project_id,
                transition="reopen",
                from_state=ProjectState.FROZEN,
                to_state=ProjectState.FROZEN,
                checkpoint_digest=checkpoint_digest,
                checkpoint_verified=True,
                human_approved=False,
                policy_version=policy_version,
                reason=reason,
                reopen_reason=reopen_reason,
            ),
        )

    reason = "controlled_reopen_approved"
    return LifecycleResult(
        state=ProjectState.ACTIVE,
        verdict=Verdict.APPROVE,
        reason=reason,
        receipt=_receipt(
            project_id=project_id,
            transition="reopen",
            from_state=ProjectState.FROZEN,
            to_state=ProjectState.ACTIVE,
            checkpoint_digest=checkpoint_digest,
            checkpoint_verified=True,
            human_approved=True,
            policy_version=policy_version,
            reason=reason,
            reopen_reason=reopen_reason,
        ),
    )
