from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum

from .engine import ClaimType, Directness


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
