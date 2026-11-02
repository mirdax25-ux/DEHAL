from b_1_2_core import ClaimType
from b_1_2_core.raw_pipeline import (
    ClauseTypeStatus,
    RawResponseEnvelope,
    SpeakerRole,
    atomize_raw_response,
    type_clause,
)


def atom(text: str):
    envelope = RawResponseEnvelope.create("r1", text, SpeakerRole.ASSISTANT)
    return atomize_raw_response(envelope)[0]


def test_simple_declarative_clause_types_as_observation():
    decision = type_clause(atom("The file exists."))

    assert decision.status is ClauseTypeStatus.TYPED
    assert decision.claim_type is ClaimType.OBSERVATION
    assert decision.reasons == ()


def test_clear_negated_clause_remains_observation():
    decision = type_clause(atom("The file does not exist."))

    assert decision.status is ClauseTypeStatus.TYPED
    assert decision.claim_type is ClaimType.OBSERVATION


def test_completion_language_types_as_action_state():
    decision = type_clause(atom("Deployment completed."))

    assert decision.status is ClauseTypeStatus.TYPED
    assert decision.claim_type is ClaimType.ACTION_STATE
    assert decision.rule == "action_state_cue"


def test_sent_language_types_as_action_state():
    decision = type_clause(atom("The email was sent."))

    assert decision.status is ClauseTypeStatus.TYPED
    assert decision.claim_type is ClaimType.ACTION_STATE


def test_explicit_estimate_types_as_estimate():
    decision = type_clause(atom("Estimated duration is 3 hours."))

    assert decision.status is ClauseTypeStatus.TYPED
    assert decision.claim_type is ClaimType.ESTIMATE
    assert decision.rule == "estimate_cue"


def test_epistemic_qualifier_types_as_inference_but_keeps_review_gate():
    decision = type_clause(atom("The root cause is probably a timeout."))

    assert decision.status is ClauseTypeStatus.REVIEW_REQUIRED
    assert decision.claim_type is ClaimType.INFERENCE
    assert "epistemic_qualifier" in decision.reasons


def test_conditional_clause_is_not_auto_typed():
    decision = type_clause(atom("If the service responds, deployment is ready."))

    assert decision.status is ClauseTypeStatus.REVIEW_REQUIRED
    assert decision.claim_type is None
    assert "conditional_clause" in decision.reasons


def test_compound_clause_is_not_auto_typed():
    decision = type_clause(atom("Tests passed and deployment completed."))

    assert decision.status is ClauseTypeStatus.REVIEW_REQUIRED
    assert decision.claim_type is None
    assert "compound_clause" in decision.reasons


def test_ambiguous_referent_is_not_auto_typed():
    decision = type_clause(atom("It failed."))

    assert decision.status is ClauseTypeStatus.REVIEW_REQUIRED
    assert decision.claim_type is None
    assert "ambiguous_referent" in decision.reasons


def test_mixed_action_and_epistemic_signals_fail_closed():
    decision = type_clause(atom("Deployment may have completed."))

    assert decision.status is ClauseTypeStatus.REVIEW_REQUIRED
    assert decision.claim_type is None
    assert "multiple_type_signals" in decision.reasons


def test_mixed_action_and_estimate_signals_fail_closed():
    decision = type_clause(atom("Deployment completed in approximately 3 hours."))

    assert decision.status is ClauseTypeStatus.REVIEW_REQUIRED
    assert decision.claim_type is None
    assert "multiple_type_signals" in decision.reasons
