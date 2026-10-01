import json
from pathlib import Path

import pytest

from bodulskihal_core.evaluation import evaluate_benchmark


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "research_fixture.json"
BENCHMARK = ROOT / "examples" / "research_benchmark.json"


def load_inputs():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    return fixture, benchmark


def test_reference_benchmark_emits_expected_direct_metrics():
    fixture, benchmark = load_inputs()
    result = evaluate_benchmark(fixture, benchmark)
    metrics = result["metrics"]

    assert metrics["total_claims"] == 5
    assert metrics["auto_approved_count"] == 1
    assert metrics["auto_blocked_count"] == 3
    assert metrics["escalated_count"] == 1

    assert metrics["human_attention_queue_count"] == 2
    assert metrics["human_attention_rate"] == 0.4
    assert metrics["automatic_disposition_count"] == 3
    assert metrics["automatic_disposition_rate"] == 0.6

    assert metrics["evidence_coverage"] == 0.8
    assert metrics["unsupported_claim_block_rate"] == 1.0
    assert metrics["contradiction_detection_rate"] == 1.0
    assert metrics["action_completion_false_positive_rate"] == 0.0
    assert metrics["high_risk_without_human_approval_approve_rate"] == 0.0


def test_human_attention_queue_contains_conflict_and_escalation_only():
    fixture, benchmark = load_inputs()
    result = evaluate_benchmark(fixture, benchmark)

    assert result["human_attention_claim_ids"] == ["conflict", "high-risk"]


def test_benchmark_report_is_deterministic():
    fixture, benchmark = load_inputs()
    assert evaluate_benchmark(fixture, benchmark) == evaluate_benchmark(fixture, benchmark)


def test_human_summary_does_not_claim_hours_saved():
    fixture, benchmark = load_inputs()
    result = evaluate_benchmark(fixture, benchmark)

    summary = result["human_summary"].lower()
    assert "hours saved" not in summary
    assert "human attention" in summary
    assert "automatic disposition rate" in summary
    assert "false-positive" in summary


def test_benchmark_requires_label_for_every_claim():
    fixture, benchmark = load_inputs()
    del benchmark["labels"]["missing"]

    with pytest.raises(ValueError, match="benchmark label"):
        evaluate_benchmark(fixture, benchmark)


def test_benchmark_rejects_unknown_claim_labels():
    fixture, benchmark = load_inputs()
    benchmark["labels"]["ghost"] = "unsupported"

    with pytest.raises(ValueError, match="unknown claim"):
        evaluate_benchmark(fixture, benchmark)


def test_benchmark_rejects_unknown_label_kind():
    fixture, benchmark = load_inputs()
    benchmark["labels"]["supported"] = "magic"

    with pytest.raises(ValueError, match="benchmark label kind"):
        evaluate_benchmark(fixture, benchmark)
