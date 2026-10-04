"""Prototype for the exact grouped architecture:

    N1 <-> N2 -> N2(final) -> C -> S1 -> S2 -> N1(read-only) -> OUTPUT

This is an isolated deterministic testbed for trust-boundary behavior. It does
not call a model or claim real-world correctness. Untrusted N1/N2 data are
bound into receipts by a tiny HMAC-based in-process boundary; the HMAC is a
prototype provenance mechanism, not production key management.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import math
import re
from typing import Any

VERSION = "0.1.1"
STATUS_ORDER = {"PASS": 0, "UNKNOWN": 1, "BLOCK": 2, "CONFLICT": 3}
TERMINAL_STATUSES = frozenset(STATUS_ORDER)


class ProtocolError(ValueError):
    pass


def _reject_constant(_: str):
    raise ProtocolError("nonfinite_json_number")


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ProtocolError("nonfinite_json_number")
    return result


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ProtocolError("duplicate_json_key")
        out[key] = value
    return out


def strict_json_loads(text: str):
    return json.loads(
        text,
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
        parse_float=_finite_float,
    )


def canonical(value: Any) -> bytes:
    """Small canonical JSON domain used by all hashes/MACs in the prototype."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ProtocolError("noncanonical_value") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _strict_keys(value: Any, keys: tuple[str, ...], *, optional: tuple[str, ...] = ()):
    if type(value) is not dict:
        raise ProtocolError("object_required")
    allowed = set(keys) | set(optional)
    if set(value) - allowed or set(keys) - set(value):
        raise ProtocolError("unexpected_or_missing_fields")


def _name(value: Any) -> bool:
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", value) is not None


def worst_status(*statuses: str) -> str:
    if not statuses:
        raise ProtocolError("status_required")
    if any(s not in TERMINAL_STATUSES for s in statuses):
        raise ProtocolError("invalid_status")
    return max(statuses, key=lambda s: STATUS_ORDER[s])


