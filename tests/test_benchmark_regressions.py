from datetime import datetime, timezone

import pytest

from bodulskihal_core import (
    AnswerabilityStatus,
    AuthorityScope,
    Claim,
    ClaimType,
    Classification,
    Directness,
    Evidence,
    EvidenceOrigin,
    Policy,
    RiskLevel,
    SourceRole,
    Verdict,
    verify_claim,
)
from bodulskihal_core.conversation_gate import (
    ConstraintRecord,
    ConversationContract,
    evaluate_conversation_contract,
)
from bodulskihal_core.guard_loop import (
    Realism,
    SelfCheck,
    UnknownRecord,
    UnknownSeverity,
    run_guard_loop,
)


T0 = datetime(2026, 10, 3, 21, 30, tzinfo=timezone.utc)
POLICY = Policy(version="benchmark-v1", max_age_seconds=300)


def ev(
    evidence_id: str,
    *,
    supports: bool = True,
    source_id: str | None = None,
    origin: EvidenceOrigin = EvidenceOrigin.EXTERNAL_SOURCE,
    authority_scope: AuthorityScope = AuthorityScope.EXTERNAL_FACT,
) -> Evidence:
    return Evidence(
        source_id=source_id or evidence_id,
        evidence_id=evidence_id,
        supports=supports,
        observed_at=T0,
        directness=Directness.DIRECT,
        source_role=SourceRole.EXTERNAL,
        origin=origin,
        authority_scope=authority_scope,
    )


