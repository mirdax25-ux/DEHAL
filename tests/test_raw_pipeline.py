import hashlib

import pytest

from bodulskihal_core import ClaimType, Directness
from bodulskihal_core.raw_pipeline import (
    AtomStatus,
    SpeakerRole,
    RawResponseEnvelope,
    bind_atom,
    atomize_raw_response,
    build_evidence_contract,
)


def test_raw_response_envelope_hashes_exact_bytes():
    raw = "The result may be 42.\nDeployment is not complete."
    envelope = RawResponseEnvelope.create(
        response_id="r1",
        text=raw,
        speaker_role=SpeakerRole.ASSISTANT,
    )

    assert envelope.text == raw
    assert envelope.raw_sha256 == hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_atom_span_is_exact_source_slice_not_paraphrase():
    raw = "The result may be 42."
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)

    atom = bind_atom(
        envelope,
        atom_id="a1",
        start=0,
        end=len(raw),
    )

    assert atom.source_text == raw
    assert envelope.text[atom.start:atom.end] == atom.source_text


def test_bind_atom_rejects_proposed_text_drift():
    raw = "The result may be 42."
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)

    with pytest.raises(ValueError, match="source span"):
        bind_atom(
            envelope,
            atom_id="a1",
            start=0,
            end=len(raw),
            proposed_text="The result is 42.",
        )


def test_qualifiers_negation_numbers_and_dates_are_preserved_verbatim():
    raw = "It may not be ready on 2026-10-05 and the estimate is 42.5%."
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)

    atom = bind_atom(envelope, atom_id="a1", start=0, end=len(raw))

    assert "may not" in atom.source_text
    assert "2026-10-05" in atom.source_text
    assert "42.5%" in atom.source_text


def test_default_atomizer_keeps_compound_sentence_whole_and_requires_review():
    raw = "Tests passed and deployment completed."
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)

    atoms = atomize_raw_response(envelope)

    assert len(atoms) == 1
    assert atoms[0].source_text == raw
    assert atoms[0].status is AtomStatus.REVIEW_REQUIRED
    assert "compound_clause" in atoms[0].review_reasons


def test_simple_sentence_can_be_ready_without_rewriting():
    raw = "The file exists."
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)

    atoms = atomize_raw_response(envelope)

    assert len(atoms) == 1
    assert atoms[0].status is AtomStatus.READY
    assert atoms[0].source_text == "The file exists."


def test_ambiguous_pronoun_claim_requires_review():
    raw = "It failed."
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)

    atoms = atomize_raw_response(envelope)

    assert atoms[0].status is AtomStatus.REVIEW_REQUIRED
    assert "ambiguous_referent" in atoms[0].review_reasons


def test_user_prompt_is_not_silently_treated_as_assistant_claims():
    envelope = RawResponseEnvelope.create(
        response_id="r1",
        text="The system is definitely broken.",
        speaker_role=SpeakerRole.USER,
    )

    with pytest.raises(ValueError, match="assistant"):
        atomize_raw_response(envelope)


def test_sentence_segmentation_preserves_offsets_and_original_order():
    raw = "First claim. Second claim! Third claim?"
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)

    atoms = atomize_raw_response(envelope)

    assert [a.source_text for a in atoms] == [
        "First claim.",
        "Second claim!",
        "Third claim?",
    ]
    for atom in atoms:
        assert raw[atom.start:atom.end] == atom.source_text
    assert [a.start for a in atoms] == sorted(a.start for a in atoms)


def test_evidence_contract_for_action_requires_direct_post_action_evidence():
    raw = "Deployment completed."
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)
    atom = bind_atom(envelope, atom_id="a1", start=0, end=len(raw))

    contract = build_evidence_contract(atom, ClaimType.ACTION_STATE)

    assert contract.claim_type is ClaimType.ACTION_STATE
    assert contract.required_directness is Directness.DIRECT
    assert contract.requires_post_action is True
    assert contract.fact_eligible is True


def test_evidence_contract_for_inference_cannot_be_fact_eligible():
    raw = "The root cause is probably a timeout."
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)
    atom = bind_atom(envelope, atom_id="a1", start=0, end=len(raw))

    contract = build_evidence_contract(atom, ClaimType.INFERENCE)

    assert contract.claim_type is ClaimType.INFERENCE
    assert contract.fact_eligible is False


def test_review_required_atom_cannot_get_auto_approvable_contract():
    raw = "Tests passed and deployment completed."
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)
    atom = atomize_raw_response(envelope)[0]

    contract = build_evidence_contract(atom, ClaimType.OBSERVATION)

    assert contract.requires_human_review is True
    assert contract.fact_eligible is False


def test_empty_or_whitespace_raw_response_fails_closed():
    with pytest.raises(ValueError, match="text"):
        RawResponseEnvelope.create("r1", "   ", SpeakerRole.ASSISTANT)


def test_invalid_span_fails_closed():
    envelope = RawResponseEnvelope.create("r1", "abc", SpeakerRole.ASSISTANT)

    with pytest.raises(ValueError, match="span"):
        bind_atom(envelope, atom_id="a1", start=2, end=1)


def test_epistemic_qualifier_requires_review_and_blocks_fact_eligibility():
    raw = "The result may be 42."
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)

    atom = atomize_raw_response(envelope)[0]
    contract = build_evidence_contract(atom, ClaimType.OBSERVATION)

    assert atom.status is AtomStatus.REVIEW_REQUIRED
    assert "epistemic_qualifier" in atom.review_reasons
    assert contract.fact_eligible is False
    assert contract.requires_human_review is True


