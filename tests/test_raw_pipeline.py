import hashlib

import pytest

from b_1_2_core import ClaimType, Directness
from b_1_2_core.raw_pipeline import (
    AtomStatus,
    ClaimAtom,
    SpeakerRole,
    RawResponseEnvelope,
    SpanProposal,
    bind_atom,
    atomize_raw_response,
    build_evidence_contract,
    type_clause,
    validate_atom_proposals,
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


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            'He said, "Done." Next sentence.',
            ['He said, "Done."', "Next sentence."],
        ),
        (
            "(The file exists.) The service is ready.",
            ["(The file exists.)", "The service is ready."],
        ),
    ],
)
def test_sentence_segmentation_includes_closers_before_splitting(raw, expected):
    envelope = RawResponseEnvelope.create("r1", raw, SpeakerRole.ASSISTANT)

    atoms = atomize_raw_response(envelope)

    assert [atom.source_text for atom in atoms] == expected
    for atom in atoms:
        assert raw[atom.start:atom.end] == atom.source_text


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
    from b_1_2_core.raw_pipeline import SpanProposal, validate_atom_proposals

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
    from b_1_2_core.raw_pipeline import SpanProposal, validate_atom_proposals

    raw = "The result may be 42."
    envelope = RawResponseEnvelope.create("r2", raw, SpeakerRole.ASSISTANT)

    with pytest.raises(ValueError, match="quoted_text"):
        validate_atom_proposals(
            envelope,
            [SpanProposal(atom_id="p1", start=0, end=len(raw), quoted_text="The result is 42.")],
        )


def test_span_proposals_must_not_overlap():
    from b_1_2_core.raw_pipeline import SpanProposal, validate_atom_proposals

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
    from b_1_2_core.raw_pipeline import SpanProposal, validate_atom_proposals

    raw = "First. Second."
    envelope = RawResponseEnvelope.create("r2", raw, SpeakerRole.ASSISTANT)
    first = SpanProposal(atom_id="p1", start=0, end=6, quoted_text="First.")
    second = SpanProposal(atom_id="p2", start=7, end=14, quoted_text="Second.")

    atoms = validate_atom_proposals(envelope, [second, first])

    assert [a.atom_id for a in atoms] == ["p1", "p2"]
    assert [a.source_text for a in atoms] == ["First.", "Second."]


def test_duplicate_atom_ids_are_rejected():
    from b_1_2_core.raw_pipeline import SpanProposal, validate_atom_proposals

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
    from b_1_2_core.raw_pipeline import SpanProposal, validate_atom_proposals

    raw = "The system is broken."
    envelope = RawResponseEnvelope.create("r2", raw, SpeakerRole.USER)

    with pytest.raises(ValueError, match="assistant"):
        validate_atom_proposals(
            envelope,
            [SpanProposal(atom_id="p1", start=0, end=len(raw), quoted_text=raw)],
        )


def test_span_proposal_preserves_uncertainty_in_source_text():
    from b_1_2_core.raw_pipeline import SpanProposal, validate_atom_proposals

    raw = "The result might be 42."
    envelope = RawResponseEnvelope.create("r2", raw, SpeakerRole.ASSISTANT)

    atoms = validate_atom_proposals(
        envelope,
        [SpanProposal(atom_id="p1", start=0, end=len(raw), quoted_text=raw)],
    )

    assert atoms[0].source_text == raw
    assert atoms[0].status is AtomStatus.REVIEW_REQUIRED
    assert "epistemic_qualifier" in atoms[0].review_reasons


def test_raw_observation_type_is_not_fact_eligible_without_type_approval():
    raw = "The file exists."
    envelope = RawResponseEnvelope.create("r3", raw, SpeakerRole.ASSISTANT)
    atom = atomize_raw_response(envelope)[0]

    contract = build_evidence_contract(atom, ClaimType.OBSERVATION)

    assert contract.fact_eligible is False
    assert contract.requires_human_review is True
    assert "observation_type_requires_approval" in contract.review_reasons


def test_raw_observation_type_can_be_fact_eligible_after_type_approval():
    raw = "The file exists."
    envelope = RawResponseEnvelope.create("r3", raw, SpeakerRole.ASSISTANT)
    atom = atomize_raw_response(envelope)[0]

    contract = build_evidence_contract(
        atom,
        ClaimType.OBSERVATION,
        type_human_approved=True,
    )

    assert contract.fact_eligible is True
    assert contract.requires_human_review is False


