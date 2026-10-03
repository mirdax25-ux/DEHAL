import pytest

from bodulskihal_core.adapter import verify_payload


T0 = "2026-10-01T08:00:00+00:00"


def action_payload(source_role: str) -> dict:
    return {
        "claim": {
            "id": "action",
            "text": "External action completed",
            "type": "action_state",
        },
        "evidence": [
            {
                "source_id": "agent-or-provider",
                "evidence_id": "final-state-1",
                "source_role": source_role,
                "source_ref": "provider:operation:123",
                "content_sha256": "b" * 64,
                "supports": True,
                "observed_at": T0,
                "directness": "direct",
                "post_action": True,
            }
        ],
        "policy": {
            "version": "2.0",
            "max_age_seconds": 300,
            "require_independent_action_evidence": True,
            "medium_risk_min_independent_sources": 2,
        },
        "evaluation_time": T0,
    }


def test_adapter_parses_provenance_fields_and_blocks_executor_self_report():
    result = verify_payload(action_payload("executor"))

    assert result["schema_version"] == 3
    assert result["verdict"] == "BLOCK"
    assert result["reason"] == "missing_independent_post_action_evidence"
    item = result["receipt"]["evidence"][0]
    assert item["evidence_id"] == "final-state-1"
    assert item["source_role"] == "executor"
    assert item["source_ref"] == "provider:operation:123"
    assert item["content_sha256"] == "b" * 64


def test_adapter_allows_independent_external_final_state():
    result = verify_payload(action_payload("external"))

    assert result["verdict"] == "APPROVE"
    assert result["receipt"]["gates"]["independent_post_action_verified"] is True


def test_adapter_rejects_unknown_source_role():
    payload = action_payload("magic")
    with pytest.raises(ValueError, match="source_role"):
        verify_payload(payload)


def test_adapter_parses_medium_risk_source_threshold():
    payload = {
        "claim": {
            "id": "medium",
            "text": "Medium risk decision",
            "type": "observation",
            "risk": "medium",
        },
        "evidence": [
            {
                "source_id": "a",
                "evidence_id": "a1",
                "source_role": "external",
                "supports": True,
                "observed_at": T0,
                "directness": "direct",
            },
            {
                "source_id": "b",
                "evidence_id": "b1",
                "source_role": "verifier",
                "supports": True,
                "observed_at": T0,
                "directness": "direct",
            },
        ],
        "policy": {
            "version": "2.0",
            "max_age_seconds": 300,
            "medium_risk_min_independent_sources": 3,
        },
        "evaluation_time": T0,
    }

    result = verify_payload(payload)

    assert result["verdict"] == "ESCALATE"
    assert result["receipt"]["gates"]["independent_supporting_source_count"] == 2
    assert result["receipt"]["gates"]["medium_risk_required_sources"] == 3
