from datetime import datetime, timezone
from itertools import product

from b_1_2_core import (
    Claim,
    ClaimType,
    Classification,
    Directness,
    Evidence,
    Policy,
    RiskLevel,
    Verdict,
    verify_claim,
)

T0 = datetime(2026, 9, 30, 19, 0, tzinfo=timezone.utc)
POLICY = Policy(version="1.0", max_age_seconds=300)


def test_exhaustive_boolean_core_invariants_128_cases():
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
        # Keep type selection deterministic if both inference and estimate bits are true.
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
            "bounded invariant case",
            claim_type,
            risk=RiskLevel.HIGH if high_risk else RiskLevel.LOW,
        )
        evidence = []
        if has_evidence:
            evidence.append(
                Evidence(
                    "support",
                    True,
                    T0,
                    Directness.DIRECT,
                    post_action=post_action,
                )
            )
        if contradiction:
            evidence.append(
                Evidence(
                    "contradiction",
                    False,
                    T0,
                    Directness.DIRECT,
                    post_action=post_action,
                )
            )

        result_no_human = verify_claim(
            claim, evidence, policy=POLICY, evaluation_time=T0, human_approved=False
        )
        result_human = verify_claim(
            claim, evidence, policy=POLICY, evaluation_time=T0, human_approved=True
        )

        # I1/I2: no evidence cannot become FACT/APPROVE, unless contradiction evidence exists,
        # in which case the stronger fail-closed state is CONFLICT.
        if not has_evidence and not contradiction:
            assert result_no_human.classification is Classification.UNKNOWN
            assert result_no_human.verdict is Verdict.BLOCK

        # I3/I4: mixed support/counterevidence is CONFLICT; pure counterevidence is REFUTED.
        if contradiction:
            expected = (
                Classification.CONFLICT
                if has_evidence
                else Classification.REFUTED
            )
            assert result_no_human.classification is expected
            assert result_no_human.verdict is Verdict.BLOCK
            assert result_human.verdict is Verdict.BLOCK

        # I5: non-FACT classifications never approve.
        if result_no_human.classification is not Classification.FACT:
            assert result_no_human.verdict is not Verdict.APPROVE

        # I6: action-state FACT cannot approve without post-action proof.
        if action_claim and claim_type is ClaimType.ACTION_STATE and has_evidence and not contradiction and not post_action:
            assert result_no_human.verdict is Verdict.BLOCK
            assert result_human.verdict is Verdict.BLOCK

        # I7: high-risk FACT needs human approval once all non-human gates pass.
        nonhuman_gates_pass = not (
            action_claim and claim_type is ClaimType.ACTION_STATE and not post_action
        )
        if high_risk and result_no_human.classification is Classification.FACT and nonhuman_gates_pass:
            assert result_no_human.verdict is Verdict.ESCALATE
            assert result_human.verdict is Verdict.APPROVE

        checked += 1

    assert checked == 128
