from datetime import datetime, timezone

import pytest

from b_1_2_core import (
    Claim,
    ClaimType,
    Classification,
    Directness,
    Evidence,
    Policy,
    RiskLevel,
    Verdict,
)
from b_1_2_core.guard_loop import (
    GuardStage,
    Realism,
    SelfCheck,
    run_guard_loop,
)


T0 = datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)
POLICY = Policy(version="2.0", max_age_seconds=300)


def evidence(
    source_id: str = "source",
    *,
    supports: bool = True,
    post_action: bool = False,
) -> Evidence:
    return Evidence(
        source_id=source_id,
        supports=supports,
        observed_at=T0,
        directness=Directness.DIRECT,
        post_action=post_action,
    )


def self_check(
    *,
    realism: Realism = Realism.POSSIBLE,
    assumptions_reviewed: bool = True,
    unknowns_reviewed: bool = True,
    known: tuple[str, ...] = ("claim text is available",),
    assumptions: tuple[str, ...] = (),
    unknowns: tuple[str, ...] = (),
) -> SelfCheck:
    return SelfCheck(
        realism=realism,
        known=known,
        assumptions=assumptions,
        unknowns=unknowns,
        assumptions_reviewed=assumptions_reviewed,
        unknowns_reviewed=unknowns_reviewed,
    )


def test_self_check_is_mandatory():
    with pytest.raises(TypeError):
        run_guard_loop(
            claim=Claim("c1", "File exists", ClaimType.OBSERVATION),
            evidence=[evidence()],
            policy=POLICY,
            evaluation_time=T0,
        )


def test_impossible_self_check_blocks_before_verifier():
    result = run_guard_loop(
        claim=Claim("c1", "Impossible state", ClaimType.OBSERVATION),
        evidence=[evidence()],
        self_check=self_check(realism=Realism.IMPOSSIBLE),
        policy=POLICY,
        evaluation_time=T0,
    )

    assert result.stage is GuardStage.SELF_CHECK
    assert result.verdict is Verdict.BLOCK
    assert result.classification is Classification.UNKNOWN
    assert result.reason == "self_check_impossible"
    assert result.verification is None


def test_uncertain_self_check_escalates_instead_of_claiming_fact():
    result = run_guard_loop(
        claim=Claim("c1", "Uncertain state", ClaimType.OBSERVATION),
        evidence=[evidence()],
        self_check=self_check(
            realism=Realism.UNCERTAIN,
            unknowns=("external state not checked",),
        ),
        policy=POLICY,
        evaluation_time=T0,
    )

    assert result.stage is GuardStage.SELF_CHECK
    assert result.verdict is Verdict.ESCALATE
    assert result.classification is Classification.UNKNOWN
    assert result.reason == "self_check_uncertain"
    assert result.verification is None


def test_unreviewed_assumptions_escalate_before_verifier():
    result = run_guard_loop(
        claim=Claim("c1", "File exists", ClaimType.OBSERVATION),
        evidence=[evidence()],
        self_check=self_check(
            assumptions=("provider is reachable",),
            assumptions_reviewed=False,
        ),
        policy=POLICY,
        evaluation_time=T0,
    )

    assert result.stage is GuardStage.SELF_CHECK
    assert result.verdict is Verdict.ESCALATE
    assert result.reason == "assumptions_not_reviewed"
    assert result.verification is None


def test_unreviewed_unknowns_escalate_before_verifier():
    result = run_guard_loop(
        claim=Claim("c1", "File exists", ClaimType.OBSERVATION),
        evidence=[evidence()],
        self_check=self_check(
            unknowns=("final state not observed",),
            unknowns_reviewed=False,
        ),
        policy=POLICY,
        evaluation_time=T0,
    )

    assert result.stage is GuardStage.SELF_CHECK
    assert result.verdict is Verdict.ESCALATE
    assert result.reason == "unknowns_not_reviewed"
    assert result.verification is None