def test_action_state_type_is_safe_to_accept_without_type_approval_because_it_adds_gate():
    raw = "Deployment completed."
    envelope = RawResponseEnvelope.create("r3", raw, SpeakerRole.ASSISTANT)
    atom = atomize_raw_response(envelope)[0]

    contract = build_evidence_contract(atom, ClaimType.ACTION_STATE)

    assert contract.fact_eligible is True
    assert contract.requires_post_action is True
    assert contract.requires_human_review is False


@pytest.mark.parametrize("claim_type", [ClaimType.INFERENCE, ClaimType.ESTIMATE])
def test_non_fact_types_never_need_type_approval_to_remain_non_fact_eligible(claim_type):
    raw = "The root cause may be a timeout."
    envelope = RawResponseEnvelope.create("r3", raw, SpeakerRole.ASSISTANT)
    atom = bind_atom(envelope, atom_id="a1", start=0, end=len(raw))

    contract = build_evidence_contract(atom, claim_type)

    assert contract.fact_eligible is False


def test_human_type_approval_cannot_override_review_required_atom():
    raw = "Tests passed and deployment completed."
    envelope = RawResponseEnvelope.create("r3", raw, SpeakerRole.ASSISTANT)
    atom = atomize_raw_response(envelope)[0]

    contract = build_evidence_contract(
        atom,
        ClaimType.OBSERVATION,
        type_human_approved=True,
    )

    assert contract.fact_eligible is False
    assert contract.requires_human_review is True
    assert "compound_clause" in contract.review_reasons


def test_raw_pipeline_rejects_envelope_with_forged_hash():
    envelope = RawResponseEnvelope(
        response_id="r4",
        text="The file exists.",
        speaker_role=SpeakerRole.ASSISTANT,
        raw_sha256="0" * 64,
    )

    with pytest.raises(ValueError, match="raw_sha256"):
        atomize_raw_response(envelope)


@pytest.mark.parametrize(("start", "end"), [(True, 2), (0, False)])
def test_bind_atom_rejects_boolean_span_offsets(start, end):
    envelope = RawResponseEnvelope.create("r4", "abc", SpeakerRole.ASSISTANT)

    with pytest.raises(TypeError, match="span offsets"):
        bind_atom(envelope, atom_id="a1", start=start, end=end)


def test_proposals_reject_invalid_items_before_accessing_fields():
    envelope = RawResponseEnvelope.create("r4", "The file exists.", SpeakerRole.ASSISTANT)

    with pytest.raises(TypeError, match="SpanProposal"):
        validate_atom_proposals(envelope, [object()])


def test_proposals_reject_duplicate_ids_after_normalization():
    envelope = RawResponseEnvelope.create("r4", "First. Second.", SpeakerRole.ASSISTANT)

    with pytest.raises(ValueError, match="duplicate atom_id"):
        validate_atom_proposals(
            envelope,
            [
                SpanProposal("same", 0, 6, "First."),
                SpanProposal(" same ", 7, 14, "Second."),
            ],
        )


def test_clause_typing_rejects_forged_atom_runtime_types():
    atom = ClaimAtom(
        atom_id="a1",
        response_id="r4",
        start=0,
        end=1,
        source_text="A",
        status="ready",
        review_reasons=(),
    )

    with pytest.raises(TypeError, match="atom.status"):
        type_clause(atom)


def test_evidence_contract_rejects_atom_whose_status_omits_review_reasons():
    atom = ClaimAtom(
        atom_id="a1",
        response_id="r4",
        start=0,
        end=len("Tests passed and deployment completed."),
        source_text="Tests passed and deployment completed.",
        status=AtomStatus.READY,
        review_reasons=("compound_clause",),
    )

    with pytest.raises(ValueError, match="status must match review reasons"):
        build_evidence_contract(
            atom,
            ClaimType.OBSERVATION,
            type_human_approved=True,
        )


def test_clause_typing_rejects_atom_that_omits_text_review_signals():
    text = "Tests passed and deployment completed."
    atom = ClaimAtom(
        atom_id="a1",
        response_id="r4",
        start=0,
        end=len(text),
        source_text=text,
        status=AtomStatus.READY,
        review_reasons=(),
    )

    with pytest.raises(ValueError, match="review_reasons must match source_text"):
        type_clause(atom)
