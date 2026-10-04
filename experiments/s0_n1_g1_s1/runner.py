"""One bounded S0 -> candidate N1 -> deterministic G1 -> receipt S1 cycle.

Run from the repository root: python -m experiments.s0_n1_g1_s1.runner --demo
No network, model integration, application state changes, or second cycle.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import re
import tempfile

from bodulskihal_core.engine import (
    Claim, ClaimType, Classification, Directness, Evidence, EvidenceOrigin,
    Policy, SourceRole, Verdict, verify_claim,
)

EXPERIMENT_VERSION = "0.1.0"
MAX_BYTES = 65536
EXIT_CODES = {"PASS": 0, "BLOCK": 1, "UNKNOWN": 2, "CONFLICT": 3}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _invalid_number(value):
    raise ValueError("nonfinite_json_number")


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite_json_number")
    return result


def read_json(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("input_too_large")
    return json.loads(data, object_pairs_hook=_unique_object,
                      parse_constant=_invalid_number, parse_float=_finite_float)


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError("unexpected_or_missing_fields")


def _name(value):
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value)


def validate_s0(s0):
    """The operator owns S0; candidate output cannot supply or weaken it."""
    _keys(s0, ("schema_version", "max_age_seconds", "predicates"))
    if type(s0["schema_version"]) is not int or s0["schema_version"] != 1:
        raise ValueError("unsupported_schema")
    age = s0["max_age_seconds"]
    if type(age) is not int or not 1 <= age <= 3600:
        raise ValueError("invalid_max_age")
    predicates = s0["predicates"]
    if type(predicates) is not list or not 1 <= len(predicates) <= 16:
        raise ValueError("nonempty_bounded_spec_required")
    ids, pinned = set(), {}
    for predicate in predicates:
        _keys(predicate, ("id", "field", "expected", "sources"))
        if not _name(predicate["id"]) or predicate["id"] in ids:
            raise ValueError("invalid_or_duplicate_predicate_id")
        ids.add(predicate["id"])
        if not _name(predicate["field"]):
            raise ValueError("invalid_field")
        if type(predicate["expected"]) not in (str, int, bool, type(None)):
            raise ValueError("expected_must_be_json_scalar_without_float")
        sources = predicate["sources"]
        if type(sources) is not list or not 1 <= len(sources) <= 8:
            raise ValueError("nonempty_bounded_sources_required")
        seen = set()
        for source in sources:
            _keys(source, ("path", "sha256"))
            path = source["path"]
            if type(path) is not str or not path or len(path) > 240 or "\x00" in path:
                raise ValueError("invalid_source_path")
            if path in seen:
                raise ValueError("duplicate_source")
            seen.add(path)
            sha = source["sha256"]
            if type(sha) is not str or not re.fullmatch(r"[a-f0-9]{64}", sha):
                raise ValueError("invalid_snapshot_hash")
            if path in pinned and pinned[path] != sha:
                raise ValueError("inconsistent_snapshot_hash")
            pinned[path] = sha
    return s0


def n1(s0):
    """Candidate-only stub: nondeterministic ordering, no authority or I/O.

    An external candidate JSON can replace this stub through --candidate.
    This is NOT a tested LLM/BodulLogic integration.
    """
    validate_s0(s0)
    ids = [p["id"] for p in s0["predicates"]]
    random.SystemRandom().shuffle(ids)
    return {"s0_sha256": digest(s0), "predicate_ids": ids}


def _source_path(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("source_outside_root")
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("source_outside_root")
    return path


def _snapshot(path):
    before = path.stat()
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    after = path.stat()
    signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if signature(before) != signature(after):
        raise ValueError("source_changed_during_read")
    if len(raw) > MAX_BYTES:
        raise ValueError("source_too_large")
    return raw, signature(after)


def _timestamp(value):
    if type(value) is not str:
        raise ValueError("invalid_observed_at")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("observed_at_requires_timezone")
    return result


def _finish(status, reason, *, s0_hash=None, candidate_hash=None, checks=None, now=None):
    checks = checks or []
    facts = [{"predicate_id": c["id"], "field": c["field"],
              "expected": c["expected"], "source_sha256": c["source_sha256"],
              "classification": "FACT"} for c in checks] if status == "PASS" else []
    receipt = {
        "experiment_version": EXPERIMENT_VERSION, "status": status,
        "approved": status == "PASS", "reason": reason,
        "s0_sha256": s0_hash, "candidate_sha256": candidate_hash,
        "evaluated_at": now.isoformat() if now else None,
        "scope": "pinned_local_json_field_equalities_only",
        "checks": checks,
    }
    receipt["sha256"] = digest(receipt)
    return {"state": {"facts": facts, "s0_sha256": s0_hash} if status == "PASS" else None,
            "receipt": receipt}


def g1(s0, candidate, root, *, clock=None):
    """Collect evidence ourselves; N1 cannot supply supports/FACT/evidence flags.

    clock is a trusted test seam; CLI always uses the real UTC clock.
    Hash pinning + two reads signal common TOCTOU changes, not atomicity/ABA.
    """
    clock = clock or (lambda: datetime.now(timezone.utc))
    try:
        # Freeze caller-owned objects before collection and bind the exact contract.
        s0 = json.loads(canonical(s0))
        candidate = json.loads(canonical(candidate))
        validate_s0(s0)
        _keys(candidate, ("s0_sha256", "predicate_ids"))
        ids = candidate["predicate_ids"]
        expected_ids = [p["id"] for p in s0["predicates"]]
        if (type(ids) is not list or any(type(i) is not str for i in ids)
                or sorted(ids) != sorted(expected_ids)
                or candidate["s0_sha256"] != digest(s0)):
            raise ValueError("candidate_contract_mismatch")
        root = Path(root).resolve(strict=True)
        # Validate paths before reading any evidence.
        paths = {s["path"]: _source_path(root, s["path"])
                 for p in s0["predicates"] for s in p["sources"]}
    except (ValueError, TypeError, OSError, OverflowError, RecursionError):
        return _finish("BLOCK", "invalid_s0_or_candidate_or_root")

    s0_hash, candidate_hash = digest(s0), digest(candidate)
    snapshots, errors = {}, {}
    for name, path in paths.items():
        try:
            raw, signature = _snapshot(path)
            data = json.loads(raw, object_pairs_hook=_unique_object,
                              parse_constant=_invalid_number, parse_float=_finite_float)
            _keys(data, ("observed_at", "values"))
            if type(data["values"]) is not dict:
                raise ValueError("invalid_values")
            observed_at = _timestamp(data["observed_at"])
            snapshots[name] = (raw, signature, data, observed_at)
        except (ValueError, TypeError, OSError, OverflowError, RecursionError):
            errors[name] = "missing_or_invalid_evidence"

    # Second collection closes the obvious read/evaluate race, without claiming
    # a filesystem transaction. Re-resolve paths to detect symlink retargeting.
    for name, snapshot in snapshots.items():
        try:
            path = _source_path(root, name)
            raw, signature = _snapshot(path)
            if path != paths[name] or (raw, signature) != snapshot[:2]:
                errors[name] = "toctou_source_changed"
        except (ValueError, OSError):
            errors[name] = "toctou_source_unavailable"

    now = clock()
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        return _finish("UNKNOWN", "invalid_verifier_clock", s0_hash=s0_hash,
                       candidate_hash=candidate_hash)
    checks = []
    for predicate in sorted(s0["predicates"], key=lambda p: p["id"]):
        evidence, issues, hashes = [], [], []
        for index, source in enumerate(predicate["sources"]):
            name = source["path"]
            if name in errors:
                issues.append({"source": name, "reason": errors[name]})
                continue
            raw, _, data, observed_at = snapshots[name]
            actual_hash = hashlib.sha256(raw).hexdigest()
            age = (now - observed_at).total_seconds()
            issue = None
            if actual_hash != source["sha256"]:
                issue = "snapshot_hash_mismatch"
            elif not 0 <= age <= s0["max_age_seconds"]:
                issue = "stale_or_future_evidence"
            elif predicate["field"] not in data["values"]:
                issue = "missing_evidence_field"
            if issue:
                issues.append({"source": name, "reason": issue})
                continue
            hashes.append(actual_hash)
            supports = canonical(data["values"][predicate["field"]]) == canonical(predicate["expected"])
            evidence.append(Evidence(
                source_id=name, evidence_id=str(index), source_ref=paths[name].as_uri(),
                supports=supports, observed_at=observed_at, directness=Directness.DIRECT,
                source_role=SourceRole.VERIFIER, origin=EvidenceOrigin.TOOL_OBSERVATION,
                content_sha256=actual_hash,
            ))
        result = verify_claim(
            Claim(predicate["id"], f"Pinned JSON field {predicate['field']} equals "
                  f"{canonical(predicate['expected']).decode()}", ClaimType.OBSERVATION),
            evidence, policy=Policy(version="experiment-0.1.0", max_age_seconds=s0["max_age_seconds"]),
            evaluation_time=now,
        )
        if result.classification is Classification.CONFLICT:
            status = "CONFLICT"
        elif result.classification is Classification.REFUTED:
            status = "BLOCK"
        elif issues or result.verdict is not Verdict.APPROVE:
            status = "UNKNOWN"
        else:
            status = "PASS"
        checks.append({"id": predicate["id"], "field": predicate["field"],
                       "expected": predicate["expected"], "status": status,
                       "issues": issues, "source_sha256": hashes,
                       "core_receipt": result.receipt})
    status = next((s for s in ("CONFLICT", "BLOCK", "UNKNOWN")
                   if any(c["status"] == s for c in checks)), "PASS")
    return _finish(status, "all_predicates_satisfied" if status == "PASS" else "gate_not_satisfied",
                   s0_hash=s0_hash, candidate_hash=candidate_hash, checks=checks, now=now)


def run(s0, root, candidate=None):
    try:
        candidate = n1(s0) if candidate is None else candidate
    except (ValueError, TypeError):
        return _finish("BLOCK", "invalid_s0")
    return g1(s0, candidate, root)


def demo():
    """Fresh synthetic local evidence; demonstrates the cycle, not external truth."""
    with tempfile.TemporaryDirectory(prefix="bodulhal-cycle-") as temp:
        path = Path(temp) / "observation.json"
        raw = canonical({"observed_at": datetime.now(timezone.utc).isoformat(),
                         "values": {"answer": 42, "units": "items"}})
        path.write_bytes(raw)
        source = {"path": path.name, "sha256": hashlib.sha256(raw).hexdigest()}
        s0 = {"schema_version": 1, "max_age_seconds": 60, "predicates": [
            {"id": "answer", "field": "answer", "expected": 42, "sources": [source]},
            {"id": "units", "field": "units", "expected": "items", "sources": [source]},
        ]}
        return run(s0, temp)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--s0", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    if args.demo and (args.s0 or args.candidate) or not args.demo and not args.s0:
        parser.error("use --demo OR --s0 FILE [--candidate FILE] [--root DIR]")
    try:
        output = demo() if args.demo else run(
            read_json(args.s0), args.root, read_json(args.candidate) if args.candidate else None)
    except (ValueError, TypeError, OSError, OverflowError, RecursionError):
        output = _finish("BLOCK", "invalid_or_unreadable_input")
    print(json.dumps(output, ensure_ascii=True, sort_keys=True, indent=2))
    return EXIT_CODES[output["receipt"]["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
