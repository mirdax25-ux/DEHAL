from datetime import datetime, timezone

import pytest

from b_1_2_core import Classification, Policy, Verdict
from b_1_2_core.ingestion import (
    TypeAuthority,
    collect_normalize_evidence,
    verify_model_response,
)


T0 = datetime(2026, 10, 1, 8, 30, tzinfo=timezone.utc)
POLICY = Policy(version="2.0", max_age_seconds=300)


def record(
    source_id: str,
    *,
    supports: bool = True,
    directness: str = "direct",
    post_action: bool = False,
):
    return {
        "source_id": source_id,
        "supports": supports,
        "observed_at": T0.isoformat(),
        "directness": directness,
        "post_action": post_action,
    }


def test_collect_normalize_evidence_parses_supplied_collector_records():
    normalized = collect_normalize_evidence(
        {
            "atom-0001": [
                record("source-b"),
                record("source-a", directness="indirect"),
            ]
        },
        known_atom_ids={"atom-0001"},
    )

    items = normalized["atom-0001"]
    assert [item.source_id for item in items] == ["source-a", "source-b"]
    assert items[0].directness.value == "indirect"
    assert items[1].directness.value == "direct"
    assert items[0].observed_at == T0


def test_collect_normalize_evidence_rejects_unknown_atom_id():
    with pytest.raises(ValueError, match="unknown atom_id"):
        collect_normalize_evidence(
            {"atom-9999": [record("source-a")]},
            known_atom_ids={"atom-0001"},
        )


def test_collect_normalize_evidence_rejects_duplicate_source_identity():
    with pytest.raises(ValueError, match="duplicate source_id"):
        collect_normalize_evidence(
            {
                "atom-0001": [
                    record("same"),
                    record("same"),
                ]
            },
            known_atom_ids={"atom-0001"},
        )


def test_executor_cannot_smuggle_observation_label_into_fact():
    result = verify_model_response(
        "[OBSERVATION] The result is correct.",
        evidence_by_atom={"atom-0001": [record("source-a")]},
        authority=TypeAuthority.EXECUTOR,
        policy=POLICY,
        evaluation_time=T0,
    )

    item = result.results[0]
    assert item.classification is Classification.UNKNOWN
    assert item.verdict is Verdict.BLOCK
    assert item.reason == "unclassified_claim"


def test_trusted_policy_observation_can_flow_to_fact_approve():
    result = verify_model_response(
        "[OBSERVATION] The result is correct.",
        evidence_by_atom={"atom-0001": [record("source-a")]},
        authority=TypeAuthority.TRUSTED_POLICY,
        policy=POLICY,
        evaluation_time=T0,
    )

    item = result.results[0]
    assert item.classification is Classification.FACT
    assert item.verdict is Verdict.APPROVE


def test_action_state_without_post_action_proof_blocks_end_to_end():
    result = verify_model_response(
        "[ACTION_STATE] Export completed.",
        evidence_by_atom={"atom-0001": [record("request-log")]},
        authority=TypeAuthority.EXECUTOR,
        policy=POLICY,
        evaluation_time=T0,
    )

    item = result.results[0]
    assert item.classification is Classification.FACT
    assert item.verdict is Verdict.BLOCK
    assert item.reason == "missing_post_action_final_state_evidence"


def test_action_state_with_post_action_proof_can_approve_end_to_end():
    result = verify_model_response(
        "[ACTION_STATE] Export completed.",
        evidence_by_atom={
            "atom-0001": [
                record("provider-final-state", post_action=True),
            ]
        },
        authority=TypeAuthority.EXECUTOR,
        policy=POLICY,
        evaluation_time=T0,
    )

    assert result.results[0].verdict is Verdict.APPROVE


def test_risk_sensitive_clause_escalates_without_human_approval():
    result = verify_model_response(
        "[RISK_SENSITIVE] Publish externally.",
        evidence_by_atom={"atom-0001": [record("policy-check")]},
        authority=TypeAuthority.EXECUTOR,
        policy=POLICY,
        evaluation_time=T0,
    )

    item = result.results[0]
    assert item.classification is Classification.FACT
    assert item.verdict is Verdict.ESCALATE
    assert item.reason == "human_approval_required"


def test_risk_sensitive_clause_can_approve_after_explicit_human_approval():
    result = verify_model_response(
        "[RISK_SENSITIVE] Publish externally.",
        evidence_by_atom={"atom-0001": [record("policy-check")]},
        authority=TypeAuthority.EXECUTOR,
        policy=POLICY,
        evaluation_time=T0,
        human_approvals={"atom-0001": True},
    )

    assert result.results[0].verdict is Verdict.APPROVE


def test_raw_to_verifier_pipeline_is_deterministic_for_same_inputs():
    kwargs = dict(
        raw=(
            "[OBSERVATION] Record exists. "
            "[INFERENCE] It probably explains the effect."
        ),
        evidence_by_atom={
            "atom-0001": [record("source-a")],
            "atom-0002": [record("source-b")],
        },
        authority=TypeAuthority.TRUSTED_POLICY,
        policy=POLICY,
        evaluation_time=T0,
    )

    first = verify_model_response(**kwargs)
    second = verify_model_response(**kwargs)

    assert first == second
