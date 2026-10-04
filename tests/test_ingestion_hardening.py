from datetime import datetime, timezone

import pytest

from bodulskihal_core import (
    Claim,
    ClaimType,
    Policy,
    RiskLevel,
    Verdict,
    verify_claim,
)
from bodulskihal_core.ingestion import (
    TypeAuthority,
    collect_normalize_evidence,
    type_clause,
    verify_model_response,
)


T0 = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)
POLICY = Policy(version="ingestion-hardening", max_age_seconds=300)


def record(source_id, *, independence_group=None):
    return {
        "source_id": source_id,
        "supports": True,
        "observed_at": T0.isoformat(),
        "directness": "direct",
        "source_ref": f"https://example.test/{source_id}",
        "independence_group": independence_group,
    }


@pytest.mark.parametrize("authority", ["executor", "trusted_policy", None, 42, True])
def test_clause_typing_rejects_non_enum_authority(authority):
    with pytest.raises(TypeError, match="authority must be TypeAuthority"):
        type_clause("[OBSERVATION] Value equals one.", authority=authority)


@pytest.mark.parametrize("authority", ["executor", "trusted_policy", None, 42, True])
def test_raw_response_cannot_bypass_executor_gate_with_non_enum_authority(authority):
    evidence = record("source-a")
    evidence.pop("independence_group")
    with pytest.raises(TypeError, match="authority must be TypeAuthority"):
        verify_model_response(
            "[OBSERVATION] Value equals one.",
            evidence_by_atom={"atom-0001": [evidence]},
            authority=authority,
            policy=POLICY,
            evaluation_time=T0,
        )


@pytest.mark.parametrize("authority", [TypeAuthority.TRUSTED_POLICY, TypeAuthority.HUMAN])
def test_trusted_enum_authority_preserves_observation_flow(authority):
    result = verify_model_response(
        "[OBSERVATION] Value equals one.",
        evidence_by_atom={"atom-0001": [record("source-a")]},
        authority=authority,
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.verdict is Verdict.APPROVE


def test_ingestion_preserves_independence_group_for_quorum_gate():
    normalized = collect_normalize_evidence(
        {
            "atom-0001": [
                record("source-a", independence_group="publisher-one"),
                record("source-b", independence_group="publisher-one"),
            ]
        },
        known_atom_ids={"atom-0001"},
    )
    assert [item.independence_group for item in normalized["atom-0001"]] == [
        "publisher-one",
        "publisher-one",
    ]
    result = verify_claim(
        Claim("atom-0001", "Bounded observation", ClaimType.OBSERVATION, risk=RiskLevel.MEDIUM),
        normalized["atom-0001"],
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.verdict is Verdict.ESCALATE
    assert result.receipt["gates"]["independent_supporting_group_count"] == 1


def test_raw_response_receipt_preserves_independence_group():
    result = verify_model_response(
        "[OBSERVATION] Value equals one.",
        evidence_by_atom={
            "atom-0001": [record("source-a", independence_group="publisher-one")]
        },
        authority=TypeAuthority.TRUSTED_POLICY,
        policy=POLICY,
        evaluation_time=T0,
    )
    assert result.verdict is Verdict.APPROVE
    assert result.results[0].receipt["evidence"][0]["independence_group"] == "publisher-one"


@pytest.mark.parametrize("invalid_group", ["", " ", False, 1, [], {}])
def test_ingestion_rejects_invalid_independence_group(invalid_group):
    with pytest.raises(TypeError, match="independence_group must be non-empty string"):
        collect_normalize_evidence(
            {"atom-0001": [record("source-a", independence_group=invalid_group)]},
            known_atom_ids={"atom-0001"},
        )
