from datetime import datetime, timezone

import pytest

from bodulskihal_core import (
    Claim,
    ClaimType,
    Directness,
    Evidence,
    Policy,
    SourceRole,
    Verdict,
    canonical_receipt_sha256,
    verify_claim,
)
from bodulskihal_core.ingestion import TypeAuthority, verify_model_response


T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
POLICY = Policy(version="2.0", max_age_seconds=300)


def test_same_source_can_have_multiple_distinct_evidence_items():
    result = verify_claim(
        Claim("c1", "Two records support the claim", ClaimType.OBSERVATION),
        [
            Evidence(
                source_id="provider",
                evidence_id="e-1",
                supports=True,
                observed_at=T0,
                directness=Directness.DIRECT,
            ),
            Evidence(
                source_id="provider",
                evidence_id="e-2",
                supports=True,
                observed_at=T0,
                directness=Directness.DIRECT,
            ),
        ],
        policy=POLICY,
        evaluation_time=T0,
    )

    assert result.verdict is Verdict.APPROVE


def test_duplicate_evidence_id_fails_closed_even_across_sources():
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        verify_claim(
            Claim("c1", "Record exists", ClaimType.OBSERVATION),
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
                evidence_id="self-report",
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

    assert result.verdict is Verdict.BLOCK
    assert result.reason == "missing_independent_post_action_evidence"
    assert result.receipt["gates"]["independent_post_action_verified"] is False


def test_external_final_state_can_prove_action_completion():
    result = verify_claim(
        Claim("c1", "External action completed", ClaimType.ACTION_STATE),
        [
            Evidence(
                source_id="provider",
                evidence_id="final-state",
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


def test_receipt_records_provenance_and_canonical_hash():
    result = verify_claim(
        Claim("c1", "Publication record exists", ClaimType.OBSERVATION),
        [
            Evidence(
                source_id="research-provider",
                evidence_id="publication-123",
                source_role=SourceRole.EXTERNAL,
                source_ref="provider:publication:123",
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
    assert item["evidence_id"] == "publication-123"
    assert item["source_role"] == "external"
    assert item["source_ref"] == "provider:publication:123"
    assert item["content_sha256"] == "a" * 64

    digest = result.receipt["receipt_sha256"]
    assert len(digest) == 64
    assert digest == canonical_receipt_sha256(result.receipt)


def test_receipt_hash_is_independent_of_evidence_input_order():
    claim = Claim("c1", "Record exists", ClaimType.OBSERVATION)
    a = Evidence(
        source_id="same-provider",
        evidence_id="a",
        supports=True,
        observed_at=T0,
        directness=Directness.DIRECT,
    )
    b = Evidence(
        source_id="same-provider",
        evidence_id="b",
        supports=True,
        observed_at=T0,
        directness=Directness.DIRECT,
    )

    first = verify_claim(claim, [a, b], policy=POLICY, evaluation_time=T0)
    second = verify_claim(claim, [b, a], policy=POLICY, evaluation_time=T0)

    assert first.receipt == second.receipt


def test_provenance_change_changes_receipt_hash():
    common = dict(
        source_id="provider",
        evidence_id="e-1",
        supports=True,
        observed_at=T0,
        directness=Directness.DIRECT,
    )
    first = verify_claim(
        Claim("c1", "Record exists", ClaimType.OBSERVATION),
        [Evidence(source_ref="provider:1", **common)],
        policy=POLICY,
        evaluation_time=T0,
    )
    second = verify_claim(
        Claim("c1", "Record exists", ClaimType.OBSERVATION),
        [Evidence(source_ref="provider:2", **common)],
        policy=POLICY,
        evaluation_time=T0,
    )

    assert first.receipt["receipt_sha256"] != second.receipt["receipt_sha256"]


def test_raw_pipeline_preserves_provenance_and_blocks_executor_action_self_report():
    result = verify_model_response(
        "[ACTION_STATE] Export completed.",
        evidence_by_atom={
            "atom-0001": [
                {
                    "source_id": "executor",
                    "evidence_id": "executor-claim",
                    "source_role": "executor",
                    "source_ref": "agent:run:42",
                    "content_sha256": "b" * 64,
                    "supports": True,
                    "observed_at": T0.isoformat(),
                    "directness": "direct",
                    "post_action": True,
                }
            ]
        },
        authority=TypeAuthority.EXECUTOR,
        policy=POLICY,
        evaluation_time=T0,
    )

    item = result.results[0]
    assert item.verdict is Verdict.BLOCK
    assert item.reason == "missing_independent_post_action_evidence"
    assert item.receipt["evidence"][0]["source_ref"] == "agent:run:42"
