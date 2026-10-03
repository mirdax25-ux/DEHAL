from datetime import datetime, timezone

import pytest

from bodulskihal_core.adapter import SCHEMA_VERSION, verify_compound_payload, verify_payload

T0 = "2026-10-01T03:50:00+00:00"


def base_payload():
    return {
        "claim": {
            "id": "c1",
            "text": "Email sent",
            "type": "action_state",
            "risk": "low",
            "consequential": True,
        },
        "evidence": [
            {
                "source_id": "provider-final-state",
                "supports": True,
                "observed_at": T0,
                "directness": "direct",
                "post_action": True,
                "eligible": True,
            }
        ],
        "policy": {
            "version": "1.0",
            "max_age_seconds": 300,
            "reject_future_evidence": True,
        },
        "evaluation_time": T0,
        "human_approved": False,
    }


def test_verify_payload_returns_json_safe_result():
    result = verify_payload(base_payload())
    assert result["schema_version"] == SCHEMA_VERSION == 3
    assert result["algorithm_version"] == "2.1.0"
    assert result["classification"] == "FACT"
    assert result["verdict"] == "APPROVE"
    assert result["receipt"]["claim"]["id"] == "c1"


def test_verify_payload_blocks_missing_post_action_evidence():
    payload = base_payload()
    payload["evidence"][0]["post_action"] = False
    result = verify_payload(payload)
    assert result["verdict"] == "BLOCK"
    assert result["reason"] == "missing_post_action_final_state_evidence"


def test_verify_payload_requires_timezone_aware_iso_datetime():
    payload = base_payload()
    payload["evaluation_time"] = "2026-10-01T03:50:00"
    with pytest.raises(ValueError, match="timezone-aware"):
        verify_payload(payload)


def test_verify_payload_accepts_z_suffix_as_utc():
    payload = base_payload()
    payload["evaluation_time"] = "2026-10-01T03:50:00Z"
    payload["evidence"][0]["observed_at"] = "2026-10-01T03:50:00Z"
    result = verify_payload(payload)
    assert result["verdict"] == "APPROVE"


def test_verify_payload_rejects_unknown_enum_values():
    payload = base_payload()
    payload["claim"]["type"] = "magic"
    with pytest.raises(ValueError):
        verify_payload(payload)


def test_verify_payload_rejects_non_boolean_supports():
    payload = base_payload()
    payload["evidence"][0]["supports"] = 1
    with pytest.raises(TypeError, match="supports must be bool"):
        verify_payload(payload)


def test_verify_payload_rejects_missing_required_claim_key():
    payload = base_payload()
    del payload["claim"]["text"]
    with pytest.raises(ValueError, match="claim.text"):
        verify_payload(payload)


def test_verify_payload_escalates_high_risk_without_human_approval():
    payload = base_payload()
    payload["claim"]["risk"] = "high"
    result = verify_payload(payload)
    assert result["classification"] == "FACT"
    assert result["verdict"] == "ESCALATE"


def test_compound_payload_requires_every_consequential_clause():
    payload = {
        "claims": [
            {"id": "c1", "text": "Email sent", "type": "action_state"},
            {"id": "c2", "text": "Tests passed", "type": "observation"},
        ],
        "evidence_by_claim": {
            "c1": [
                {
                    "source_id": "provider-final-state",
                    "supports": True,
                    "observed_at": T0,
                    "directness": "direct",
                    "post_action": True,
                }
            ],
            "c2": [],
        },
        "policy": {"version": "1.0", "max_age_seconds": 300},
        "evaluation_time": T0,
    }
    result = verify_compound_payload(payload)
    assert result["schema_version"] == 3
    assert result["verdict"] == "BLOCK"
    assert [item["verdict"] for item in result["results"]] == ["APPROVE", "BLOCK"]


def test_compound_payload_rejects_unknown_evidence_claim_id():
    payload = {
        "claims": [{"id": "c1", "text": "File exists", "type": "observation"}],
        "evidence_by_claim": {"other": []},
        "policy": {"version": "1.0", "max_age_seconds": 300},
        "evaluation_time": T0,
    }
    with pytest.raises(ValueError, match="unknown claim id"):
        verify_compound_payload(payload)
