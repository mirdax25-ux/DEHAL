from datetime import datetime, timezone

from bodulskihal_core import (
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

T0 = datetime(2026, 10, 3, 21, 30, tzinfo=timezone.utc)


def test_explicit_independence_group_collapses_different_refs():
    base = dict(
        supports=True,
        observed_at=T0,
        directness=Directness.DIRECT,
        source_role=SourceRole.EXTERNAL,
        origin=EvidenceOrigin.EXTERNAL_SOURCE,
        authority_scope=AuthorityScope.EXTERNAL_FACT,
        independence_group="publisher-one",
    )
    result = verify_claim(
        Claim("c-group", "Medium-risk fact", ClaimType.OBSERVATION, risk=RiskLevel.MEDIUM),
        [
            Evidence(source_id="source-a", evidence_id="group-e1", source_ref="https://publisher.example/a", **base),
            Evidence(source_id="source-b", evidence_id="group-e2", source_ref="https://publisher.example/b", **base),
        ],
        policy=Policy(version="benchmark-v1", max_age_seconds=300, medium_risk_min_independent_sources=2),
        evaluation_time=T0,
    )
    assert result.classification is Classification.FACT
    assert result.verdict is Verdict.ESCALATE
    assert result.receipt["gates"]["independent_supporting_group_count"] == 1


def test_distinct_independence_groups_can_satisfy_medium_risk_quorum():
    common = dict(
        supports=True,
        observed_at=T0,
        directness=Directness.DIRECT,
        source_role=SourceRole.EXTERNAL,
        origin=EvidenceOrigin.EXTERNAL_SOURCE,
        authority_scope=AuthorityScope.EXTERNAL_FACT,
    )
    result = verify_claim(
        Claim("c-groups-ok", "Medium-risk fact", ClaimType.OBSERVATION, risk=RiskLevel.MEDIUM),
        [
            Evidence(source_id="source-a", evidence_id="ok-e1", source_ref="https://a.example/item", independence_group="origin-a", **common),
            Evidence(source_id="source-b", evidence_id="ok-e2", source_ref="https://b.example/item", independence_group="origin-b", **common),
        ],
        policy=Policy(version="benchmark-v1", max_age_seconds=300, medium_risk_min_independent_sources=2),
        evaluation_time=T0,
    )
    assert result.classification is Classification.FACT
    assert result.verdict is Verdict.APPROVE
    assert result.receipt["gates"]["independent_supporting_group_count"] == 2


def test_json_adapter_preserves_independence_group():
    from bodulskihal_core import verify_payload

    payload = {
        "claim": {
            "id": "adapter-group",
            "text": "Medium-risk fact",
            "type": "observation",
            "risk": "medium",
            "authority_scope": "external_fact",
            "answerability": "answerable",
        },
        "evidence": [
            {
                "source_id": "alias-a",
                "evidence_id": "adapter-e1",
                "supports": True,
                "observed_at": T0.isoformat(),
                "directness": "direct",
                "source_role": "external",
                "source_ref": "https://a.example/one",
                "independence_group": "publisher-one",
                "origin": "external_source",
                "authority_scope": "external_fact",
            },
            {
                "source_id": "alias-b",
                "evidence_id": "adapter-e2",
                "supports": True,
                "observed_at": T0.isoformat(),
                "directness": "direct",
                "source_role": "external",
                "source_ref": "https://a.example/two",
                "independence_group": "publisher-one",
                "origin": "external_source",
                "authority_scope": "external_fact",
            },
        ],
        "policy": {
            "version": "adapter-independence",
            "max_age_seconds": 300,
            "medium_risk_min_independent_sources": 2,
        },
        "evaluation_time": T0.isoformat(),
        "human_approved": False,
    }
    result = verify_payload(payload)
    assert result["classification"] == "FACT"
    assert result["verdict"] == "ESCALATE"
    assert result["receipt"]["gates"]["independent_supporting_group_count"] == 1


def test_same_content_hash_cannot_count_as_independent_sources():
    common = dict(
        supports=True,
        observed_at=T0,
        directness=Directness.DIRECT,
        source_role=SourceRole.EXTERNAL,
        origin=EvidenceOrigin.EXTERNAL_SOURCE,
        authority_scope=AuthorityScope.EXTERNAL_FACT,
        content_sha256="a" * 64,
    )
    result = verify_claim(
        Claim(
            "c-same-content",
            "Medium-risk fact",
            ClaimType.OBSERVATION,
            risk=RiskLevel.MEDIUM,
        ),
        [
            Evidence(
                source_id="source-a",
                evidence_id="same-content-e1",
                source_ref="https://a.example/item",
                independence_group="origin-a",
                **common,
            ),
            Evidence(
                source_id="source-b",
                evidence_id="same-content-e2",
                source_ref="https://b.example/item",
                independence_group="origin-b",
                **common,
            ),
        ],
        policy=Policy(
            version="materiality-v1",
            max_age_seconds=300,
            medium_risk_min_independent_sources=2,
        ),
        evaluation_time=T0,
    )

    assert result.verdict is Verdict.ESCALATE
    assert result.receipt["gates"]["independent_supporting_group_count"] == 1
