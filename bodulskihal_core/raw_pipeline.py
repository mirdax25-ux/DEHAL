from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum

from .engine import ClaimType, Directness


class SpeakerRole(str, Enum):
    ASSISTANT = "assistant"
    USER = "user"
    TOOL = "tool"
    UNKNOWN = "unknown"


class AtomStatus(str, Enum):
    READY = "ready"
    REVIEW_REQUIRED = "review_required"


class ClauseTypeStatus(str, Enum):
    TYPED = "typed"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True)
class RawResponseEnvelope:
    response_id: str
    text: str
    speaker_role: SpeakerRole
    raw_sha256: str

    @classmethod
    def create(
        cls,
        response_id: str,
        text: str,
        speaker_role: SpeakerRole,
    ) -> "RawResponseEnvelope":
        if not isinstance(response_id, str) or not response_id.strip():
            raise ValueError("response_id must be non-empty")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be non-empty")
        if not isinstance(speaker_role, SpeakerRole):
            raise TypeError("speaker_role must be SpeakerRole")

        return cls(
            response_id=response_id.strip(),
            text=text,
            speaker_role=speaker_role,
            raw_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )


@dataclass(frozen=True)
class ClaimAtom:
    atom_id: str
    response_id: str
    start: int
    end: int
    source_text: str
    status: AtomStatus
    review_reasons: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceContract:
    atom_id: str
    claim_type: ClaimType
    required_directness: Directness
    requires_post_action: bool
    requires_human_review: bool
    fact_eligible: bool
    review_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ClauseTypeDecision:
    atom_id: str
    claim_type: ClaimType | None
    status: ClauseTypeStatus
    reasons: tuple[str, ...]
    rule: str


@dataclass(frozen=True)
class SpanProposal:
    atom_id: str
    start: int
    end: int
    quoted_text: str


_COMPOUND_CUES = re.compile(
    r"\b(and|or|nor|but|while|although|however|whereas|because)\b",
    re.IGNORECASE,
)

_EPISTEMIC_QUALIFIERS = re.compile(
    r"\b(may|might|could|probably|likely|possibly|perhaps|appears?|seems?)\b",
    re.IGNORECASE,
)

_CONDITIONAL_CUES = re.compile(
    r"\b(if|unless|provided|assuming)\b",
    re.IGNORECASE,
)

_ACTION_STATE_CUES = re.compile(
    r"\b(completed|complete|finished|sent|submitted|deployed|merged|published|"
    r"uploaded|downloaded|installed|deleted|created|updated|saved|executed|"
    r"started|stopped|closed|opened|approved|rejected)\b",
    re.IGNORECASE,
)

_ESTIMATE_CUES = re.compile(
    r"\b(estimate|estimated|approximately|approximate|roughly)\b",
    re.IGNORECASE,
)

_ABBREVIATIONS = {
    "dr.",
    "mr.",
    "mrs.",
    "ms.",
    "prof.",
    "sr.",
    "jr.",
    "st.",
}

_AMBIGUOUS_REFERENT = re.compile(
    r"^(it|this|that|they|these|those|he|she)\b",
    re.IGNORECASE,
)


def _review_reasons(source_text: str) -> tuple[str, ...]:
    reasons: list[str] = []
    stripped = source_text.strip()

    if _COMPOUND_CUES.search(stripped) or ";" in stripped:
        reasons.append("compound_clause")

    if _EPISTEMIC_QUALIFIERS.search(stripped):
        reasons.append("epistemic_qualifier")

    if _CONDITIONAL_CUES.search(stripped):
        reasons.append("conditional_clause")

    if _AMBIGUOUS_REFERENT.search(stripped):
        reasons.append("ambiguous_referent")

    return tuple(reasons)


def bind_atom(
    envelope: RawResponseEnvelope,
    *,
    atom_id: str,
    start: int,
    end: int,
    proposed_text: str | None = None,
) -> ClaimAtom:
    if not isinstance(atom_id, str) or not atom_id.strip():
        raise ValueError("atom_id must be non-empty")
    if not isinstance(start, int) or not isinstance(end, int):
        raise TypeError("span offsets must be integers")
    if start < 0 or end > len(envelope.text) or start >= end:
        raise ValueError("invalid source span")

    source_text = envelope.text[start:end]
    if not source_text.strip():
        raise ValueError("source span must contain non-whitespace text")

    if proposed_text is not None and proposed_text != source_text:
        raise ValueError("proposed text must exactly match source span")

    reasons = _review_reasons(source_text)
    status = AtomStatus.REVIEW_REQUIRED if reasons else AtomStatus.READY

    return ClaimAtom(
        atom_id=atom_id.strip(),
        response_id=envelope.response_id,
        start=start,
        end=end,
        source_text=source_text,
        status=status,
        review_reasons=reasons,
    )


