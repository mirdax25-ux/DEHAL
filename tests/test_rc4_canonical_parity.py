import pytest

from bodulskihal_core.adapter import verify_payload


T0 = "2026-10-06T18:00:00+00:00"


def payload() -> dict:
    return {
        "claim": {
            "id": "claim-1",
            "text": "Bounded observation",
            "type": "observation",
        },
        "evidence": [
            {
                "source_id": "source-1",
                "supports": True,
                "observed_at": T0,
                "directness": "direct",
            }
        ],
        "policy": {
            "version": "2.1.2",
            "max_age_seconds": 300,
        },
        "evaluation_time": T0,
    }


def test_rc4_parity_rejects_whitespace_claim_identity():
    candidate = payload()
    candidate["claim"]["id"] = "   "
    with pytest.raises((TypeError, ValueError), match="claim.id"):
        verify_payload(candidate)


def test_rc4_parity_rejects_whitespace_source_identity():
    candidate = payload()
    candidate["evidence"][0]["source_id"] = "   "
    with pytest.raises((TypeError, ValueError), match="source_id"):
        verify_payload(candidate)
