from __future__ import annotations

from typing import Any, Mapping

from .research_demo import run_research_demo


_ALLOWED_LABELS = {
    "supported",
    "unsupported",
    "contradiction",
    "action_without_post_state",
    "high_risk_without_human_approval",
}


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must be object")
    return value


def _rate(numerator: int, denominator: int) -> float:
    return (numerator / denominator) if denominator else 0.0


def _validate_labels(
    fixture: Mapping[str, Any],
    benchmark: Mapping[str, Any],
) -> dict[str, str]:
    claims = fixture.get("claims")
    if not isinstance(claims, list):
        raise TypeError("fixture.claims must be list")

    claim_ids: list[str] = []
    for index, raw in enumerate(claims):
        claim = _mapping(raw, f"fixture.claims[{index}]")
        claim_id = claim.get("id")
        if not isinstance(claim_id, str) or not claim_id:
            raise TypeError(f"fixture.claims[{index}].id must be non-empty string")
        claim_ids.append(claim_id)

    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("fixture contains duplicate claim id")

    labels_raw = _mapping(benchmark.get("labels"), "benchmark.labels")
    unknown_ids = sorted(set(labels_raw) - set(claim_ids))
    if unknown_ids:
        raise ValueError("benchmark label references unknown claim: " + ", ".join(unknown_ids))

    missing_ids = [claim_id for claim_id in claim_ids if claim_id not in labels_raw]
    if missing_ids:
        raise ValueError("missing benchmark label for claim: " + ", ".join(missing_ids))

    labels: dict[str, str] = {}
    for claim_id in claim_ids:
        label = labels_raw[claim_id]
        if not isinstance(label, str) or label not in _ALLOWED_LABELS:
            raise ValueError(f"invalid benchmark label kind for {claim_id}: {label}")
        labels[claim_id] = label

    missing_kinds = sorted(_ALLOWED_LABELS - set(labels.values()))
    if missing_kinds:
        raise ValueError(
            "benchmark must contain every benchmark label kind: "
            + ", ".join(missing_kinds)
        )

    return labels


def _claim_ids_with_label(labels: Mapping[str, str], kind: str) -> list[str]:
    return [claim_id for claim_id, label in labels.items() if label == kind]


def _summary(metrics: Mapping[str, Any]) -> str:
    return (
        "BENCHMARK SUMMARY\n"
        f"- total claims: {metrics['total_claims']}\n"
        f"- automatic disposition rate: {metrics['automatic_disposition_rate']:.2f}\n"
        f"- human attention queue: {metrics['human_attention_queue_count']} "
        f"({metrics['human_attention_rate']:.2f})\n"
        f"- evidence coverage: {metrics['evidence_coverage']:.2f}\n"
        f"- unsupported-claim block rate: {metrics['unsupported_claim_block_rate']:.2f}\n"
        f"- contradiction detection rate: {metrics['contradiction_detection_rate']:.2f}\n"
        f"- action-completion false-positive rate: "
        f"{metrics['action_completion_false_positive_rate']:.2f}\n"
        f"- high-risk unauthorized approve rate: "
        f"{metrics['high_risk_without_human_approval_approve_rate']:.2f}\n"
        "Human attention is a routing count/rate, not a claim of reviewer hours saved."
    )


def evaluate_benchmark(
    fixture: Mapping[str, Any],
    benchmark: Mapping[str, Any],
) -> dict[str, Any]:
    fixture_obj = _mapping(fixture, "fixture")
    benchmark_obj = _mapping(benchmark, "benchmark")
    labels = _validate_labels(fixture_obj, benchmark_obj)

    demo = run_research_demo(fixture_obj)
    results = demo["results"]
    by_id = {
        item["receipt"]["claim"]["id"]: item
        for item in results
    }

    total = len(results)
    auto_approved_count = sum(
        1 for item in results if item["verdict"] == "APPROVE"
    )
    auto_blocked_count = sum(
        1 for item in results if item["verdict"] == "BLOCK"
    )
    escalated_count = sum(
        1 for item in results if item["verdict"] == "ESCALATE"
    )

    human_attention_claim_ids = [
        item["receipt"]["claim"]["id"]
        for item in results
        if item["classification"] == "CONFLICT"
        or item["verdict"] == "ESCALATE"
    ]
    human_attention_queue_count = len(human_attention_claim_ids)
    automatic_disposition_count = total - human_attention_queue_count

    unsupported_ids = _claim_ids_with_label(labels, "unsupported")
    contradiction_ids = _claim_ids_with_label(labels, "contradiction")
    action_ids = _claim_ids_with_label(labels, "action_without_post_state")
    high_risk_ids = _claim_ids_with_label(
        labels,
        "high_risk_without_human_approval",
    )

    unsupported_blocked = sum(
        1 for claim_id in unsupported_ids if by_id[claim_id]["verdict"] == "BLOCK"
    )
    contradiction_detected = sum(
        1
        for claim_id in contradiction_ids
        if by_id[claim_id]["classification"] == "CONFLICT"
    )
    action_false_positive_approves = sum(
        1 for claim_id in action_ids if by_id[claim_id]["verdict"] == "APPROVE"
    )
    high_risk_unauthorized_approves = sum(
        1
        for claim_id in high_risk_ids
        if by_id[claim_id]["verdict"] == "APPROVE"
    )

    metrics = {
        "total_claims": total,
        "auto_approved_count": auto_approved_count,
        "auto_blocked_count": auto_blocked_count,
        "escalated_count": escalated_count,
        "human_attention_queue_count": human_attention_queue_count,
        "human_attention_rate": _rate(human_attention_queue_count, total),
        "automatic_disposition_count": automatic_disposition_count,
        "automatic_disposition_rate": _rate(automatic_disposition_count, total),
        "evidence_coverage": demo["metrics"]["evidence_coverage"],
        "unsupported_claim_block_rate": _rate(
            unsupported_blocked,
            len(unsupported_ids),
        ),
        "contradiction_detection_rate": _rate(
            contradiction_detected,
            len(contradiction_ids),
        ),
        "action_completion_false_positive_rate": _rate(
            action_false_positive_approves,
            len(action_ids),
        ),
        "high_risk_without_human_approval_approve_rate": _rate(
            high_risk_unauthorized_approves,
            len(high_risk_ids),
        ),
    }

    return {
        "benchmark_version": benchmark_obj.get("version"),
        "research_request": demo["research_request"],
        "algorithm_version": demo["algorithm_version"],
        "schema_version": demo["schema_version"],
        "policy_version": demo["policy_version"],
        "labels": labels,
        "metrics": metrics,
        "human_attention_claim_ids": human_attention_claim_ids,
        "human_summary": _summary(metrics),
    }
