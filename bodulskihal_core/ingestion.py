from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from .engine import (
    Claim,
    ClaimType,
    Directness,
    Evidence,
    Policy,
    RiskLevel,
    SourceRole,
    VerificationResult,
    Verdict,
    verify_compound,
)


class TypeAuthority(str, Enum):
    EXECUTOR = "executor"
    TRUSTED_POLICY = "trusted_policy"
    HUMAN = "human"


@dataclass(frozen=True)
class NormalizedResponse:
    text: str
    sha256: str


@dataclass(frozen=True)
class ClaimAtom:
    atom_id: str
    text: str
    start: int
    end: int
    source_response_sha256: str
    claim_type: ClaimType


@dataclass(frozen=True)
class EvidenceContract:
    atom_id: str
    claim_type: ClaimType
    verification_ready: bool
    required_directness: Directness | None
    post_action_required: bool
    independent_post_action_required: bool
    minimum_independent_sources: int
    human_approval_required: bool
    reason: str


@dataclass(frozen=True)
class IngestionResult:
    normalized: NormalizedResponse
    atoms: tuple[ClaimAtom, ...]
    contracts: tuple[EvidenceContract, ...]


@dataclass(frozen=True)
class IngestedVerificationResult:
    ingestion: IngestionResult
    results: tuple[VerificationResult, ...]
    verdict: Verdict


_TYPE_LABEL = re.compile(r"^\[(?P<label>[A-Za-z_]+)\](?:\s+|$)")

_LABEL_TYPES = {
    "INFERENCE": ClaimType.INFERENCE,
    "ESTIMATE": ClaimType.ESTIMATE,
    "ACTION_STATE": ClaimType.ACTION_STATE,
    "RISK_SENSITIVE": ClaimType.RISK_SENSITIVE,
    "OBSERVATION": ClaimType.OBSERVATION,
}


def normalize_model_response(raw: str) -> NormalizedResponse:
    if not isinstance(raw, str):
        raise TypeError("model response must be string")

    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    normalized = unicodedata.normalize("NFC", normalized).strip()
    if not normalized:
        raise ValueError("model response must be non-empty")

    return NormalizedResponse(
        text=normalized,
        sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    )


def type_clause(
    text: str,
    *,
    authority: TypeAuthority = TypeAuthority.EXECUTOR,
) -> ClaimType:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("clause text must be non-empty")

    match = _TYPE_LABEL.match(text)
    if match is None:
        return ClaimType.UNCLASSIFIED

    declared = _LABEL_TYPES.get(match.group("label").upper())
    if declared is None:
        return ClaimType.UNCLASSIFIED

    if (
        declared is ClaimType.OBSERVATION
        and authority is TypeAuthority.EXECUTOR
    ):
        return ClaimType.UNCLASSIFIED

    return declared