@dataclass
class TrustedBoundary:
    secret: bytes
    consumed_tokens: set[str] = field(default_factory=set)

    def _mac(self, body: dict[str, Any]) -> str:
        return hmac.new(self.secret, canonical(body), hashlib.sha256).hexdigest()

    def issue(self, *, issuer: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not _name(issuer) or not _name(kind):
            raise ProtocolError("invalid_receipt_identity")
        body = {"v": VERSION, "issuer": issuer, "kind": kind, "payload": deepcopy(payload)}
        return {**body, "mac": self._mac(body)}

    def verify(self, receipt: Any, *, issuer: str | None = None, kind: str | None = None) -> dict[str, Any]:
        _strict_keys(receipt, ("v", "issuer", "kind", "payload", "mac"))
        if receipt["v"] != VERSION or type(receipt["mac"]) is not str:
            raise ProtocolError("invalid_receipt")
        body = {k: deepcopy(receipt[k]) for k in ("v", "issuer", "kind", "payload")}
        if not hmac.compare_digest(receipt["mac"], self._mac(body)):
            raise ProtocolError("receipt_mac_mismatch")
        if issuer is not None and receipt["issuer"] != issuer:
            raise ProtocolError("receipt_issuer_mismatch")
        if kind is not None and receipt["kind"] != kind:
            raise ProtocolError("receipt_kind_mismatch")
        return deepcopy(receipt["payload"])

    def make_transition_envelope(
        self,
        *,
        goal_id: str,
        state: dict[str, Any],
        policy: dict[str, Any],
        evidence_root: str,
        previous_receipt_hash: str,
        global_anchor: dict[str, Any],
        phase_id: str = "group3",
    ) -> dict[str, Any]:
        validate_state(state)
        validate_policy(policy)
        validate_anchor(global_anchor)
        if not all(_name(x) for x in (goal_id, evidence_root, previous_receipt_hash, phase_id)):
            raise ProtocolError("invalid_transition_identity")
        payload = {
            "goal_id": goal_id,
            "contract_hash": digest(policy),
            "schema_version": policy["schema_version"],
            "state_hash": digest(state),
            "state_version": state["version"],
            "evidence_root": evidence_root,
            "previous_receipt_hash": previous_receipt_hash,
            "phase_id": phase_id,
            "global_anchor": deepcopy(global_anchor),
        }
        return self.issue(issuer="S-boundary", kind="transition", payload=payload)


def validate_state(state: Any):
    _strict_keys(state, ("version", "balance", "verified_recipients"))
    if type(state["version"]) is not int or state["version"] < 0:
        raise ProtocolError("invalid_state_version")
    if type(state["balance"]) is not int or state["balance"] < 0:
        raise ProtocolError("invalid_balance")
    recipients = state["verified_recipients"]
    if type(recipients) is not list or any(not _name(x) for x in recipients) or len(recipients) != len(set(recipients)):
        raise ProtocolError("invalid_recipient_set")


def validate_policy(policy: Any):
    _strict_keys(policy, ("schema_version", "contract_id", "max_amount", "allowed_actions"))
    if policy["schema_version"] != 1 or type(policy["schema_version"]) is not int:
        raise ProtocolError("unsupported_policy_schema")
    if not _name(policy["contract_id"]):
        raise ProtocolError("invalid_contract_id")
    if type(policy["max_amount"]) is not int or policy["max_amount"] <= 0:
        raise ProtocolError("invalid_max_amount")
    actions = policy["allowed_actions"]
    if type(actions) is not list or not actions or any(not _name(x) for x in actions):
        raise ProtocolError("invalid_allowed_actions")


def validate_anchor(anchor: Any):
    _strict_keys(anchor, ("status", "independent", "scope", "state_version"))
    if anchor["status"] not in ("PASS", "UNKNOWN", "CONFLICT"):
        raise ProtocolError("invalid_anchor_status")
    if type(anchor["independent"]) is not bool:
        raise ProtocolError("invalid_anchor_independence")
    if type(anchor["scope"]) is not list or any(not _name(x) for x in anchor["scope"]):
        raise ProtocolError("invalid_anchor_scope")
    if type(anchor["state_version"]) is not int or anchor["state_version"] < 0:
        raise ProtocolError("invalid_anchor_state_version")


def validate_candidate(candidate: Any):
    _strict_keys(candidate, ("goal_id", "state_version", "action"))
    if not _name(candidate["goal_id"]):
        raise ProtocolError("invalid_candidate_goal")
    if type(candidate["state_version"]) is not int or candidate["state_version"] < 0:
        raise ProtocolError("invalid_candidate_state_version")
    action = candidate["action"]
    _strict_keys(action, ("type", "recipient", "amount", "memo"))
    if not _name(action["type"]) or not _name(action["recipient"]):
        raise ProtocolError("invalid_action_identity")
    if type(action["amount"]) is not int or action["amount"] <= 0:
        raise ProtocolError("invalid_action_amount")
    if type(action["memo"]) is not str or len(action["memo"]) > 240:
        raise ProtocolError("invalid_action_memo")


def validate_n2_review(review: Any):
    _strict_keys(review, ("round_id", "decision", "issues"))
    if type(review["round_id"]) is not int or review["round_id"] < 0:
        raise ProtocolError("invalid_round")
    if review["decision"] not in ("CLEAR", "CHALLENGE", "UNKNOWN"):
        raise ProtocolError("invalid_review_decision")
    if type(review["issues"]) is not list or any(not _name(x) for x in review["issues"]):
        raise ProtocolError("invalid_review_issues")


def seal_n2_review(boundary: TrustedBoundary, *, candidate: dict[str, Any], review: dict[str, Any], parent_hash: str) -> dict[str, Any]:
    validate_candidate(candidate)
    validate_n2_review(review)
    if not _name(parent_hash):
        raise ProtocolError("invalid_parent_hash")
    payload = {
        "candidate_hash": digest(candidate),
        "parent_hash": parent_hash,
        "round_id": review["round_id"],
        "decision": review["decision"],
        "issues": list(review["issues"]),
    }
    return boundary.issue(issuer="N2", kind="review", payload=payload)


def n1_n2_loop(
    boundary: TrustedBoundary,
    *,
    initial_candidate: dict[str, Any],
    exchanges: list[dict[str, Any]],
    transition_receipt: dict[str, Any],
    max_rounds: int = 4,
) -> dict[str, Any]:
    if type(max_rounds) is not int or not 1 <= max_rounds <= 16:
        raise ProtocolError("invalid_max_rounds")
    transition = boundary.verify(transition_receipt, issuer="S-boundary", kind="transition")
    candidate = deepcopy(initial_candidate)
    validate_candidate(candidate)
    if candidate["goal_id"] != transition["goal_id"] or candidate["state_version"] != transition["state_version"]:
        raise ProtocolError("candidate_transition_mismatch")
    receipts = []
    seen = {digest(candidate)}
    loop_status = "UNKNOWN"
    for index, exchange in enumerate(exchanges):
        if index >= max_rounds:
            break
        _strict_keys(exchange, ("n2",), optional=("n1_revision",))
        review = deepcopy(exchange["n2"])
        validate_n2_review(review)
        if review["round_id"] != index:
            raise ProtocolError("round_mismatch")
        parent_hash = digest(transition_receipt) if not receipts else digest(receipts[-1])
        receipt = seal_n2_review(boundary, candidate=candidate, review=review, parent_hash=parent_hash)
        receipts.append(receipt)
        if review["decision"] == "CLEAR":
            loop_status = "PASS"
            break
        if review["decision"] == "UNKNOWN":
            loop_status = "UNKNOWN"
            break
        if "n1_revision" not in exchange:
            loop_status = "CONFLICT"
            break
        revised = deepcopy(exchange["n1_revision"])
        validate_candidate(revised)
        if revised["goal_id"] != transition["goal_id"] or revised["state_version"] != transition["state_version"]:
            raise ProtocolError("revision_transition_mismatch")
        d = digest(revised)
        if d in seen:
            loop_status = "UNKNOWN"
            break
        seen.add(d)
        candidate = revised
    return {
        "candidate": candidate,
        "receipts": receipts,
        "loop_status": loop_status,
        "loop_root": digest([digest(r) for r in receipts]),
    }


def final_n2(boundary: TrustedBoundary, *, loop_result: dict[str, Any], review: dict[str, Any], transition_receipt: dict[str, Any]) -> dict[str, Any]:
    _strict_keys(loop_result, ("candidate", "receipts", "loop_status", "loop_root"))
    transition = boundary.verify(transition_receipt, issuer="S-boundary", kind="transition")
    candidate = deepcopy(loop_result["candidate"])
    validate_candidate(candidate)
    validate_n2_review(review)
    parent = loop_result["loop_root"]
    receipt = seal_n2_review(boundary, candidate=candidate, review=review, parent_hash=parent)
    payload = boundary.verify(receipt, issuer="N2", kind="review")
    if payload["candidate_hash"] != digest(candidate) or candidate["goal_id"] != transition["goal_id"]:
        raise ProtocolError("final_n2_binding_mismatch")
    return receipt


def make_checkpoint(
    boundary: TrustedBoundary,
    *,
    transition_receipt: dict[str, Any],
    loop_result: dict[str, Any],
    final_n2_receipt: dict[str, Any],
) -> dict[str, Any]:
    transition = boundary.verify(transition_receipt, issuer="S-boundary", kind="transition")
    candidate = deepcopy(loop_result["candidate"])
    validate_candidate(candidate)
    n2 = boundary.verify(final_n2_receipt, issuer="N2", kind="review")
    if n2["candidate_hash"] != digest(candidate):
        raise ProtocolError("final_review_wrong_candidate")
    payload = {
        "transition_hash": digest(transition_receipt),
        "goal_id": transition["goal_id"],
        "contract_hash": transition["contract_hash"],
        "state_hash": transition["state_hash"],
        "state_version": transition["state_version"],
        "evidence_root": transition["evidence_root"],
        "candidate": candidate,
        "candidate_hash": digest(candidate),
        "loop_status": loop_result["loop_status"],
        "loop_root": loop_result["loop_root"],
        "final_n2_receipt_hash": digest(final_n2_receipt),
        "final_n2_decision": n2["decision"],
        "final_n2_issues": list(n2["issues"]),
        "global_anchor": deepcopy(transition["global_anchor"]),
    }
    return boundary.issue(issuer="C", kind="checkpoint", payload=payload)


def s1_verify(
    boundary: TrustedBoundary,
    *,
    checkpoint: dict[str, Any],
    transition_receipt: dict[str, Any],
    final_n2_receipt: dict[str, Any],
    current_state: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    try:
        cp = boundary.verify(checkpoint, issuer="C", kind="checkpoint")
        tr = boundary.verify(transition_receipt, issuer="S-boundary", kind="transition")
        n2 = boundary.verify(final_n2_receipt, issuer="N2", kind="review")
        validate_state(current_state)
        validate_policy(policy)
        validate_candidate(cp["candidate"])
        checks = {
            "transition_hash": cp["transition_hash"] == digest(transition_receipt),
            "goal": cp["goal_id"] == tr["goal_id"] == cp["candidate"]["goal_id"],
            "contract": cp["contract_hash"] == digest(policy) == tr["contract_hash"],
            "state_hash": cp["state_hash"] == digest(current_state) == tr["state_hash"],
            "state_version": cp["state_version"] == current_state["version"] == tr["state_version"] == cp["candidate"]["state_version"],
            "candidate_hash": cp["candidate_hash"] == digest(cp["candidate"]) == n2["candidate_hash"],
            "n2_receipt": cp["final_n2_receipt_hash"] == digest(final_n2_receipt),
        }
        status = "PASS" if all(checks.values()) else "BLOCK"
        payload = {"status": status, "checkpoint_hash": digest(checkpoint), "checks": checks}
    except (ProtocolError, KeyError, TypeError, ValueError, OverflowError):
        payload = {"status": "BLOCK", "checkpoint_hash": digest(checkpoint) if type(checkpoint) is dict else None, "checks": {}}
    return boundary.issue(issuer="S1", kind="integrity", payload=payload)


def _contract_status(candidate: dict[str, Any], state: dict[str, Any], policy: dict[str, Any]) -> str:
    action = candidate["action"]
    if action["type"] not in policy["allowed_actions"]:
        return "BLOCK"
    if action["amount"] > policy["max_amount"] or action["amount"] > state["balance"]:
        return "BLOCK"
    if action["recipient"] not in state["verified_recipients"]:
        return "BLOCK"
    return "PASS"


def _global_status(anchor: dict[str, Any], state_version: int) -> str:
    validate_anchor(anchor)
    if anchor["status"] == "CONFLICT":
        return "CONFLICT"
    if not anchor["independent"] or "goal" not in anchor["scope"] or anchor["state_version"] != state_version:
        return "UNKNOWN"
    return "PASS" if anchor["status"] == "PASS" else "UNKNOWN"


def _n2_decision_status(decision: str) -> str:
    if decision == "CLEAR":
        return "PASS"
    if decision == "UNKNOWN":
        return "UNKNOWN"
    if decision == "CHALLENGE":
        return "CONFLICT"
    raise ProtocolError("invalid_n2_decision")


def s2_decide(
    boundary: TrustedBoundary,
    *,
    checkpoint: dict[str, Any],
    s1_receipt: dict[str, Any],
    current_state: dict[str, Any],
    policy: dict[str, Any],
    action_nonce: str,
) -> dict[str, Any]:
    try:
        cp = boundary.verify(checkpoint, issuer="C", kind="checkpoint")
        s1 = boundary.verify(s1_receipt, issuer="S1", kind="integrity")
        validate_state(current_state)
        validate_policy(policy)
        if not _name(action_nonce):
            raise ProtocolError("invalid_action_nonce")
        if s1["checkpoint_hash"] != digest(checkpoint):
            raise ProtocolError("s1_wrong_checkpoint")
        integrity = s1["status"]
        loop_status = cp["loop_status"]
        if loop_status not in ("PASS", "UNKNOWN", "CONFLICT"):
            raise ProtocolError("invalid_loop_status")
        final_n2_status = _n2_decision_status(cp["final_n2_decision"])
        contract = _contract_status(cp["candidate"], current_state, policy)
        global_status = _global_status(cp["global_anchor"], current_state["version"])
        terminal = worst_status(integrity, loop_status, final_n2_status, contract, global_status)
        payload = {
            "terminal_status": terminal,
            "integrity_status": integrity,
            "loop_status": loop_status,
            "final_n2_status": final_n2_status,
            "contract_status": contract,
            "global_goal_status": global_status,
            "checkpoint_hash": digest(checkpoint),
            "state_hash": digest(current_state),
            "state_version": current_state["version"],
            "contract_hash": digest(policy),
            "action": deepcopy(cp["candidate"]["action"]),
            "action_hash": digest(cp["candidate"]["action"]),
            "action_nonce": action_nonce,
        }
    except (ProtocolError, KeyError, TypeError, ValueError, OverflowError):
        payload = {
            "terminal_status": "BLOCK",
            "integrity_status": "BLOCK",
            "loop_status": "UNKNOWN",
            "final_n2_status": "UNKNOWN",
            "contract_status": "BLOCK",
            "global_goal_status": "UNKNOWN",
            "checkpoint_hash": digest(checkpoint) if type(checkpoint) is dict else None,
            "state_hash": digest(current_state) if type(current_state) is dict else None,
            "state_version": current_state.get("version") if type(current_state) is dict else None,
            "contract_hash": digest(policy) if type(policy) is dict else None,
            "action": None,
            "action_hash": None,
            "action_nonce": action_nonce if type(action_nonce) is str else None,
        }
    return boundary.issue(issuer="S2", kind="terminal", payload=payload)


def render_readonly(boundary: TrustedBoundary, *, terminal_receipt: dict[str, Any], presentation: dict[str, Any]) -> dict[str, Any]:
    terminal = boundary.verify(terminal_receipt, issuer="S2", kind="terminal")
    _strict_keys(presentation, ("text",))
    if type(presentation["text"]) is not str or len(presentation["text"]) > 2000:
        raise ProtocolError("invalid_presentation")
    return {
        "terminal_status": terminal["terminal_status"],
        "action": deepcopy(terminal["action"]),
        "action_hash": terminal["action_hash"],
        "state_version": terminal["state_version"],
        "terminal_receipt": deepcopy(terminal_receipt),
        "explanation": presentation["text"],
    }


def execute(boundary: TrustedBoundary, *, output: dict[str, Any], current_state: dict[str, Any], action: dict[str, Any]) -> str:
    try:
        _strict_keys(output, ("terminal_status", "action", "action_hash", "state_version", "terminal_receipt", "explanation"))
        terminal = boundary.verify(output["terminal_receipt"], issuer="S2", kind="terminal")
        validate_state(current_state)
        if output["terminal_status"] != terminal["terminal_status"] or terminal["terminal_status"] != "PASS":
            return "BLOCK"
        if output["action_hash"] != terminal["action_hash"] or digest(action) != terminal["action_hash"]:
            return "BLOCK"
        if output["action"] != terminal["action"] or action != terminal["action"]:
            return "BLOCK"
        if output["state_version"] != current_state["version"] or terminal["state_hash"] != digest(current_state):
            return "BLOCK"
        nonce = terminal["action_nonce"]
        if nonce in boundary.consumed_tokens:
            return "NOOP"
        boundary.consumed_tokens.add(nonce)
        return "EXECUTED"
    except (ProtocolError, KeyError, TypeError, ValueError, OverflowError):
        return "BLOCK"


def default_fixture(boundary: TrustedBoundary):
    state = {"version": 7, "balance": 100, "verified_recipients": ["alice"]}
    policy = {"schema_version": 1, "contract_id": "transfer-v1", "max_amount": 80, "allowed_actions": ["transfer"]}
    anchor = {"status": "PASS", "independent": True, "scope": ["goal"], "state_version": 7}
    transition = boundary.make_transition_envelope(
        goal_id="pay-alice",
        state=state,
        policy=policy,
        evidence_root="evidence-root-1",
        previous_receipt_hash="root-receipt-1",
        global_anchor=anchor,
    )
    initial = {"goal_id": "pay-alice", "state_version": 7,
               "action": {"type": "transfer", "recipient": "alice", "amount": 50, "memo": "invoice"}}
    exchanges = [
        {"n2": {"round_id": 0, "decision": "CHALLENGE", "issues": ["amount-check"]},
         "n1_revision": {"goal_id": "pay-alice", "state_version": 7,
                         "action": {"type": "transfer", "recipient": "alice", "amount": 40, "memo": "invoice"}}},
        {"n2": {"round_id": 1, "decision": "CLEAR", "issues": []}},
    ]
    loop = n1_n2_loop(boundary, initial_candidate=initial, exchanges=exchanges, transition_receipt=transition)
    final_review = {"round_id": 99, "decision": "CLEAR", "issues": []}
    final_receipt = final_n2(boundary, loop_result=loop, review=final_review, transition_receipt=transition)
    checkpoint = make_checkpoint(boundary, transition_receipt=transition, loop_result=loop, final_n2_receipt=final_receipt)
    s1 = s1_verify(boundary, checkpoint=checkpoint, transition_receipt=transition, final_n2_receipt=final_receipt,
                   current_state=state, policy=policy)
    s2 = s2_decide(boundary, checkpoint=checkpoint, s1_receipt=s1, current_state=state, policy=policy,
                   action_nonce="action-1")
    output = render_readonly(boundary, terminal_receipt=s2, presentation={"text": "Transfer ready."})
    return {"state": state, "policy": policy, "anchor": anchor, "transition": transition,
            "initial": initial, "exchanges": exchanges, "loop": loop, "final_n2": final_receipt,
            "checkpoint": checkpoint, "s1": s1, "s2": s2, "output": output}
