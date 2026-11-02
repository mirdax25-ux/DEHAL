from __future__ import annotations

from typing import Any, Mapping

from .adapter import SCHEMA_VERSION, verify_compound_payload
from .engine import ALGORITHM_VERSION


def _non_empty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{path} must be non-empty string")
    return value.strip()


def _metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    eligible_claims = sum(
        1
        for item in results
        if item["receipt"]["gates"]["eligible_source_count"] > 0
    )

    return {
        "total_claims": total,
        "verified_fact_count": sum(
            1
            for item in results
            if item["classification"] == "FACT" and item["verdict"] == "APPROVE"
        ),
        "unknown_blocked_count": sum(
            1
            for item in results
            if item["classification"] == "UNKNOWN" and item["verdict"] == "BLOCK"
        ),
        "conflict_blocked_count": sum(
            1
            for item in results
            if item["classification"] == "CONFLICT" and item["verdict"] == "BLOCK"
        ),
        "action_gate_blocked_count": sum(
            1
            for item in results
            if item["reason"] == "missing_post_action_final_state_evidence"
        ),
        "escalated_count": sum(
            1 for item in results if item["verdict"] == "ESCALATE"
        ),
        "blocked_unsupported_claim_count": sum(
            1
            for item in results
            if item["classification"] == "UNKNOWN" and item["verdict"] == "BLOCK"
        ),
        "evidence_coverage": (eligible_claims / total) if total else 0.0,
    }


def _bullet(item: dict[str, Any]) -> str:
    claim = item["receipt"]["claim"]
    return f"- [{item['classification']}/{item['verdict']}] {claim['text']}"


def _human_report(research_request: str, results: list[dict[str, Any]]) -> str:
    sections = [
        (
            "VERIFIED FACTS",
            [
                item
                for item in results
                if item["classification"] == "FACT"
                and item["verdict"] == "APPROVE"
            ],
        ),
        (
            "UNKNOWN / BLOCKED",
            [
                item
                for item in results
                if item["classification"] == "UNKNOWN"
                and item["verdict"] == "BLOCK"
            ],
        ),
        (
            "CONFLICTS",
            [item for item in results if item["classification"] == "CONFLICT"],
        ),
        (
            "ACTION GATE BLOCKS",
            [
                item
                for item in results
                if item["reason"] == "missing_post_action_final_state_evidence"
            ],
        ),
        (
            "ESCALATIONS",
            [item for item in results if item["verdict"] == "ESCALATE"],
        ),
    ]

    lines = [f"RESEARCH REQUEST: {research_request}", ""]
    for title, items in sections:
        lines.append(title)
        if items:
            lines.extend(_bullet(item) for item in items)
        else:
            lines.append("- none")
        lines.append("")

    return "\n".join(lines).rstrip()


def run_research_demo(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be object")

    research_request = _non_empty_string(
        payload.get("research_request"),
        "payload.research_request",
    )

    verification_payload = {
        "claims": payload.get("claims"),
        "evidence_by_claim": payload.get("evidence_by_claim"),
        "human_approvals": payload.get("human_approvals", {}),
        "policy": payload.get("policy"),
        "evaluation_time": payload.get("evaluation_time"),
    }

    verified = verify_compound_payload(verification_payload)
    results = verified["results"]
    policy = payload.get("policy")
    policy_version = (
        policy.get("version")
        if isinstance(policy, Mapping)
        else None
    )

    return {
        "research_request": research_request,
        "schema_version": SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "policy_version": policy_version,
        "overall_verdict": verified["verdict"],
        "results": results,
        "metrics": _metrics(results),
        "human_report": _human_report(research_request, results),
    }
