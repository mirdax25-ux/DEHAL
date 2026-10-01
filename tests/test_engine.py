from datetime import datetime, timedelta, timezone

import pytest

from bodulskihal_core import (
    Claim,
    ClaimType,
    Classification,
    Directness,
    Evidence,
    Policy,
    RiskLevel,
    Verdict,
    verify_claim,
    verify_compound,
)

T0 = datetime(2026, 9, 30, 19, 0, tzinfo=timezone.utc)
POLICY = Policy(version="1.0", max_age_seconds=300)


def ev(source_id: str, *, supports: bool = True, age_seconds: int = 0,
       directness: Directness = Directness.DIRECT,
       post_action: bool = False, eligible: bool = True) -> Evidence:
    return Evidence(
        source_id=source_id,
        supports=supports,
        observed_at=T0 - timedelta(seconds=age_seconds),
        directness=directness,
        post_action=post_action,
        eligible=eligible,
    )


def test_missing_evidence_is_unknown_and_blocked():
    result = verify_claim(
        Claim("c1", "Deployment completed", ClaimType.OBSERVATION),
        [],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.UNKNOWN
    assert result.verdict is Verdict.BLOCK


def test_direct_fresh_support_can_be_fact_and_approve():
    result = verify_claim(
        Claim("c1", "File exists", ClaimType.OBSERVATION),
        [ev("filesystem")],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.FACT
    assert result.verdict is Verdict.APPROVE


def test_contradicting_eligible_evidence_yields_conflict():
    result = verify_claim(
        Claim("c1", "Service is healthy", ClaimType.OBSERVATION),
        [ev("health-a"), ev("health-b", supports=False)],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.CONFLICT
    assert result.verdict is Verdict.BLOCK


def test_stale_evidence_cannot_make_fact():
    result = verify_claim(
        Claim("c1", "Deployment completed", ClaimType.OBSERVATION),
        [ev("old", age_seconds=301)],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.UNKNOWN
    assert result.verdict is Verdict.BLOCK


def test_indirect_support_is_inference_not_fact():
    result = verify_claim(
        Claim("c1", "System state is X", ClaimType.OBSERVATION),
        [ev("log-summary", directness=Directness.INDIRECT)],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.INFERENCE
    assert result.verdict is Verdict.BLOCK


def test_inference_claim_never_approves_as_fact():
    result = verify_claim(
        Claim("c1", "Likely root cause", ClaimType.INFERENCE),
        [ev("trace")],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.INFERENCE
    assert result.verdict is Verdict.BLOCK


def test_estimate_claim_never_approves_as_fact():
    result = verify_claim(
        Claim("c1", "Estimated work hours", ClaimType.ESTIMATE),
        [ev("model-input")],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.ESTIMATE
    assert result.verdict is Verdict.BLOCK


def test_action_completion_requires_post_action_evidence():
    result = verify_claim(
        Claim("c1", "Email sent", ClaimType.ACTION_STATE),
        [ev("send-request")],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.verdict is Verdict.BLOCK
    assert "post_action" in result.reason


def test_action_completion_approves_with_fresh_direct_post_action_evidence():
    result = verify_claim(
        Claim("c1", "Email sent", ClaimType.ACTION_STATE),
        [ev("provider-final-state", post_action=True)],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.FACT
    assert result.verdict is Verdict.APPROVE


def test_high_risk_requires_human_approval():
    result = verify_claim(
        Claim("c1", "High-risk action ready", ClaimType.OBSERVATION, risk=RiskLevel.HIGH),
        [ev("policy-check")],
        policy=POLICY,
        evaluation_time=T0,
        human_approved=False,
    )
    assert result.classification is Classification.FACT
    assert result.verdict is Verdict.ESCALATE


def test_high_risk_can_approve_after_human_approval():
    result = verify_claim(
        Claim("c1", "High-risk action ready", ClaimType.OBSERVATION, risk=RiskLevel.HIGH),
        [ev("policy-check")],
        policy=POLICY,
        evaluation_time=T0,
        human_approved=True,
    )
    assert result.verdict is Verdict.APPROVE


def test_compound_claim_requires_every_consequential_clause_to_pass():
    compound = verify_compound(
        [
            Claim("c1", "Deployment completed", ClaimType.ACTION_STATE),
            Claim("c2", "Tests passed", ClaimType.OBSERVATION),
        ],
        {
            "c1": [ev("deployment-state", post_action=True)],
            "c2": [],
        },
        policy=POLICY,
        evaluation_time=T0,
    )
    assert compound.verdict is Verdict.BLOCK
    assert compound.results[0].verdict is Verdict.APPROVE
    assert compound.results[1].verdict is Verdict.BLOCK


def test_nonconsequential_clause_does_not_block_compound_approval():
    compound = verify_compound(
        [
            Claim("c1", "Deployment completed", ClaimType.ACTION_STATE),
            Claim("c2", "Nice-to-have context", ClaimType.OBSERVATION, consequential=False),
        ],
        {
            "c1": [ev("deployment-state", post_action=True)],
            "c2": [],
        },
        policy=POLICY,
        evaluation_time=T0,
    )
    assert compound.verdict is Verdict.APPROVE


def test_receipt_is_deterministic_for_same_inputs_policy_and_evaluation_time():
    claim = Claim("c1", "File exists", ClaimType.OBSERVATION)
    evidence = [ev("b"), ev("a")]
    r1 = verify_claim(claim, evidence, policy=POLICY, evaluation_time=T0)
    r2 = verify_claim(claim, list(reversed(evidence)), policy=POLICY, evaluation_time=T0)
    assert r1.receipt == r2.receipt


def test_freshness_can_change_with_evaluation_time_and_is_part_of_deterministic_input():
    claim = Claim("c1", "File exists", ClaimType.OBSERVATION)
    evidence = [ev("filesystem", age_seconds=299)]
    now = verify_claim(claim, evidence, policy=POLICY, evaluation_time=T0)
    later = verify_claim(claim, evidence, policy=POLICY, evaluation_time=T0 + timedelta(seconds=2))
    assert now.classification is Classification.FACT
    assert later.classification is Classification.UNKNOWN
    assert now.receipt != later.receipt


def test_ineligible_evidence_is_ignored():
    result = verify_claim(
        Claim("c1", "File exists", ClaimType.OBSERVATION),
        [ev("untrusted", eligible=False)],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.UNKNOWN
    assert result.verdict is Verdict.BLOCK


def test_future_dated_evidence_is_ineligible_by_default():
    future = Evidence(
        source_id="future",
        supports=True,
        observed_at=T0 + timedelta(seconds=1),
        directness=Directness.DIRECT,
    )
    result = verify_claim(
        Claim("c1", "File exists", ClaimType.OBSERVATION),
        [future],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.UNKNOWN
    assert result.verdict is Verdict.BLOCK


def test_duplicate_source_ids_are_rejected_to_preserve_provenance_identity():
    with pytest.raises(ValueError, match="duplicate source_id"):
        verify_claim(
            Claim("c1", "File exists", ClaimType.OBSERVATION),
            [ev("same"), ev("same")],
            policy=POLICY,
            evaluation_time=T0,
        )


def test_receipt_records_algorithm_and_policy_versions():
    result = verify_claim(
        Claim("c1", "File exists", ClaimType.OBSERVATION),
        [ev("filesystem")],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.receipt["algorithm_version"] == "1.0.0"
    assert result.receipt["policy_version"] == "1.0"


def test_blocked_claim_emits_failure_evolution_record():
    result = verify_claim(
        Claim("c1", "Deployment completed", ClaimType.ACTION_STATE),
        [],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.failure_record is not None
    assert result.failure_record["failure_mode"] == "insufficient_eligible_evidence"
    assert result.failure_record["record_type"] == "expected_gate"
    assert result.failure_record["regression_test_required"] is False
    assert result.failure_record["version_change_required"] is False


def test_approved_claim_has_no_failure_evolution_record():
    result = verify_claim(
        Claim("c1", "File exists", ClaimType.OBSERVATION),
        [ev("filesystem")],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.failure_record is None


def test_receipt_has_explicit_gate_summary():
    result = verify_claim(
        Claim("c1", "Email sent", ClaimType.ACTION_STATE, risk=RiskLevel.HIGH),
        [ev("provider", post_action=True)],
        policy=POLICY,
        evaluation_time=T0,
        human_approved=True,
    )
    gates = result.receipt["gates"]
    assert gates["eligible_source_count"] == 1
    assert gates["contradiction_count"] == 0
    assert gates["post_action_verified"] is True
    assert gates["human_gate"] == "approved"


def test_receipt_lists_contradicting_sources_deterministically():
    result = verify_claim(
        Claim("c1", "Service healthy", ClaimType.OBSERVATION),
        [ev("z", supports=False), ev("a", supports=True)],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.receipt["gates"]["supporting_sources"] == ["a"]
    assert result.receipt["gates"]["contradicting_sources"] == ["z"]


def test_evaluation_time_must_be_timezone_aware():
    with pytest.raises(ValueError, match="evaluation_time must be timezone-aware"):
        verify_claim(
            Claim("c1", "File exists", ClaimType.OBSERVATION),
            [ev("filesystem")],
            policy=POLICY,
            evaluation_time=datetime(2026, 9, 30, 19, 0),
        )


def test_evidence_timestamp_must_be_timezone_aware():
    naive = Evidence(
        source_id="naive",
        supports=True,
        observed_at=datetime(2026, 9, 30, 19, 0),
        directness=Directness.DIRECT,
    )
    with pytest.raises(ValueError, match="observed_at must be timezone-aware"):
        verify_claim(
            Claim("c1", "File exists", ClaimType.OBSERVATION),
            [naive],
            policy=POLICY,
            evaluation_time=T0,
        )


def test_negative_max_age_is_rejected():
    with pytest.raises(ValueError, match="max_age_seconds must be non-negative"):
        verify_claim(
            Claim("c1", "File exists", ClaimType.OBSERVATION),
            [ev("filesystem")],
            policy=Policy(version="bad", max_age_seconds=-1),
            evaluation_time=T0,
        )


def test_compound_rejects_duplicate_claim_ids():
    with pytest.raises(ValueError, match="duplicate claim_id"):
        verify_compound(
            [
                Claim("c1", "A", ClaimType.OBSERVATION),
                Claim("c1", "B", ClaimType.OBSERVATION),
            ],
            {"c1": [ev("source")]},
            policy=POLICY,
            evaluation_time=T0,
        )


def test_empty_compound_does_not_vacuously_approve():
    with pytest.raises(ValueError, match="at least one claim"):
        verify_compound([], {}, policy=POLICY, evaluation_time=T0)