def _span_segments(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    length = len(text)
    start = 0

    while start < length:
        while start < length and text[start].isspace():
            start += 1
        if start >= length:
            break

        index = start
        emitted = False
        while index < length:
            char = text[index]

            if char == "\n":
                end = index
                while end > start and text[end - 1].isspace():
                    end -= 1
                if end > start:
                    spans.append((start, end))
                start = index + 1
                emitted = True
                break

            if char in ".?!":
                next_index = index + 1
                if next_index == length or text[next_index].isspace():
                    spans.append((start, next_index))
                    start = next_index
                    emitted = True
                    break

            index += 1

        if not emitted:
            end = length
            while end > start and text[end - 1].isspace():
                end -= 1
            if end > start:
                spans.append((start, end))
            break

    return spans


def atomize_model_response(
    normalized: NormalizedResponse,
    *,
    authority: TypeAuthority = TypeAuthority.EXECUTOR,
) -> tuple[ClaimAtom, ...]:
    if not isinstance(normalized, NormalizedResponse):
        raise TypeError("normalized must be NormalizedResponse")

    atoms = []
    for index, (start, end) in enumerate(_span_segments(normalized.text), start=1):
        text = normalized.text[start:end]
        atoms.append(
            ClaimAtom(
                atom_id=f"atom-{index:04d}",
                text=text,
                start=start,
                end=end,
                source_response_sha256=normalized.sha256,
                claim_type=type_clause(text, authority=authority),
            )
        )

    if not atoms:
        raise ValueError("model response produced no claim atoms")

    return tuple(atoms)


def build_evidence_contract(
    *,
    atom_id: str,
    claim_type: ClaimType,
) -> EvidenceContract:
    if not isinstance(atom_id, str) or not atom_id.strip():
        raise ValueError("atom_id must be non-empty")

    if claim_type is ClaimType.UNCLASSIFIED:
        return EvidenceContract(
            atom_id=atom_id,
            claim_type=claim_type,
            verification_ready=False,
            required_directness=None,
            post_action_required=False,
            independent_post_action_required=False,
            minimum_independent_sources=0,
            human_approval_required=False,
            reason="trusted_typing_required",
        )

    if claim_type is ClaimType.ACTION_STATE:
        return EvidenceContract(
            atom_id=atom_id,
            claim_type=claim_type,
            verification_ready=True,
            required_directness=Directness.DIRECT,
            post_action_required=True,
            independent_post_action_required=True,
            minimum_independent_sources=1,
            human_approval_required=False,
            reason="post_action_final_state_required",
        )

    if claim_type is ClaimType.RISK_SENSITIVE:
        return EvidenceContract(
            atom_id=atom_id,
            claim_type=claim_type,
            verification_ready=True,
            required_directness=Directness.DIRECT,
            post_action_required=False,
            independent_post_action_required=False,
            minimum_independent_sources=1,
            human_approval_required=True,
            reason="human_approval_required",
        )

    if claim_type is ClaimType.OBSERVATION:
        return EvidenceContract(
            atom_id=atom_id,
            claim_type=claim_type,
            verification_ready=True,
            required_directness=Directness.DIRECT,
            post_action_required=False,
            independent_post_action_required=False,
            minimum_independent_sources=1,
            human_approval_required=False,
            reason="direct_evidence_required",
        )

    return EvidenceContract(
        atom_id=atom_id,
        claim_type=claim_type,
        verification_ready=True,
        required_directness=None,
        post_action_required=False,
        independent_post_action_required=False,
        minimum_independent_sources=1,
        human_approval_required=False,
        reason="typed_nonfact_claim",
    )


def ingest_model_response(
    raw: str,
    *,
    authority: TypeAuthority = TypeAuthority.EXECUTOR,
) -> IngestionResult:
    normalized = normalize_model_response(raw)
    atoms = atomize_model_response(normalized, authority=authority)
    contracts = tuple(
        build_evidence_contract(
            atom_id=atom.atom_id,
            claim_type=atom.claim_type,
        )
        for atom in atoms
    )
    return IngestionResult(
        normalized=normalized,
        atoms=atoms,
        contracts=contracts,
    )



_ALLOWED_EVIDENCE_KEYS = {
    "source_id",
    "supports",
    "observed_at",
    "directness",
    "post_action",
    "eligible",
    "evidence_id",
    "source_role",
    "source_ref",
    "content_sha256",
}


def _record_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must be object")
    return value


def _record_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{path} must be non-empty string")
    return value.strip()


def _record_optional_string(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _record_string(value, path)


def _record_bool(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{path} must be bool")
    return value


def _record_datetime(value: Any, path: str) -> datetime:
    raw = _record_string(value, path)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{path} must be ISO 8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{path} must be timezone-aware")
    return parsed


def _record_directness(value: Any, path: str) -> Directness:
    raw = _record_string(value, path)
    try:
        return Directness(raw)
    except ValueError as exc:
        raise ValueError(f"invalid {path}: {raw}") from exc


def _record_source_role(value: Any, path: str) -> SourceRole:
    raw = _record_string(value, path)
    try:
        return SourceRole(raw)
    except ValueError as exc:
        raise ValueError(f"invalid {path}: {raw}") from exc


def collect_normalize_evidence(
    records_by_atom: Mapping[str, list[Mapping[str, Any]]],
    *,
    known_atom_ids: set[str],
) -> dict[str, tuple[Evidence, ...]]:
    if not isinstance(records_by_atom, Mapping):
        raise TypeError("records_by_atom must be object")
    if not isinstance(known_atom_ids, set):
        raise TypeError("known_atom_ids must be set")

    unknown = sorted(set(records_by_atom) - known_atom_ids)
    if unknown:
        raise ValueError("unknown atom_id: " + ", ".join(unknown))

    normalized: dict[str, tuple[Evidence, ...]] = {}
    for atom_id in sorted(known_atom_ids):
        raw_items = records_by_atom.get(atom_id, [])
        if not isinstance(raw_items, list):
            raise TypeError(f"evidence for {atom_id} must be list")

        items: list[Evidence] = []
        seen_evidence_ids: set[str] = set()

        for index, raw in enumerate(raw_items):
            path = f"evidence_by_atom.{atom_id}[{index}]"
            obj = _record_mapping(raw, path)

            extra = sorted(set(obj) - _ALLOWED_EVIDENCE_KEYS)
            if extra:
                raise ValueError(
                    f"{path} contains unsupported fields: " + ", ".join(extra)
                )

            source_id = _record_string(obj.get("source_id"), f"{path}.source_id")
            evidence_id = _record_optional_string(
                obj.get("evidence_id"),
                f"{path}.evidence_id",
            )
            effective_id = evidence_id or source_id
            if effective_id in seen_evidence_ids:
                if evidence_id is None:
                    raise ValueError(
                        f"duplicate source_id for {atom_id}: {source_id}"
                    )
                raise ValueError(
                    f"duplicate evidence_id for {atom_id}: {effective_id}"
                )
            seen_evidence_ids.add(effective_id)

            if "supports" not in obj:
                raise ValueError(f"missing required field: {path}.supports")
            if "observed_at" not in obj:
                raise ValueError(f"missing required field: {path}.observed_at")
            if "directness" not in obj:
                raise ValueError(f"missing required field: {path}.directness")

            items.append(
                Evidence(
                    source_id=source_id,
                    supports=_record_bool(obj["supports"], f"{path}.supports"),
                    observed_at=_record_datetime(
                        obj["observed_at"],
                        f"{path}.observed_at",
                    ),
                    directness=_record_directness(
                        obj["directness"],
                        f"{path}.directness",
                    ),
                    post_action=_record_bool(
                        obj.get("post_action", False),
                        f"{path}.post_action",
                    ),
                    eligible=_record_bool(
                        obj.get("eligible", True),
                        f"{path}.eligible",
                    ),
                    evidence_id=evidence_id,
                    source_role=_record_source_role(
                        obj.get("source_role", SourceRole.EXTERNAL.value),
                        f"{path}.source_role",
                    ),
                    source_ref=_record_optional_string(
                        obj.get("source_ref"),
                        f"{path}.source_ref",
                    ),
                    content_sha256=_record_optional_string(
                        obj.get("content_sha256"),
                        f"{path}.content_sha256",
                    ),
                )
            )

        normalized[atom_id] = tuple(
            sorted(
                items,
                key=lambda item: (
                    item.evidence_id or item.source_id,
                    item.source_id,
                ),
            )
        )

    return normalized


def _claim_from_atom(atom: ClaimAtom) -> Claim:
    risk = (
        RiskLevel.HIGH
        if atom.claim_type is ClaimType.RISK_SENSITIVE
        else RiskLevel.LOW
    )
    return Claim(
        claim_id=atom.atom_id,
        text=atom.text,
        claim_type=atom.claim_type,
        risk=risk,
        consequential=True,
    )


def verify_model_response(
    raw: str,
    *,
    evidence_by_atom: Mapping[str, list[Mapping[str, Any]]],
    authority: TypeAuthority,
    policy: Policy,
    evaluation_time: datetime,
    human_approvals: Mapping[str, bool] | None = None,
) -> IngestedVerificationResult:
    ingestion = ingest_model_response(raw, authority=authority)
    atom_ids = {atom.atom_id for atom in ingestion.atoms}

    evidence = collect_normalize_evidence(
        evidence_by_atom,
        known_atom_ids=atom_ids,
    )

    approvals = human_approvals or {}
    unknown_approvals = sorted(set(approvals) - atom_ids)
    if unknown_approvals:
        raise ValueError(
            "human_approvals contains unknown atom_id: "
            + ", ".join(unknown_approvals)
        )
    for atom_id, value in approvals.items():
        if type(value) is not bool:
            raise TypeError(f"human_approvals.{atom_id} must be bool")

    compound = verify_compound(
        tuple(_claim_from_atom(atom) for atom in ingestion.atoms),
        evidence,
        policy=policy,
        evaluation_time=evaluation_time,
        human_approvals=approvals,
    )

    return IngestedVerificationResult(
        ingestion=ingestion,
        results=compound.results,
        verdict=compound.verdict,
    )