def _is_abbreviation_period(text: str, index: int) -> bool:
    if text[index] != "." or index + 1 >= len(text):
        return False

    word_start = index - 1
    while word_start >= 0 and text[word_start].isalpha():
        word_start -= 1
    token = text[word_start + 1:index + 1].lower()

    is_initial = len(token) == 2 and token[0].isalpha() and token[1] == "."
    if token not in _ABBREVIATIONS and not is_initial:
        return False

    cursor = index + 1
    while cursor < len(text) and text[cursor] in " \t":
        cursor += 1

    if cursor >= len(text) or "\n" in text[index + 1:cursor + 1]:
        return False

    return text[cursor].isupper()


def _sentence_spans(text: str) -> tuple[tuple[int, int], ...]:
    spans: list[tuple[int, int]] = []
    length = len(text)
    cursor = 0

    while cursor < length:
        while cursor < length and text[cursor].isspace():
            cursor += 1
        if cursor >= length:
            break

        start = cursor
        end = length
        i = cursor

        while i < length:
            ch = text[i]

            if ch == "\n":
                end = i
                break

            if ch in ".!?":
                if ch == "." and _is_abbreviation_period(text, i):
                    i += 1
                    continue

                next_index = i + 1
                if next_index >= length or text[next_index].isspace():
                    end = next_index
                    break

            i += 1

        while end > start and text[end - 1].isspace():
            end -= 1

        if end > start:
            spans.append((start, end))

        cursor = max(i + 1, end)

    return tuple(spans)


def atomize_raw_response(
    envelope: RawResponseEnvelope,
) -> tuple[ClaimAtom, ...]:
    if envelope.speaker_role is not SpeakerRole.ASSISTANT:
        raise ValueError(
            "only assistant responses may be atomized as assistant claims"
        )

    spans = _sentence_spans(envelope.text)
    return tuple(
        bind_atom(
            envelope,
            atom_id=f"{envelope.response_id}:atom:{index}",
            start=start,
            end=end,
        )
        for index, (start, end) in enumerate(spans, start=1)
    )


def validate_atom_proposals(
    envelope: RawResponseEnvelope,
    proposals: list[SpanProposal] | tuple[SpanProposal, ...],
) -> tuple[ClaimAtom, ...]:
    if envelope.speaker_role is not SpeakerRole.ASSISTANT:
        raise ValueError(
            "only assistant responses may be atomized as assistant claims"
        )

    proposal_seq = tuple(proposals)
    atom_ids = [proposal.atom_id for proposal in proposal_seq]
    if len(atom_ids) != len(set(atom_ids)):
        raise ValueError("duplicate atom_id")

    ordered = sorted(
        proposal_seq,
        key=lambda proposal: (proposal.start, proposal.end, proposal.atom_id),
    )

    previous_end: int | None = None
    atoms: list[ClaimAtom] = []

    for proposal in ordered:
        if not isinstance(proposal.atom_id, str) or not proposal.atom_id.strip():
            raise ValueError("atom_id must be non-empty")
        if not isinstance(proposal.quoted_text, str):
            raise TypeError("quoted_text must be string")

        if (
            proposal.start < 0
            or proposal.end > len(envelope.text)
            or proposal.start >= proposal.end
        ):
            raise ValueError("invalid source span")

        exact_slice = envelope.text[proposal.start:proposal.end]
        if proposal.quoted_text != exact_slice:
            raise ValueError("quoted_text must exactly match source span")

        atom = bind_atom(
            envelope,
            atom_id=proposal.atom_id,
            start=proposal.start,
            end=proposal.end,
            proposed_text=proposal.quoted_text,
        )

        if previous_end is not None and atom.start < previous_end:
            raise ValueError("span proposals must not overlap")

        atoms.append(atom)
        previous_end = atom.end

    return tuple(atoms)


