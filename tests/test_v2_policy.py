from datetime import datetime, timezone

import pytest

from bodulskihal_core import (
    Claim,
    ClaimType,
    Directness,
    Evidence,
    Policy,
    RiskLevel,
    SourceRole,
    Verdict,
    make_failure_evolution_record,
    verify_claim,
)


T0 = datetime(2026, 10, 1, 7, 30, tzinfo=timezone.utc)
POLICY = Policy(version="2.0", max_age_seconds=300)


def evidence(evidence_id: str, source_id: str) -> Evidence:
    return Evidence(
        source_id=source_id,
        evidence_id=evidence_id,
        source_role=SourceRole.EXTERNAL,
        supports=True,
        observed_at=T0,
        directness=Directness.DIRECT,
    )


def test_medium_risk_requires_two_independent_supporting_sources_by_default():
    result = verify_claim(
        Claim(
            "c1",
            "Medium-risk research decision is supported",
            ClaimType.OBSERVATION,
            risk=RiskLevel.MEDIUM,
        ),
        [evidence("e1", "source-a")],
        policy=POLICY,
        evaluation_time=T0,
    )

    assert result.verdict is Verdict.ESCALATE
    assert result.reason == "additional_independent_evidence_required"
    assert result.receipt["gates"]["independent_supporting_source_count"] == 1
    assert result.receipt["gates"]["medium_risk_required_sources"] == 2


def test_medium_risk_approves_with_two_independent_supporting_sources():
    result = verify_claim(
        Claim(
            "c1",
            "Medium-risk research decision is supported",
            ClaimType.OBSERVATION,
            risk=RiskLevel.MEDIUM,
        ),
        [
            evidence("e1", "source-a"),
            evidence("e2", "source-b"),
        ],
        policy=POLICY,
        evaluation_time=T0,
    )

    assert result.verdict is Verdict.APPROVE
    assert result.receipt["gates"]["independent_supporting_source_count"] == 2


def test_two_evidence_items_from_same_source_do_not_satisfy_medium_risk():
    result = verify_claim(
        Claim(
            "c1",
            "Medium-risk research decision is supported",
            ClaimType.OBSERVATION,
            risk=RiskLevel.MEDIUM,
        ),
        [
            evidence("e1", "same-source"),
            evidence("e2", "same-source"),
        ],
        policy=POLICY,
        evaluation_time=T0,
    )

    assert result.verdict is Verdict.ESCALATE
    assert result.receipt["gates"]["independent_supporting_source_count"] == 1


def test_medium_risk_policy_threshold_must_be_positive():
    with pytest.raises(ValueError, match="medium_risk_min_independent_sources"):
        verify_claim(
            Claim(
                "c1",
                "Decision",
                ClaimType.OBSERVATION,
                risk=RiskLevel.MEDIUM,
            ),
            [evidence("e1", "source-a")],
            policy=Policy(
                version="bad",
                max_age_seconds=300,
                medium_risk_min_independent_sources=0,
            ),
            evaluation_time=T0,
        )


def test_novel_failure_evolution_record_requires_explicit_guardrail_fields():
    record = make_failure_evolution_record(
        failure_mode="unexpected parser divergence",
        root_cause="normalization mismatch",
        guardrail="canonicalize before comparison",
        regression_test="test_parser_divergence",
    )

    assert record["record_type"] == "failure_evolution"
    assert record["failure_mode"] == "unexpected parser divergence"
    assert record["root_cause"] == "normalization mismatch"
    assert record["guardrail"] == "canonicalize before comparison"
    assert record["regression_test"] == "test_parser_divergence"
    assert record["regression_test_required"] is True
    assert record["version_change_required"] is True


def test_novel_failure_evolution_record_rejects_empty_fields():
    with pytest.raises(ValueError):
        make_failure_evolution_record(
            failure_mode="",
            root_cause="x",
            guardrail="y",
            regression_test="z",
        )
