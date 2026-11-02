from b_1_2_core import Verdict, canonical_receipt_sha256
from b_1_2_core.lifecycle import (
    ProjectState,
    authorize_mutation,
    freeze_project,
    reopen_project,
)


def test_freeze_requires_verified_checkpoint():
    result = freeze_project(
        project_id="b-1-2",
        current_state=ProjectState.ACTIVE,
        checkpoint_digest="sha256:abc",
        checkpoint_verified=False,
        human_approved=True,
        policy_version="2.0",
    )

    assert result.state is ProjectState.ACTIVE
    assert result.verdict is Verdict.BLOCK
    assert result.reason == "checkpoint_not_verified"


def test_freeze_requires_human_approval():
    result = freeze_project(
        project_id="b-1-2",
        current_state=ProjectState.ACTIVE,
        checkpoint_digest="sha256:abc",
        checkpoint_verified=True,
        human_approved=False,
        policy_version="2.0",
    )

    assert result.state is ProjectState.ACTIVE
    assert result.verdict is Verdict.ESCALATE
    assert result.reason == "human_approval_required_for_freeze"


def test_verified_human_approved_freeze_moves_to_frozen():
    result = freeze_project(
        project_id="b-1-2",
        current_state=ProjectState.ACTIVE,
        checkpoint_digest="sha256:abc",
        checkpoint_verified=True,
        human_approved=True,
        policy_version="2.0",
    )

    assert result.state is ProjectState.FROZEN
    assert result.verdict is Verdict.APPROVE
    assert result.reason == "verified_checkpoint_frozen"
    assert result.receipt["transition"] == "freeze"
    assert result.receipt["from_state"] == "active"
    assert result.receipt["to_state"] == "frozen"
    assert result.receipt["checkpoint_digest"] == "sha256:abc"
    assert result.receipt["checkpoint_verified"] is True
    assert result.receipt["human_approved"] is True


def test_freezing_same_checkpoint_is_idempotent():
    result = freeze_project(
        project_id="b-1-2",
        current_state=ProjectState.FROZEN,
        checkpoint_digest="sha256:abc",
        current_checkpoint_digest="sha256:abc",
        checkpoint_verified=True,
        human_approved=True,
        policy_version="2.0",
    )

    assert result.state is ProjectState.FROZEN
    assert result.verdict is Verdict.APPROVE
    assert result.reason == "already_frozen_same_checkpoint"


def test_frozen_project_rejects_different_checkpoint_through_freeze_path():
    result = freeze_project(
        project_id="b-1-2",
        current_state=ProjectState.FROZEN,
        checkpoint_digest="sha256:new",
        current_checkpoint_digest="sha256:old",
        checkpoint_verified=True,
        human_approved=True,
        policy_version="2.0",
    )

    assert result.state is ProjectState.FROZEN
    assert result.verdict is Verdict.BLOCK
    assert result.reason == "frozen_checkpoint_mismatch"


def test_frozen_scope_blocks_normal_mutation():
    result = authorize_mutation(
        project_id="b-1-2",
        current_state=ProjectState.FROZEN,
        policy_version="2.0",
    )

    assert result.verdict is Verdict.BLOCK
    assert result.reason == "project_frozen_controlled_reopen_required"


def test_active_scope_allows_normal_mutation():
    result = authorize_mutation(
        project_id="b-1-2",
        current_state=ProjectState.ACTIVE,
        policy_version="2.0",
    )

    assert result.verdict is Verdict.APPROVE
    assert result.reason == "project_active"


def test_reopen_requires_human_approval():
    result = reopen_project(
        project_id="b-1-2",
        current_state=ProjectState.FROZEN,
        checkpoint_digest="sha256:abc",
        reopen_reason="verified defect requires repair",
        human_approved=False,
        policy_version="2.0",
    )

    assert result.state is ProjectState.FROZEN
    assert result.verdict is Verdict.ESCALATE
    assert result.reason == "human_approval_required_for_reopen"


def test_reopen_requires_recorded_reason():
    try:
        reopen_project(
            project_id="b-1-2",
            current_state=ProjectState.FROZEN,
            checkpoint_digest="sha256:abc",
            reopen_reason="",
            human_approved=True,
            policy_version="2.0",
        )
    except ValueError as exc:
        assert "reopen_reason" in str(exc)
    else:
        raise AssertionError("empty reopen reason must fail closed")


def test_human_approved_reopen_moves_to_active_and_records_reason():
    result = reopen_project(
        project_id="b-1-2",
        current_state=ProjectState.FROZEN,
        checkpoint_digest="sha256:abc",
        reopen_reason="verified defect requires repair",
        human_approved=True,
        policy_version="2.0",
    )

    assert result.state is ProjectState.ACTIVE
    assert result.verdict is Verdict.APPROVE
    assert result.reason == "controlled_reopen_approved"
    assert result.receipt["transition"] == "reopen"
    assert result.receipt["from_state"] == "frozen"
    assert result.receipt["to_state"] == "active"
    assert result.receipt["checkpoint_digest"] == "sha256:abc"
    assert result.receipt["reopen_reason"] == "verified defect requires repair"


def test_reopen_from_active_is_rejected():
    result = reopen_project(
        project_id="b-1-2",
        current_state=ProjectState.ACTIVE,
        checkpoint_digest="sha256:abc",
        reopen_reason="not applicable",
        human_approved=True,
        policy_version="2.0",
    )

    assert result.state is ProjectState.ACTIVE
    assert result.verdict is Verdict.BLOCK
    assert result.reason == "invalid_reopen_transition"


def test_lifecycle_receipts_are_deterministic_for_same_inputs():
    a = freeze_project(
        project_id="b-1-2",
        current_state=ProjectState.ACTIVE,
        checkpoint_digest="sha256:abc",
        checkpoint_verified=True,
        human_approved=True,
        policy_version="2.0",
    )
    b = freeze_project(
        project_id="b-1-2",
        current_state=ProjectState.ACTIVE,
        checkpoint_digest="sha256:abc",
        checkpoint_verified=True,
        human_approved=True,
        policy_version="2.0",
    )

    assert a.receipt == b.receipt


def test_lifecycle_receipt_contains_verifiable_canonical_sha256():
    result = freeze_project(
        project_id="b-1-2",
        current_state=ProjectState.ACTIVE,
        checkpoint_digest="sha256:abc",
        checkpoint_verified=True,
        human_approved=True,
        policy_version="2.0",
    )

    assert len(result.receipt["receipt_sha256"]) == 64
    assert result.receipt["receipt_sha256"] == canonical_receipt_sha256(result.receipt)


def test_reopen_reason_changes_lifecycle_receipt_hash():
    first = reopen_project(
        project_id="b-1-2",
        current_state=ProjectState.FROZEN,
        checkpoint_digest="sha256:abc",
        reopen_reason="verified defect A",
        human_approved=True,
        policy_version="2.0",
    )
    second = reopen_project(
        project_id="b-1-2",
        current_state=ProjectState.FROZEN,
        checkpoint_digest="sha256:abc",
        reopen_reason="verified defect B",
        human_approved=True,
        policy_version="2.0",
    )

    assert first.receipt["receipt_sha256"] != second.receipt["receipt_sha256"]
