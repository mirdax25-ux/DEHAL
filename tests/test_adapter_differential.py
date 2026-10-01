from datetime import datetime, timezone
from itertools import product

from bodulskihal_core import (
    Claim,
    ClaimType,
    Directness,
    Evidence,
    Policy,
    RiskLevel,
    verify_claim,
)
from bodulskihal_core.adapter import verify_payload

T0 = datetime(2026, 10, 1, 3, 50, tzinfo=timezone.utc)
POLICY = Policy(version="1.0", max_age_seconds=300)


def test_adapter_matches_core_across_128_boolean_cases():
    checked = 0
    for (
        has_evidence,
        contradiction,
        inference_only,
        estimate_only,
        action_claim,
        post_action,
        high_risk,
    ) in product([False, True], repeat=7):
        if inference_only:
            claim_type = ClaimType.INFERENCE
        elif estimate_only:
            claim_type = ClaimType.ESTIMATE
        elif action_claim:
            claim_type = ClaimType.ACTION_STATE
        else:
            claim_type = ClaimType.OBSERVATION

        claim = Claim(
            "c",
            "adapter differential case",
            claim_type,
            risk=RiskLevel.HIGH if high_risk else RiskLevel.LOW,
        )
        evidence = []
        evidence_json = []
        if has_evidence:
            evidence.append(Evidence("support", True, T0, Directness.DIRECT, post_action=post_action))
            evidence_json.append({
                "source_id": "support",
                "supports": True,
                "observed_at": T0.isoformat(),
                "directness": "direct",
                "post_action": post_action,
            })
        if contradiction:
            evidence.append(Evidence("contradiction", False, T0, Directness.DIRECT, post_action=post_action))
            evidence_json.append({
                "source_id": "contradiction",
                "supports": False,
                "observed_at": T0.isoformat(),
                "directness": "direct",
                "post_action": post_action,
            })

        for human_approved in (False, True):
            core = verify_claim(
                claim,
                evidence,
                policy=POLICY,
                evaluation_time=T0,
                human_approved=human_approved,
            )
            adapted = verify_payload({
                "claim": {
                    "id": claim.claim_id,
                    "text": claim.text,
                    "type": claim.claim_type.value,
                    "risk": claim.risk.value,
                    "consequential": True,
                },
                "evidence": evidence_json,
                "policy": {"version": "1.0", "max_age_seconds": 300},
                "evaluation_time": T0.isoformat(),
                "human_approved": human_approved,
            })
            assert adapted["classification"] == core.classification.value
            assert adapted["verdict"] == core.verdict.value
            assert adapted["reason"] == core.reason
            assert adapted["receipt"] == core.receipt
        checked += 1

    assert checked == 128