def test_conditional_clause_requires_review():
    raw = "If the service responds, deployment is ready."
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)

    atom = atomize_raw_response(envelope)[0]

    assert atom.status is AtomStatus.REVIEW_REQUIRED
    assert "conditional_clause" in atom.review_reasons


def test_alternative_clause_requires_review():
    raw = "The fault is in the network or the database."
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)

    atom = atomize_raw_response(envelope)[0]

    assert atom.status is AtomStatus.REVIEW_REQUIRED
    assert "compound_clause" in atom.review_reasons


def test_semicolon_clause_requires_review():
    raw = "Tests passed; deployment is still pending."
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)

    atom = atomize_raw_response(envelope)[0]

    assert atom.status is AtomStatus.REVIEW_REQUIRED
    assert "compound_clause" in atom.review_reasons


def test_common_abbreviation_does_not_split_person_name():
    raw = "Dr. Smith approved the report."
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)

    atoms = atomize_raw_response(envelope)

    assert len(atoms) == 1
    assert atoms[0].source_text == raw


def test_initial_does_not_split_person_name():
    raw = "A. Smith approved the report."
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)

    atoms = atomize_raw_response(envelope)

    assert len(atoms) == 1
    assert atoms[0].source_text == raw


def test_span_proposal_can_only_point_to_exact_raw_text():
    from bodulskihal_core.raw_pipeline import SpanProposal, validate_atom_proposals

    raw = "The file exists. Deployment may still be pending."
    envelope = RawResponseEnvelope.create("r2", raw, SpeakerRole.ASSISTANT)
    start = raw.index("The file exists.")
    end = start + len("The file exists.")

    atoms = validate_atom_proposals(
        envelope,
        [SpanProposal(atom_id="p1", start=start, end=end, quoted_text="The file exists.")],
    )

    assert len(atoms) == 1
    assert atoms[0].source_text == "The file exists."
    assert atoms[0].start == start
    assert atoms[0].end == end


def test_span_proposal_rejects_paraphrased_quote():
    from bodulskihal_core.raw_pipeline import SpanProposal, validate_atom_proposals

    raw = "The result may be 42."
    envelope = RawResponseEnvelope.create("r2", raw, SpeakerRole.ASSISTANT)

    with pytest.raises(ValueError, match="quoted_text"):
        validate_atom_proposals(
            envelope,
            [SpanProposal(atom_id="p1", start=0, end=len(raw), quoted_text="The result is 42.")],
        )


def test_span_proposals_must_not_overlap():
    from bodulskihal_core.raw_pipeline import SpanProposal, validate_atom_proposals

    raw = "Alpha beta gamma."
    envelope = RawResponseEnvelope.create("r2", raw, SpeakerRole.ASSISTANT)

    with pytest.raises(ValueError, match="overlap"):
        validate_atom_proposals(
            envelope,
            [
                SpanProposal(atom_id="p1", start=0, end=10, quoted_text=raw[0:10]),
                SpanProposal(atom_id="p2", start=6, end=len(raw), quoted_text=raw[6:]),
            ],
        )


def test_span_proposals_are_sorted_deterministically_by_source_offset():
    from bodulskihal_core.raw_pipeline import SpanProposal, validate_atom_proposals

    raw = "First. Second."
    envelope = RawResponseEnvelope.create("r2", raw, SpeakerRole.ASSISTANT)
    first = SpanProposal(atom_id="p1", start=0, end=6, quoted_text="First.")
    second = SpanProposal(atom_id="p2", start=7, end=14, quoted_text="Second.")

    atoms = validate_atom_proposals(envelope, [second, first])

    assert [a.atom_id for a in atoms] == ["p1", "p2"]
    assert [a.source_text for a in atoms] == ["First.", "Second."]


def test_duplicate_atom_ids_are_rejected():
    from bodulskihal_core.raw_pipeline import SpanProposal, validate_atom_proposals

    raw = "First. Second."
    envelope = RawResponseEnvelope.create("r2", raw, SpeakerRole.ASSISTANT)

    with pytest.raises(ValueError, match="duplicate atom_id"):
        validate_atom_proposals(
            envelope,
            [
                SpanProposal(atom_id="same", start=0, end=6, quoted_text="First."),
                SpanProposal(atom_id="same", start=7, end=14, quoted_text="Second."),
            ],
        )


def test_non_assistant_span_proposals_are_rejected():
    from bodulskihal_core.raw_pipeline import SpanProposal, validate_atom_proposals

    raw = "The system is broken."
    envelope = RawResponseEnvelope.create("r2", raw, SpeakerRole.USER)

    with pytest.raises(ValueError, match="assistant"):
        validate_atom_proposals(
            envelope,
            [SpanProposal(atom_id="p1", start=0, end=len(raw), quoted_text=raw)],
        )


def test_span_proposal_preserves_uncertainty_in_source_text():
    from bodulskihal_core.raw_pipeline import SpanProposal, validate_atom_proposals

    raw = "The result might be 42."
    envelope = RawResponseEnvelope.create("r2", raw, SpeakerRole.ASSISTANT)

    atoms = validate_atom_proposals(
        envelope,
        [SpanProposal(atom_id="p1", start=0, end=len(raw), quoted_text=raw)],
    )

    assert atoms[0].source_text == raw
    assert atoms[0].status is AtomStatus.REVIEW_REQUIRED
    assert "epistemic_qualifier" in atoms[0].review_reasons