def test_passing_self_check_delegates_missing_evidence_to_existing_verifier():
    result = run_guard_loop(
        claim=Claim("c1", "File exists", ClaimType.OBSERVATION),
        evidence=[],
        self_check=self_check(),
        policy=POLICY,
        evaluation_time=T0,
    )

    assert result.stage is GuardStage.VERIFICATION
    assert result.verification is not None
    assert result.verification.classification is Classification.UNKNOWN
    assert result.verdict is Verdict.BLOCK
    assert result.reason == "insufficient_eligible_evidence"


def test_passing_self_check_and_direct_evidence_can_approve_fact():
    result = run_guard_loop(
        claim=Claim("c1", "File exists", ClaimType.OBSERVATION),
        evidence=[evidence("filesystem")],
        self_check=self_check(),
        policy=POLICY,
        evaluation_time=T0,
    )

    assert result.stage is GuardStage.VERIFICATION
    assert result.classification is Classification.FACT
    assert result.verdict is Verdict.APPROVE
    assert result.reason == "fact_with_required_gates"


def test_action_command_is_not_completion_without_post_action_evidence():
    result = run_guard_loop(
        claim=Claim("c1", "Email sent", ClaimType.ACTION_STATE),
        evidence=[evidence("send-request", post_action=False)],
        self_check=self_check(),
        policy=POLICY,
        evaluation_time=T0,
    )

    assert result.stage is GuardStage.VERIFICATION
    assert result.classification is Classification.FACT
    assert result.verdict is Verdict.BLOCK
    assert result.reason == "missing_post_action_final_state_evidence"


def test_action_completion_can_approve_with_final_state_evidence():
    result = run_guard_loop(
        claim=Claim("c1", "Email sent", ClaimType.ACTION_STATE),
        evidence=[evidence("provider-final-state", post_action=True)],
        self_check=self_check(),
        policy=POLICY,
        evaluation_time=T0,
    )

    assert result.verdict is Verdict.APPROVE
    assert result.reason == "fact_with_required_gates"


def test_high_risk_fact_escalates_without_human_approval():
    result = run_guard_loop(
        claim=Claim(
            "c1",
            "High-risk action ready",
            ClaimType.OBSERVATION,
            risk=RiskLevel.HIGH,
        ),
        evidence=[evidence("policy-check")],
        self_check=self_check(),
        policy=POLICY,
        evaluation_time=T0,
        human_approved=False,
    )

    assert result.classification is Classification.FACT
    assert result.verdict is Verdict.ESCALATE
    assert result.reason == "human_approval_required"


def test_guard_receipt_records_self_check_and_verifier_result():
    result = run_guard_loop(
        claim=Claim("c1", "File exists", ClaimType.OBSERVATION),
        evidence=[evidence("filesystem")],
        self_check=self_check(
            known=("filesystem source is available",),
            assumptions=("path is canonical",),
            unknowns=("remote mirror freshness",),
        ),
        policy=POLICY,
        evaluation_time=T0,
    )

    receipt = result.receipt
    assert receipt["self_check"]["realism"] == "possible"
    assert receipt["self_check"]["known"] == ["filesystem source is available"]
    assert receipt["self_check"]["assumptions"] == ["path is canonical"]
    assert receipt["self_check"]["unknowns"] == ["remote mirror freshness"]
    assert receipt["self_check"]["assumptions_reviewed"] is True
    assert receipt["self_check"]["unknowns_reviewed"] is True
    assert receipt["verification"]["verdict"] == "APPROVE"
    assert receipt["verification"]["classification"] == "FACT"


def test_self_check_receipt_is_deterministic_for_same_inputs():
    kwargs = dict(
        claim=Claim("c1", "File exists", ClaimType.OBSERVATION),
        evidence=[evidence("filesystem")],
        self_check=self_check(),
        policy=POLICY,
        evaluation_time=T0,
    )

    first = run_guard_loop(**kwargs)
    second = run_guard_loop(**kwargs)

    assert first.receipt == second.receipt
