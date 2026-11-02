from b_1_2_core.research_demo import run_research_demo


T0 = "2026-10-01T04:10:00+00:00"


def fixture():
    return {
        "research_request": "Assess five bounded research-agent claims.",
        "claims": [
            {
                "id": "supported",
                "text": "The supplied study record exists.",
                "type": "observation",
            },
            {
                "id": "missing",
                "text": "The second claim is supported.",
                "type": "observation",
            },
            {
                "id": "conflict",
                "text": "The two supplied sources agree.",
                "type": "observation",
            },
            {
                "id": "action",
                "text": "The external research export completed.",
                "type": "action_state",
            },
            {
                "id": "high-risk",
                "text": "A high-risk publication action is ready.",
                "type": "observation",
                "risk": "high",
            },
        ],
        "evidence_by_claim": {
            "supported": [
                {
                    "source_id": "study-record",
                    "supports": True,
                    "observed_at": T0,
                    "directness": "direct",
                }
            ],
            "missing": [],
            "conflict": [
                {
                    "source_id": "source-a",
                    "supports": True,
                    "observed_at": T0,
                    "directness": "direct",
                },
                {
                    "source_id": "source-b",
                    "supports": False,
                    "observed_at": T0,
                    "directness": "direct",
                },
            ],
            "action": [
                {
                    "source_id": "export-request",
                    "supports": True,
                    "observed_at": T0,
                    "directness": "direct",
                    "post_action": False,
                }
            ],
            "high-risk": [
                {
                    "source_id": "policy-check",
                    "supports": True,
                    "observed_at": T0,
                    "directness": "direct",
                }
            ],
        },
        "human_approvals": {},
        "policy": {"version": "1.0", "max_age_seconds": 300},
        "evaluation_time": T0,
    }


def test_demo_produces_expected_bounded_outcomes():
    result = run_research_demo(fixture())
    by_id = {item["receipt"]["claim"]["id"]: item for item in result["results"]}

    assert by_id["supported"]["classification"] == "FACT"
    assert by_id["supported"]["verdict"] == "APPROVE"

    assert by_id["missing"]["classification"] == "UNKNOWN"
    assert by_id["missing"]["verdict"] == "BLOCK"

    assert by_id["conflict"]["classification"] == "CONFLICT"
    assert by_id["conflict"]["verdict"] == "BLOCK"

    assert by_id["action"]["classification"] == "FACT"
    assert by_id["action"]["verdict"] == "BLOCK"
    assert by_id["action"]["reason"] == "missing_post_action_final_state_evidence"

    assert by_id["high-risk"]["classification"] == "FACT"
    assert by_id["high-risk"]["verdict"] == "ESCALATE"


def test_demo_emits_measurement_metrics():
    result = run_research_demo(fixture())
    metrics = result["metrics"]

    assert metrics["total_claims"] == 5
    assert metrics["verified_fact_count"] == 1
    assert metrics["unknown_blocked_count"] == 1
    assert metrics["conflict_blocked_count"] == 1
    assert metrics["action_gate_blocked_count"] == 1
    assert metrics["escalated_count"] == 1
    assert metrics["blocked_unsupported_claim_count"] == 1
    assert metrics["evidence_coverage"] == 0.8


def test_demo_human_report_distinguishes_truth_states():
    result = run_research_demo(fixture())
    report = result["human_report"]

    assert "VERIFIED FACTS" in report
    assert "UNKNOWN / BLOCKED" in report
    assert "CONFLICTS" in report
    assert "ACTION GATE BLOCKS" in report
    assert "ESCALATIONS" in report

    assert "The supplied study record exists." in report
    assert "The second claim is supported." in report
    assert "The two supplied sources agree." in report
    assert "The external research export completed." in report
    assert "A high-risk publication action is ready." in report


def test_demo_preserves_versioned_receipts():
    result = run_research_demo(fixture())

    assert result["schema_version"] == 3
    assert result["algorithm_version"] == "2.1.2"
    assert result["policy_version"] == "1.0"

    for item in result["results"]:
        receipt = item["receipt"]
        assert receipt["algorithm_version"] == "2.1.2"
        assert receipt["policy_version"] == "1.0"


def test_demo_is_deterministic_for_same_fixture():
    assert run_research_demo(fixture()) == run_research_demo(fixture())
