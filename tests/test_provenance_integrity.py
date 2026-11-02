from datetime import datetime, timezone

import pytest

from b_1_2_core import (
    Claim,
    ClaimType,
    Classification,
    Directness,
    Evidence,
    Policy,
    SourceRole,
    Verdict,
    canonical_receipt_sha256,
    verify_claim,
)


T0 = datetime(2026, 10, 1, 7, 0, tzinfo=timezone.utc)
POLICY = Policy(version="2.0", max_age_seconds=300)


def test_same_source_can_supply_multiple_distinct_evidence_items():
    result = verify_claim(
        Claim("c1", "Two observations support the claim", ClaimType.OBSERVATION),
        [
            Evidence(
                source_id="provider",
                evidence_id="obs-1",
                supports=True,
                observed_at=T0,
                directness=Directness.DIRECT,
            ),
            Evidence(
                source_id="provider",
                evidence_id="obs-2",
                supports=True,
                observed_at=T0,
                directness=Directness.DIRECT,
            ),
        ],
        policy=POLICY,
        evaluation_time=T0,
    )

    assert result.classification is Classification.FACT
    assert result.verdict is Verdict.APPROVE


def test_duplicate_evidence_id_is_rejected_even_across_different_sources():
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        verify_claim(
            Claim("c1", "File exists", ClaimType.OBSERVATION),
            [
                Evidence(
                    source_id="a",
                    evidence_id="same",
                    supports=True,
                    observed_at=T0,
                    directness=Directness.DIRECT,
                ),
                Evidence(
                    source_id="b",
                    evidence_id="same",
                    supports=True,
                    observed_at=T0,
                    directness=Directness.DIRECT,
                ),
            ],
            policy=POLICY,
            evaluation_time=T0,
        )


def test_executor_self_report_cannot_prove_action_completion():
    result = verify_claim(
        Claim("c1", "External action completed", ClaimType.ACTION_STATE),
        [
            Evidence(
                source_id="executor",
                evidence_id="executor-self-report",
                source_role=SourceRole.EXECUTOR,
                supports=True,
                observed_at=T0,
                directness=Directness.DIRECT,
                post_action=True,
            )
        ],
        policy=POLICY,
        evaluation_time=T0,
    )

    assert result.classification is Classification.FACT
    assert result.verdict is Verdict.BLOCK
    assert result.reason == "missing_independent_post_action_evidence"
    assert result.receipt["gates"]["independent_post_action_verified"] is False


def test_independent_external_post_action_evidence_can_approve_action():
    result = verify_claim(
        Claim("c1", "External action completed", ClaimType.ACTION_STATE),
        [
            Evidence(
                source_id="provider",
                evidence_id="provider-final-state",
                source_role=SourceRole.EXTERNAL,
                supports=True,
                observed_at=T0,
                directness=Directness.DIRECT,
                post_action=True,
            )
        ],
        policy=POLICY,
        evaluation_time=T0,
    )

    assert result.verdict is Verdict.APPROVE
    assert result.receipt["gates"]["independent_post_action_verified"] is True


def test_receipt_records_provenance_metadata():
    result = verify_claim(
        Claim("c1", "Record exists", ClaimType.OBSERVATION),
        [
            Evidence(
                source_id="dimensions",
                evidence_id="record-1",
                source_role=SourceRole.EXTERNAL,
                source_ref="dimensions:publication:123",
                content_sha256="a" * 64,
                supports=True,
                observed_at=T0,
                directness=Directness.DIRECT,
            )
        ],
        policy=POLICY,
        evaluation_time=T0,
    )

    item = result.receipt["evidence"][0]
    assert item["evidence_id"] == "record-1"
    assert item["source_id"] == "dimensions"
    assert item["source_role"] == "external"
    assert item["source_ref"] == "dimensions:publication:123"
    assert item["content_sha256"] == "a" * 64


def test_receipt_contains_verifiable_canonical_sha256():
    result = verify_claim(
        Claim("c1", "Record exists", ClaimType.OBSERVATION),
        [
            Evidence(
                source_id="provider",
                evidence_id="e-1",
                supports=True,
                observed_at=T0,
                directness=Directness.DIRECT,
            )
        ],
        policy=POLICY,
        evaluation_time=T0,
    )

    digest = result.receipt["receipt_sha256"]
    assert len(digest) == 64
    assert digest == canonical_receipt_sha256(result.receipt)


def test_receipt_hash_is_order_independent_for_same_evidence_set():
    claim = Claim("c1", "Record exists", ClaimType.OBSERVATION)
    a = Evidence(
        source_id="provider",
        evidence_id="a",
        supports=True,
        observed_at=T0,
        directness=Directness.DIRECT,
    )
    b = Evidence(
        source_id="provider",
        evidence_id="b",
        supports=True,
        observed_at=T0,
        directness=Directness.DIRECT,
    )

    first = verify_claim(claim, [a, b], policy=POLICY, evaluation_time=T0)
    second = verify_claim(claim, [b, a], policy=POLICY, evaluation_time=T0)

    assert first.receipt["receipt_sha256"] == second.receipt["receipt_sha256"]
    assert first.receipt == second.receipt


def test_changing_provenance_changes_receipt_hash():
    claim = Claim("c1", "Record exists", ClaimType.OBSERVATION)
    first = verify_claim(
        claim,
        [
            Evidence(
                source_id="provider",
                evidence_id="e-1",
                source_ref="provider:record:1",
                supports=True,
                observed_at=T0,
                directness=Directness.DIRECT,
            )
        ],
        policy=POLICY,
        evaluation_time=T0,
    )
    second = verify_claim(
        claim,
        [
            Evidence(
                source_id="provider",
                evidence_id="e-1",
                source_ref="provider:record:2",
                supports=True,
                observed_at=T0,
                directness=Directness.DIRECT,
            )
        ],
        policy=POLICY,
        evaluation_time=T0,
    )

    assert first.receipt["receipt_sha256"] != second.receipt["receipt_sha256"]
