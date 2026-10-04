"""Prototype for the exact grouped architecture:

    N1 <-> N2 -> N2(final) -> C -> S1 -> S2 -> N1(read-only) -> OUTPUT

This is an isolated deterministic testbed for trust-boundary behavior. It does
not call a model or claim real-world correctness. Untrusted N1/N2 data are
bound into receipts by a tiny HMAC-based in-process boundary; the HMAC is a
prototype provenance mechanism, not production key management.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
from typing import Any

VERSION = "0.1.8"
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


@dataclass(frozen=True)
class FileNonceLedger:
    """Trusted local at-most-once nonce ledger with cross-process persistence.

    Exclusive file creation makes consumption atomic on one trusted filesystem.
    It is not a distributed transaction and cannot by itself guarantee that an
    external side effect and nonce consumption commit atomically.
    """

    root: Path | str

    def __post_init__(self) -> None:
        path = Path(self.root)
        try:
            path.mkdir(parents=True, exist_ok=True)
            path = path.resolve(strict=True)
        except OSError as exc:
            raise ProtocolError("ledger_unavailable") from exc
        if not path.is_dir():
            raise ProtocolError("ledger_not_directory")
        object.__setattr__(self, "root", path)

    def consume(self, nonce: str) -> bool:
        if not _name(nonce):
            raise ProtocolError("invalid_execution_token")
        name = hashlib.sha256(nonce.encode("utf-8")).hexdigest() + ".nonce"
        path = self.root / name
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            return False
        except OSError as exc:
            raise ProtocolError("ledger_unavailable") from exc
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(b"consumed\n")
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            raise ProtocolError("ledger_write_failed") from exc
        return True


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


def issue_global_anchor(anchor_secret: bytes, anchor: dict[str, Any]) -> dict[str, Any]:
    """Model a separate global-goal authority with a distinct trust root."""
    if type(anchor_secret) is not bytes or not anchor_secret:
        raise ProtocolError("invalid_anchor_secret")
    validate_anchor(anchor)
    body = {
        "v": VERSION,
        "issuer": "GLOBAL-ANCHOR",
        "kind": "goal",
        "payload": deepcopy(anchor),
    }
    mac = hmac.new(anchor_secret, canonical(body), hashlib.sha256).hexdigest()
    return {**body, "mac": mac}


def issue_evidence_root(
    evidence_secret: bytes,
    *,
    evidence_root: str,
    state_version: int,
    contract_hash: str,
) -> dict[str, Any]:
    """Model a separate evidence authority over the root used by S1."""
    if type(evidence_secret) is not bytes or not evidence_secret:
        raise ProtocolError("invalid_evidence_secret")
    if not _name(evidence_root):
        raise ProtocolError("invalid_evidence_root")
    if type(state_version) is not int or state_version < 0:
        raise ProtocolError("invalid_evidence_state_version")
    if type(contract_hash) is not str or re.fullmatch(r"[a-f0-9]{64}", contract_hash) is None:
        raise ProtocolError("invalid_evidence_contract_hash")
    payload = {
        "evidence_root": evidence_root,
        "state_version": state_version,
        "contract_hash": contract_hash,
    }
    body = {
        "v": VERSION,
        "issuer": "EVIDENCE-AUTHORITY",
        "kind": "root",
        "payload": payload,
    }
    mac = hmac.new(evidence_secret, canonical(body), hashlib.sha256).hexdigest()
    return {**body, "mac": mac}


@dataclass
class TrustedBoundary:
    secret: bytes
    anchor_secret: bytes
    evidence_secret: bytes

    def __post_init__(self) -> None:
        if type(self.secret) is not bytes or not self.secret:
            raise ProtocolError("invalid_boundary_secret")
        if type(self.anchor_secret) is not bytes or not self.anchor_secret:
            raise ProtocolError("invalid_anchor_secret")
        if type(self.evidence_secret) is not bytes or not self.evidence_secret:
            raise ProtocolError("invalid_evidence_secret")

    def _mac(self, body: dict[str, Any]) -> str:
        return hmac.new(self.secret, canonical(body), hashlib.sha256).hexdigest()

    def verify_global_anchor(self, receipt: Any) -> dict[str, Any]:
        _strict_keys(receipt, ("v", "issuer", "kind", "payload", "mac"))
        if (
            receipt["v"] != VERSION
            or receipt["issuer"] != "GLOBAL-ANCHOR"
            or receipt["kind"] != "goal"
            or type(receipt["mac"]) is not str
        ):
            raise ProtocolError("invalid_anchor_receipt")
        body = {k: deepcopy(receipt[k]) for k in ("v", "issuer", "kind", "payload")}
        expected = hmac.new(self.anchor_secret, canonical(body), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(receipt["mac"], expected):
            raise ProtocolError("anchor_receipt_mac_mismatch")
        validate_anchor(receipt["payload"])
        return deepcopy(receipt["payload"])

    def verify_evidence_root(self, receipt: Any) -> dict[str, Any]:
        _strict_keys(receipt, ("v", "issuer", "kind", "payload", "mac"))
        if (
            receipt["v"] != VERSION
            or receipt["issuer"] != "EVIDENCE-AUTHORITY"
            or receipt["kind"] != "root"
            or type(receipt["mac"]) is not str
        ):
            raise ProtocolError("invalid_evidence_receipt")
        body = {k: deepcopy(receipt[k]) for k in ("v", "issuer", "kind", "payload")}
        expected = hmac.new(self.evidence_secret, canonical(body), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(receipt["mac"], expected):
            raise ProtocolError("evidence_receipt_mac_mismatch")
        payload = receipt["payload"]
        _strict_keys(payload, ("evidence_root", "state_version", "contract_hash"))
        if not _name(payload["evidence_root"]):
            raise ProtocolError("invalid_evidence_root")
        if type(payload["state_version"]) is not int or payload["state_version"] < 0:
            raise ProtocolError("invalid_evidence_state_version")
        if type(payload["contract_hash"]) is not str or re.fullmatch(r"[a-f0-9]{64}", payload["contract_hash"]) is None:
            raise ProtocolError("invalid_evidence_contract_hash")
        return deepcopy(payload)

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
        global_anchor_receipt: dict[str, Any] | None = None,
        evidence_receipt: dict[str, Any] | None = None,
        phase_id: str = "group3",
    ) -> dict[str, Any]:
        validate_state(state)
        validate_policy(policy)
        validate_anchor(global_anchor)
        if global_anchor["goal_id"] != goal_id or global_anchor["contract_hash"] != digest(policy):
            raise ProtocolError("anchor_context_mismatch")
        anchor_verified = False
        if global_anchor_receipt is not None:
            verified_anchor = self.verify_global_anchor(global_anchor_receipt)
            if verified_anchor != global_anchor:
                raise ProtocolError("anchor_payload_mismatch")
            anchor_verified = True
        evidence_verified = False
        if evidence_receipt is not None:
            verified_evidence = self.verify_evidence_root(evidence_receipt)
            expected_evidence = {
                "evidence_root": evidence_root,
                "state_version": state["version"],
                "contract_hash": digest(policy),
            }
            if verified_evidence != expected_evidence:
                raise ProtocolError("evidence_payload_mismatch")
            evidence_verified = True
        if not all(_name(x) for x in (goal_id, evidence_root, previous_receipt_hash, phase_id)):
            raise ProtocolError("invalid_transition_identity")
        payload = {
            "goal_id": goal_id,
            "contract_hash": digest(policy),
            "schema_version": policy["schema_version"],
            "state_hash": digest(state),
            "state_version": state["version"],
            "evidence_root": evidence_root,
            "evidence_verified": evidence_verified,
            "evidence_receipt": deepcopy(evidence_receipt),
            "evidence_receipt_hash": digest(evidence_receipt) if evidence_receipt is not None else None,
            "previous_receipt_hash": previous_receipt_hash,
            "phase_id": phase_id,
            "global_anchor": deepcopy(global_anchor),
            "global_anchor_verified": anchor_verified,
            "global_anchor_receipt": deepcopy(global_anchor_receipt),
            "global_anchor_receipt_hash": digest(global_anchor_receipt) if global_anchor_receipt is not None else None,
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
    _strict_keys(anchor, ("status", "independent", "scope", "state_version", "goal_id", "contract_hash"))
    if anchor["status"] not in ("PASS", "UNKNOWN", "CONFLICT"):
        raise ProtocolError("invalid_anchor_status")
    if type(anchor["independent"]) is not bool:
        raise ProtocolError("invalid_anchor_independence")
    if type(anchor["scope"]) is not list or any(not _name(x) for x in anchor["scope"]):
        raise ProtocolError("invalid_anchor_scope")
    if type(anchor["state_version"]) is not int or anchor["state_version"] < 0:
        raise ProtocolError("invalid_anchor_state_version")
    if not _name(anchor["goal_id"]):
        raise ProtocolError("invalid_anchor_goal")
    if type(anchor["contract_hash"]) is not str or re.fullmatch(r"[a-f0-9]{64}", anchor["contract_hash"]) is None:
        raise ProtocolError("invalid_anchor_contract_hash")


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
    loop_root = digest([digest(r) for r in receipts])
    loop_receipt = boundary.issue(
        issuer="LOOP",
        kind="result",
        payload={
            "transition_hash": digest(transition_receipt),
            "candidate_hash": digest(candidate),
            "loop_status": loop_status,
            "loop_root": loop_root,
            "receipt_count": len(receipts),
        },
    )
    return {
        "candidate": candidate,
        "receipts": receipts,
        "loop_status": loop_status,
        "loop_root": loop_root,
        "loop_receipt": loop_receipt,
    }


def _verify_loop_result(
    boundary: TrustedBoundary,
    *,
    loop_result: dict[str, Any],
    transition_receipt: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _strict_keys(loop_result, ("candidate", "receipts", "loop_status", "loop_root", "loop_receipt"))
    transition = boundary.verify(transition_receipt, issuer="S-boundary", kind="transition")
    receipt = boundary.verify(loop_result["loop_receipt"], issuer="LOOP", kind="result")
    candidate = deepcopy(loop_result["candidate"])
    validate_candidate(candidate)
    if loop_result["loop_status"] not in ("PASS", "UNKNOWN", "CONFLICT"):
        raise ProtocolError("invalid_loop_status")
    recomputed_root = digest([digest(item) for item in loop_result["receipts"]])
    checks = (
        receipt["transition_hash"] == digest(transition_receipt),
        receipt["candidate_hash"] == digest(candidate),
        receipt["loop_status"] == loop_result["loop_status"],
        receipt["loop_root"] == loop_result["loop_root"] == recomputed_root,
        receipt["receipt_count"] == len(loop_result["receipts"]),
        candidate["goal_id"] == transition["goal_id"],
        candidate["state_version"] == transition["state_version"],
    )
    if not all(checks):
        raise ProtocolError("loop_receipt_mismatch")
    return transition, receipt


def final_n2(boundary: TrustedBoundary, *, loop_result: dict[str, Any], review: dict[str, Any], transition_receipt: dict[str, Any]) -> dict[str, Any]:
    transition, loop_receipt = _verify_loop_result(
        boundary, loop_result=loop_result, transition_receipt=transition_receipt
    )
    candidate = deepcopy(loop_result["candidate"])
    validate_n2_review(review)
    parent = digest(loop_result["loop_receipt"])
    receipt = seal_n2_review(boundary, candidate=candidate, review=review, parent_hash=parent)
    payload = boundary.verify(receipt, issuer="N2", kind="review")
    if (
        payload["candidate_hash"] != digest(candidate)
        or payload["parent_hash"] != digest(loop_result["loop_receipt"])
        or candidate["goal_id"] != transition["goal_id"]
    ):
        raise ProtocolError("final_n2_binding_mismatch")
    return receipt


def make_checkpoint(
    boundary: TrustedBoundary,
    *,
    transition_receipt: dict[str, Any],
    loop_result: dict[str, Any],
    final_n2_receipt: dict[str, Any],
) -> dict[str, Any]:
    transition, loop_receipt = _verify_loop_result(
        boundary, loop_result=loop_result, transition_receipt=transition_receipt
    )
    candidate = deepcopy(loop_result["candidate"])
    n2 = boundary.verify(final_n2_receipt, issuer="N2", kind="review")
    if (
        n2["candidate_hash"] != digest(candidate)
        or n2["parent_hash"] != digest(loop_result["loop_receipt"])
    ):
        raise ProtocolError("final_review_wrong_candidate_or_loop")
    payload = {
        "transition_hash": digest(transition_receipt),
        "goal_id": transition["goal_id"],
        "contract_hash": transition["contract_hash"],
        "state_hash": transition["state_hash"],
        "state_version": transition["state_version"],
        "evidence_root": transition["evidence_root"],
        "evidence_verified": transition["evidence_verified"],
        "evidence_receipt": deepcopy(transition["evidence_receipt"]),
        "evidence_receipt_hash": transition["evidence_receipt_hash"],
        "candidate": candidate,
        "candidate_hash": digest(candidate),
        "loop_status": loop_result["loop_status"],
        "loop_root": loop_result["loop_root"],
        "loop_receipt": deepcopy(loop_result["loop_receipt"]),
        "loop_receipt_hash": digest(loop_result["loop_receipt"]),
        "final_n2_receipt_hash": digest(final_n2_receipt),
        "final_n2_decision": n2["decision"],
        "final_n2_issues": list(n2["issues"]),
        "global_anchor": deepcopy(transition["global_anchor"]),
        "global_anchor_verified": transition["global_anchor_verified"],
        "global_anchor_receipt": deepcopy(transition["global_anchor_receipt"]),
        "global_anchor_receipt_hash": transition["global_anchor_receipt_hash"],
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
        loop_receipt = boundary.verify(cp["loop_receipt"], issuer="LOOP", kind="result")
        validate_state(current_state)
        validate_policy(policy)
        validate_candidate(cp["candidate"])
        if cp["evidence_verified"]:
            evidence_payload = boundary.verify_evidence_root(cp["evidence_receipt"])
            evidence_integrity = (
                evidence_payload["evidence_root"] == cp["evidence_root"]
                and evidence_payload["state_version"] == cp["state_version"]
                and evidence_payload["contract_hash"] == cp["contract_hash"]
                and cp["evidence_receipt_hash"] == digest(cp["evidence_receipt"])
            )
        else:
            evidence_integrity = (
                cp["evidence_receipt"] is None
                and cp["evidence_receipt_hash"] is None
            )
        if cp["global_anchor_verified"]:
            anchor_payload = boundary.verify_global_anchor(cp["global_anchor_receipt"])
            anchor_integrity = (
                anchor_payload == cp["global_anchor"]
                and cp["global_anchor_receipt_hash"] == digest(cp["global_anchor_receipt"])
            )
        else:
            anchor_integrity = (
                cp["global_anchor_receipt"] is None
                and cp["global_anchor_receipt_hash"] is None
            )
        checks = {
            "transition_hash": cp["transition_hash"] == digest(transition_receipt),
            "goal": cp["goal_id"] == tr["goal_id"] == cp["candidate"]["goal_id"],
            "contract": cp["contract_hash"] == digest(policy) == tr["contract_hash"],
            "state_hash": cp["state_hash"] == digest(current_state) == tr["state_hash"],
            "state_version": cp["state_version"] == current_state["version"] == tr["state_version"] == cp["candidate"]["state_version"],
            "candidate_hash": cp["candidate_hash"] == digest(cp["candidate"]) == n2["candidate_hash"],
            "loop_receipt": (
                cp["loop_receipt_hash"] == digest(cp["loop_receipt"])
                and loop_receipt["transition_hash"] == cp["transition_hash"]
                and loop_receipt["candidate_hash"] == cp["candidate_hash"]
                and loop_receipt["loop_status"] == cp["loop_status"]
                and loop_receipt["loop_root"] == cp["loop_root"]
                and n2["parent_hash"] == digest(cp["loop_receipt"])
            ),
            "n2_receipt": cp["final_n2_receipt_hash"] == digest(final_n2_receipt),
            "evidence_receipt": evidence_integrity,
            "global_anchor_receipt": anchor_integrity,
        }
        if not all(checks.values()):
            status = "BLOCK"
        elif not cp["evidence_verified"]:
            status = "UNKNOWN"
        else:
            status = "PASS"
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


def _global_status(
    anchor: dict[str, Any],
    state_version: int,
    *,
    provenance_verified: bool,
    goal_id: str,
    contract_hash: str,
) -> str:
    validate_anchor(anchor)
    if not provenance_verified:
        return "UNKNOWN"
    if anchor["status"] == "CONFLICT":
        return "CONFLICT"
    if (
        not anchor["independent"]
        or "goal" not in anchor["scope"]
        or anchor["state_version"] != state_version
        or anchor["goal_id"] != goal_id
        or anchor["contract_hash"] != contract_hash
    ):
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


def _execution_token(goal_id: str) -> str:
    if not _name(goal_id):
        raise ProtocolError("invalid_goal_id")
    # Stable idempotency identity: re-certifying the same trusted goal must not
    # mint a fresh execution token. A genuinely new intended operation must
    # use a distinct goal_id at the trusted transition boundary.
    return digest({"kind": "goal-execution", "goal_id": goal_id})


def s2_decide(
    boundary: TrustedBoundary,
    *,
    checkpoint: dict[str, Any],
    s1_receipt: dict[str, Any],
    current_state: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    try:
        cp = boundary.verify(checkpoint, issuer="C", kind="checkpoint")
        s1 = boundary.verify(s1_receipt, issuer="S1", kind="integrity")
        validate_state(current_state)
        validate_policy(policy)
        if s1["checkpoint_hash"] != digest(checkpoint):
            raise ProtocolError("s1_wrong_checkpoint")
        integrity = s1["status"]
        loop_status = cp["loop_status"]
        if loop_status not in ("PASS", "UNKNOWN", "CONFLICT"):
            raise ProtocolError("invalid_loop_status")
        final_n2_status = _n2_decision_status(cp["final_n2_decision"])
        contract = _contract_status(cp["candidate"], current_state, policy)
        provenance_verified = False
        if cp["global_anchor_verified"]:
            anchor_payload = boundary.verify_global_anchor(cp["global_anchor_receipt"])
            provenance_verified = (
                anchor_payload == cp["global_anchor"]
                and cp["global_anchor_receipt_hash"] == digest(cp["global_anchor_receipt"])
            )
        global_status = _global_status(
            cp["global_anchor"],
            current_state["version"],
            provenance_verified=provenance_verified,
            goal_id=cp["goal_id"],
            contract_hash=digest(policy),
        )
        terminal = worst_status(integrity, loop_status, final_n2_status, contract, global_status)
        execution_token = _execution_token(cp["goal_id"])
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
            "execution_token": execution_token,
            "epistemic_scope": "authenticated_inputs_and_declared_requirements_only",
            "global_truth_certified": False,
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
            "execution_token": None,
            "epistemic_scope": "authenticated_inputs_and_declared_requirements_only",
            "global_truth_certified": False,
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
        "epistemic_scope": terminal["epistemic_scope"],
        "global_truth_certified": terminal["global_truth_certified"],
        "explanation": presentation["text"],
    }


def execute(
    boundary: TrustedBoundary,
    *,
    output: dict[str, Any],
    current_state: dict[str, Any],
    current_policy: dict[str, Any],
    action: dict[str, Any],
    nonce_ledger: FileNonceLedger,
) -> str:
    try:
        _strict_keys(output, ("terminal_status", "action", "action_hash", "state_version", "terminal_receipt", "epistemic_scope", "global_truth_certified", "explanation"))
        terminal = boundary.verify(output["terminal_receipt"], issuer="S2", kind="terminal")
        if (
            output["epistemic_scope"] != terminal["epistemic_scope"]
            or output["global_truth_certified"] is not terminal["global_truth_certified"]
            or terminal["epistemic_scope"] != "authenticated_inputs_and_declared_requirements_only"
            or terminal["global_truth_certified"] is not False
        ):
            return "BLOCK"
        validate_state(current_state)
        validate_policy(current_policy)
        if not isinstance(nonce_ledger, FileNonceLedger):
            return "BLOCK"
        if output["terminal_status"] != terminal["terminal_status"] or terminal["terminal_status"] != "PASS":
            return "BLOCK"
        if (
            output["epistemic_scope"] != terminal["epistemic_scope"]
            or terminal["epistemic_scope"] != "authenticated_inputs_and_declared_requirements_only"
            or output["global_truth_certified"] is not terminal["global_truth_certified"]
            or terminal["global_truth_certified"] is not False
        ):
            return "BLOCK"
        if output["action_hash"] != terminal["action_hash"] or digest(action) != terminal["action_hash"]:
            return "BLOCK"
        if output["action"] != terminal["action"] or action != terminal["action"]:
            return "BLOCK"
        if output["state_version"] != current_state["version"] or terminal["state_hash"] != digest(current_state):
            return "BLOCK"
        if terminal["contract_hash"] != digest(current_policy):
            return "BLOCK"
        if _contract_status({"action": action}, current_state, current_policy) != "PASS":
            return "BLOCK"
        execution_token = terminal["execution_token"]
        if not nonce_ledger.consume(execution_token):
            return "NOOP"
        return "EXECUTED"
    except (ProtocolError, KeyError, TypeError, ValueError, OverflowError, OSError):
        return "BLOCK"


def default_fixture(boundary: TrustedBoundary):
    state = {"version": 7, "balance": 100, "verified_recipients": ["alice"]}
    policy = {"schema_version": 1, "contract_id": "transfer-v1", "max_amount": 80, "allowed_actions": ["transfer"]}
    anchor = {
        "status": "PASS", "independent": True, "scope": ["goal"], "state_version": 7,
        "goal_id": "pay-alice", "contract_hash": digest(policy),
    }
    anchor_receipt = issue_global_anchor(boundary.anchor_secret, anchor)
    evidence_root = "evidence-root-1"
    evidence_receipt = issue_evidence_root(
        boundary.evidence_secret,
        evidence_root=evidence_root,
        state_version=state["version"],
        contract_hash=digest(policy),
    )
    transition = boundary.make_transition_envelope(
        goal_id="pay-alice",
        state=state,
        policy=policy,
        evidence_root=evidence_root,
        previous_receipt_hash="root-receipt-1",
        global_anchor=anchor,
        global_anchor_receipt=anchor_receipt,
        evidence_receipt=evidence_receipt,
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
)
    output = render_readonly(boundary, terminal_receipt=s2, presentation={"text": "Transfer ready."})
    return {"state": state, "policy": policy, "anchor": anchor, "transition": transition,
            "initial": initial, "exchanges": exchanges, "loop": loop, "final_n2": final_receipt,
            "checkpoint": checkpoint, "s1": s1, "s2": s2, "output": output}