def type_clause(atom: ClaimAtom) -> ClauseTypeDecision:
    reasons = list(atom.review_reasons)
    blocking_reasons = {
        "compound_clause",
        "conditional_clause",
        "ambiguous_referent",
    }

    if blocking_reasons.intersection(reasons):
        return ClauseTypeDecision(
            atom_id=atom.atom_id,
            claim_type=None,
            status=ClauseTypeStatus.REVIEW_REQUIRED,
            reasons=tuple(reasons),
            rule="review_gate",
        )

    text = atom.source_text.strip()
    action_signal = bool(_ACTION_STATE_CUES.search(text))
    estimate_signal = bool(_ESTIMATE_CUES.search(text))
    inference_signal = "epistemic_qualifier" in reasons

    signals = [
        claim_type
        for claim_type, present in (
            (ClaimType.ACTION_STATE, action_signal),
            (ClaimType.ESTIMATE, estimate_signal),
            (ClaimType.INFERENCE, inference_signal),
        )
        if present
    ]

    if len(signals) > 1:
        if "multiple_type_signals" not in reasons:
            reasons.append("multiple_type_signals")
        return ClauseTypeDecision(
            atom_id=atom.atom_id,
            claim_type=None,
            status=ClauseTypeStatus.REVIEW_REQUIRED,
            reasons=tuple(reasons),
            rule="conflicting_type_cues",
        )

    if inference_signal:
        return ClauseTypeDecision(
            atom_id=atom.atom_id,
            claim_type=ClaimType.INFERENCE,
            status=ClauseTypeStatus.REVIEW_REQUIRED,
            reasons=tuple(reasons),
            rule="epistemic_qualifier",
        )

    if estimate_signal:
        return ClauseTypeDecision(
            atom_id=atom.atom_id,
            claim_type=ClaimType.ESTIMATE,
            status=ClauseTypeStatus.TYPED,
            reasons=tuple(reasons),
            rule="estimate_cue",
        )

    if action_signal:
        return ClauseTypeDecision(
            atom_id=atom.atom_id,
            claim_type=ClaimType.ACTION_STATE,
            status=ClauseTypeStatus.TYPED,
            reasons=tuple(reasons),
            rule="action_state_cue",
        )

    return ClauseTypeDecision(
        atom_id=atom.atom_id,
        claim_type=ClaimType.OBSERVATION,
        status=ClauseTypeStatus.TYPED,
        reasons=tuple(reasons),
        rule="default_observation",
    )


def build_evidence_contract(
    atom: ClaimAtom,
    claim_type: ClaimType,
    *,
    type_human_approved: bool = False,
) -> EvidenceContract:
    if not isinstance(claim_type, ClaimType):
        raise TypeError("claim_type must be ClaimType")
    if type(type_human_approved) is not bool:
        raise TypeError("type_human_approved must be bool")

    review_reasons = list(atom.review_reasons)
    atom_requires_review = atom.status is AtomStatus.REVIEW_REQUIRED
    requires_human_review = atom_requires_review
    requires_post_action = claim_type is ClaimType.ACTION_STATE

    if claim_type in {ClaimType.INFERENCE, ClaimType.ESTIMATE}:
        fact_eligible = False
    elif claim_type is ClaimType.ACTION_STATE:
        fact_eligible = not atom_requires_review
    elif claim_type is ClaimType.RISK_SENSITIVE:
        fact_eligible = False
        requires_human_review = True
        if "risk_sensitive_requires_human_review" not in review_reasons:
            review_reasons.append("risk_sensitive_requires_human_review")
    else:
        if atom_requires_review:
            fact_eligible = False
            requires_human_review = True
        elif type_human_approved:
            fact_eligible = True
            requires_human_review = False
        else:
            fact_eligible = False
            requires_human_review = True
            if "observation_type_requires_approval" not in review_reasons:
                review_reasons.append("observation_type_requires_approval")

    return EvidenceContract(
        atom_id=atom.atom_id,
        claim_type=claim_type,
        required_directness=Directness.DIRECT,
        requires_post_action=requires_post_action,
        requires_human_review=requires_human_review,
        fact_eligible=fact_eligible,
        review_reasons=tuple(review_reasons),
    )
