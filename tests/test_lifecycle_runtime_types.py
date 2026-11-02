import pytest

from b_1_2_core.lifecycle import (
    ProjectState,
    authorize_mutation,
    freeze_project,
    reopen_project,
)


NON_BOOLEAN_INPUTS = ["false", "true", 0, 1, None, [], {"approved": True}]


@pytest.mark.parametrize("invalid_value", NON_BOOLEAN_INPUTS)
@pytest.mark.parametrize("field", ["checkpoint_verified", "human_approved"])
@pytest.mark.parametrize(
    "state,current_digest",
    [
        (ProjectState.ACTIVE, None),
        (ProjectState.FROZEN, "sha256:checkpoint"),
        (ProjectState.FROZEN, "sha256:other"),
    ],
    ids=["active", "frozen-idempotent", "frozen-mismatch"],
)
def test_freeze_rejects_non_boolean_authority_inputs(
    invalid_value, field, state, current_digest
):
    kwargs = {
        "project_id": "b-1-2",
        "current_state": state,
        "checkpoint_digest": "sha256:checkpoint",
        "current_checkpoint_digest": current_digest,
        "checkpoint_verified": True,
        "human_approved": True,
        "policy_version": "2.1",
    }
    kwargs[field] = invalid_value

    with pytest.raises(TypeError, match=f"^{field} must be bool$"):
        freeze_project(**kwargs)


@pytest.mark.parametrize("invalid_value", NON_BOOLEAN_INPUTS)
@pytest.mark.parametrize("state", [ProjectState.ACTIVE, ProjectState.FROZEN])
def test_reopen_rejects_non_boolean_human_approval(invalid_value, state):
    with pytest.raises(TypeError, match="^human_approved must be bool$"):
        reopen_project(
            project_id="b-1-2",
            current_state=state,
            checkpoint_digest="sha256:checkpoint",
            reopen_reason="confirmed regression requires repair",
            human_approved=invalid_value,
            policy_version="2.1",
        )


@pytest.mark.parametrize(
    "operation",
    ["freeze", "mutation", "reopen"],
)
def test_lifecycle_rejects_untyped_project_state(operation):
    if operation == "freeze":
        call = lambda: freeze_project(
            project_id="b-1-2",
            current_state="active",
            checkpoint_digest="sha256:checkpoint",
            checkpoint_verified=True,
            human_approved=True,
            policy_version="2.1",
        )
    elif operation == "mutation":
        call = lambda: authorize_mutation(
            project_id="b-1-2",
            current_state="frozen",
            policy_version="2.1",
        )
    else:
        call = lambda: reopen_project(
            project_id="b-1-2",
            current_state="frozen",
            checkpoint_digest="sha256:checkpoint",
            reopen_reason="verified defect requires repair",
            human_approved=True,
            policy_version="2.1",
        )

    with pytest.raises(TypeError, match="^current_state must be ProjectState$"):
        call()


@pytest.mark.parametrize("invalid_digest", ["", " ", 0, False, [], {}])
def test_freeze_rejects_invalid_current_checkpoint_digest(invalid_digest):
    with pytest.raises(
        (TypeError, ValueError),
        match="^current_checkpoint_digest must be non-empty$",
    ):
        freeze_project(
            project_id="b-1-2",
            current_state=ProjectState.FROZEN,
            checkpoint_digest="sha256:checkpoint",
            current_checkpoint_digest=invalid_digest,
            checkpoint_verified=True,
            human_approved=True,
            policy_version="2.1",
        )