def test_direct_counterevidence_is_refuted_not_unknown_or_conflict():
    result = verify_claim(
        Claim("c1", "Count is 30", ClaimType.OBSERVATION),
        [ev("counter", supports=False)],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.REFUTED
    assert result.verdict is Verdict.BLOCK
    assert result.reason == "claim_refuted_by_eligible_evidence"


def test_mixed_support_and_counterevidence_remains_conflict():
    result = verify_claim(
        Claim("c1", "Count is 30", ClaimType.OBSERVATION),
        [ev("support"), ev("counter", supports=False)],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.CONFLICT
    assert result.verdict is Verdict.BLOCK


def test_user_assertion_cannot_certify_external_fact():
    result = verify_claim(
        Claim(
            "c1",
            "Conversation has 30 questions",
            ClaimType.OBSERVATION,
            authority_scope=AuthorityScope.EXTERNAL_FACT,
        ),
        [
            ev(
                "user-guess",
                origin=EvidenceOrigin.USER_ASSERTION,
                authority_scope=AuthorityScope.EXTERNAL_FACT,
            )
        ],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.UNKNOWN
    assert result.verdict is Verdict.BLOCK
    assert result.reason == "insufficient_authorized_evidence"
    assert result.receipt["gates"]["authority_rejected_evidence_ids"] == ["user-guess"]


def test_user_preference_is_authoritative_inside_preference_scope():
    result = verify_claim(
        Claim(
            "c1",
            "User wants Croatian Latin script",
            ClaimType.OBSERVATION,
            authority_scope=AuthorityScope.USER_PREFERENCE,
        ),
        [
            ev(
                "user-pref",
                origin=EvidenceOrigin.USER_PREFERENCE,
                authority_scope=AuthorityScope.USER_PREFERENCE,
            )
        ],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.FACT
    assert result.verdict is Verdict.APPROVE


def test_same_source_multiple_observations_do_not_satisfy_independent_quorum():
    result = verify_claim(
        Claim(
            "c1",
            "Medium-risk fact",
            ClaimType.OBSERVATION,
            risk=RiskLevel.MEDIUM,
        ),
        [
            ev("obs-1", source_id="same-source"),
            ev("obs-2", source_id="same-source"),
        ],
        policy=Policy(
            version="benchmark-v1",
            max_age_seconds=300,
            medium_risk_min_independent_sources=2,
        ),
        evaluation_time=T0,
    )
    assert result.classification is Classification.FACT
    assert result.verdict is Verdict.ESCALATE
    assert result.receipt["gates"]["independent_supporting_source_count"] == 1


@pytest.mark.parametrize(
    "status,expected_reason",
    [
        (AnswerabilityStatus.UNDERSPECIFIED, "answerability_underspecified"),
        (AnswerabilityStatus.FALSE_PREMISE, "answerability_false_premise"),
        (AnswerabilityStatus.OUT_OF_SCOPE, "answerability_out_of_scope"),
    ],
)
def test_non_answerable_claims_fail_closed(status, expected_reason):
    result = verify_claim(
        Claim(
            "c1",
            "Candidate answer",
            ClaimType.OBSERVATION,
            answerability=status,
        ),
        [ev("support")],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.UNKNOWN
    assert result.verdict is Verdict.BLOCK
    assert result.reason == expected_reason


def test_needs_clarification_escalates_without_fabricating_answer():
    result = verify_claim(
        Claim(
            "c1",
            "Ambiguous referent",
            ClaimType.OBSERVATION,
            answerability=AnswerabilityStatus.NEEDS_CLARIFICATION,
        ),
        [ev("support")],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.UNKNOWN
    assert result.verdict is Verdict.ESCALATE
    assert result.reason == "answerability_needs_clarification"


def test_reviewed_critical_unknown_is_not_treated_as_resolved():
    check = SelfCheck(
        realism=Realism.POSSIBLE,
        known=("bounded claim is available",),
        assumptions=(),
        unknowns=("source authenticity is not established",),
        assumptions_reviewed=True,
        unknowns_reviewed=True,
        unknown_records=(
            UnknownRecord(
                description="source authenticity is not established",
                severity=UnknownSeverity.CRITICAL,
                reviewed=True,
                resolved=False,
                blocking=True,
            ),
        ),
    )
    result = run_guard_loop(
        claim=Claim("c1", "External state is true", ClaimType.OBSERVATION),
        evidence=[ev("support")],
        self_check=check,
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.UNKNOWN
    assert result.verdict is Verdict.ESCALATE
    assert result.reason == "blocking_unknown_unresolved"


def test_resolved_critical_unknown_can_continue_to_verification():
    check = SelfCheck(
        realism=Realism.POSSIBLE,
        known=("bounded claim is available",),
        assumptions=(),
        unknowns=("source authenticity was checked",),
        assumptions_reviewed=True,
        unknowns_reviewed=True,
        unknown_records=(
            UnknownRecord(
                description="source authenticity was checked",
                severity=UnknownSeverity.CRITICAL,
                reviewed=True,
                resolved=True,
                blocking=True,
                resolution_reference="receipt-123",
            ),
        ),
    )
    result = run_guard_loop(
        claim=Claim("c1", "External state is true", ClaimType.OBSERVATION),
        evidence=[ev("support")],
        self_check=check,
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.FACT
    assert result.verdict is Verdict.APPROVE


def test_conversation_contract_rejects_referent_drift():
    result = evaluate_conversation_contract(
        ConversationContract(
            goal_id="find-grants",
            referent_id="three-bodulskihal-grants",
            candidate_goal_id="find-grants",
            candidate_referent_id="PRECICA",
            constraints=(),
        )
    )
    assert result.approved is False
    assert result.reason == "referent_mismatch"


def test_conversation_contract_rejects_unsatisfied_active_constraint():
    result = evaluate_conversation_contract(
        ConversationContract(
            goal_id="answer",
            referent_id="current-question",
            candidate_goal_id="answer",
            candidate_referent_id="current-question",
            constraints=(
                ConstraintRecord(
                    constraint_id="language",
                    kind="language",
                    value="hr-Latn",
                    active=True,
                    satisfied=False,
                ),
            ),
        )
    )
    assert result.approved is False
    assert result.reason == "active_constraint_failed"


def test_conversation_contract_approves_matching_candidate():
    result = evaluate_conversation_contract(
        ConversationContract(
            goal_id="answer",
            referent_id="current-question",
            candidate_goal_id="answer",
            candidate_referent_id="current-question",
            constraints=(
                ConstraintRecord(
                    constraint_id="language",
                    kind="language",
                    value="hr-Latn",
                    active=True,
                    satisfied=True,
                ),
            ),
        )
    )
    assert result.approved is True
    assert result.reason == "conversation_contract_satisfied"


def test_required_runtime_provenance_blocks_unidentified_build(monkeypatch):
    for name in (
        "BODULSKIHAL_SOURCE_COMMIT",
        "BODULSKIHAL_SOURCE_REF",
        "BODULSKIHAL_BUILD_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    result = verify_claim(
        Claim("c1", "Verified value", ClaimType.OBSERVATION),
        [ev("support")],
        policy=Policy(
            version="benchmark-v1",
            max_age_seconds=300,
            require_runtime_provenance=True,
        ),
        evaluation_time=T0,
    )
    assert result.classification is Classification.FACT
    assert result.verdict is Verdict.BLOCK
    assert result.reason == "runtime_provenance_unverified"
    assert result.receipt["runtime_provenance"]["verified"] is False


def test_runtime_receipt_binds_commit_ref_and_build_id(monkeypatch):
    commit = "a" * 40
    monkeypatch.setenv("BODULSKIHAL_SOURCE_COMMIT", commit)
    monkeypatch.setenv("BODULSKIHAL_SOURCE_REF", "integration/bodulskihal-next-20261003")
    monkeypatch.setenv("BODULSKIHAL_BUILD_ID", "ci-123")

    result = verify_claim(
        Claim("c1", "Verified value", ClaimType.OBSERVATION),
        [ev("support")],
        policy=Policy(
            version="benchmark-v1",
            max_age_seconds=300,
            require_runtime_provenance=True,
        ),
        evaluation_time=T0,
    )
    assert result.verdict is Verdict.APPROVE
    provenance = result.receipt["runtime_provenance"]
    assert provenance == {
        "source_commit": commit,
        "source_ref": "integration/bodulskihal-next-20261003",
        "build_id": "ci-123",
        "verified": True,
    }


def test_memory_cannot_certify_external_fact():
    result = verify_claim(
        Claim(
            "c1",
            "Current external state is true",
            ClaimType.OBSERVATION,
            authority_scope=AuthorityScope.EXTERNAL_FACT,
        ),
        [
            ev(
                "memory-1",
                origin=EvidenceOrigin.MEMORY,
                authority_scope=AuthorityScope.EXTERNAL_FACT,
            )
        ],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.classification is Classification.UNKNOWN
    assert result.verdict is Verdict.BLOCK
    assert result.reason == "insufficient_authorized_evidence"
