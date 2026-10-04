import pytest

from bodulskihal_core.lifecycle import ProjectState, freeze_project, reopen_project


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
        "project_id": "bodulskihal",
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
            project_id="bodulskihal",
            current_state=state,
            checkpoint_digest="sha256:checkpoint",
            reopen_reason="confirmed regression requires repair",
            human_approved=invalid_value,
            policy_version="2.1",
        )
