import unicodedata

import pytest

from b_1_2_core import (
    Claim,
    ClaimType,
    Classification,
    Directness,
    Evidence,
    Policy,
    Verdict,
    verify_claim,
)
from b_1_2_core.ingestion import (
    TypeAuthority,
    atomize_model_response,
    build_evidence_contract,
    ingest_model_response,
    normalize_model_response,
    type_clause,
)


def test_normalize_model_response_is_deterministic_and_hashes_normalized_text():
    raw = "  Cafe\u0301 result.\r\nSecond line.\r  "
    first = normalize_model_response(raw)
    second = normalize_model_response(raw)

    assert first == second
    assert first.text == "Café result.\nSecond line."
    assert first.text == unicodedata.normalize("NFC", first.text)
    assert len(first.sha256) == 64


def test_empty_model_response_fails_closed():
    with pytest.raises(ValueError, match="model response"):
        normalize_model_response("  \r\n\t ")


def test_atomizer_emits_exact_anchored_spans_without_inventing_text():
    normalized = normalize_model_response(
        "[INFERENCE] Likely cause A.\n"
        "Plain claim B!  [ESTIMATE] About 3 hours?"
    )

    atoms = atomize_model_response(normalized)

    assert [atom.text for atom in atoms] == [
        "[INFERENCE] Likely cause A.",
        "Plain claim B!",
        "[ESTIMATE] About 3 hours?",
    ]

    for atom in atoms:
        assert normalized.text[atom.start:atom.end] == atom.text
        assert atom.source_response_sha256 == normalized.sha256


def test_atom_ids_and_order_are_deterministic():
    normalized = normalize_model_response("First claim. Second claim? Third claim!")

    first = atomize_model_response(normalized)
    second = atomize_model_response(normalized)

    assert first == second
    assert [atom.atom_id for atom in first] == [
        "atom-0001",
        "atom-0002",
        "atom-0003",
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("[INFERENCE] A likely cause.", ClaimType.INFERENCE),
        ("[ESTIMATE] About three hours.", ClaimType.ESTIMATE),
        ("[ACTION_STATE] Export completed.", ClaimType.ACTION_STATE),
        ("[RISK_SENSITIVE] Publish externally.", ClaimType.RISK_SENSITIVE),
    ],
)
def test_executor_can_only_declare_stricter_non_plain_types(text, expected):
    assert type_clause(text, authority=TypeAuthority.EXECUTOR) is expected


def test_executor_observation_declaration_is_not_authoritative():
    assert (
        type_clause(
            "[OBSERVATION] The result is correct.",
            authority=TypeAuthority.EXECUTOR,
        )
        is ClaimType.UNCLASSIFIED
    )


def test_trusted_policy_can_classify_explicit_observation():
    assert (
        type_clause(
            "[OBSERVATION] The result is correct.",
            authority=TypeAuthority.TRUSTED_POLICY,
        )
        is ClaimType.OBSERVATION
    )


def test_untagged_plain_text_is_unclassified():
    assert (
        type_clause(
            "The result is correct.",
            authority=TypeAuthority.EXECUTOR,
        )
        is ClaimType.UNCLASSIFIED
    )


def test_unclassified_claim_cannot_become_fact_even_with_direct_evidence():
    result = verify_claim(
        Claim(
            "raw-1",
            "The result is correct.",
            ClaimType.UNCLASSIFIED,
        ),
        [
            Evidence(
                source_id="source-a",
                supports=True,
                observed_at=__import__("datetime").datetime(
                    2026, 10, 1, 8, 0, tzinfo=__import__("datetime").timezone.utc
                ),
                directness=Directness.DIRECT,
            )
        ],
        policy=Policy(version="2.0", max_age_seconds=300),
        evaluation_time=__import__("datetime").datetime(
            2026, 10, 1, 8, 0, tzinfo=__import__("datetime").timezone.utc
        ),
    )

    assert result.classification is Classification.UNKNOWN
    assert result.verdict is Verdict.BLOCK
    assert result.reason == "unclassified_claim"


def test_unclassified_contract_is_not_verification_ready():
    contract = build_evidence_contract(
        atom_id="atom-0001",
        claim_type=ClaimType.UNCLASSIFIED,
    )

    assert contract.verification_ready is False
    assert contract.reason == "trusted_typing_required"


def test_action_state_contract_requires_independent_post_action_evidence():
    contract = build_evidence_contract(
        atom_id="atom-0001",
        claim_type=ClaimType.ACTION_STATE,
    )

    assert contract.verification_ready is True
    assert contract.post_action_required is True
    assert contract.independent_post_action_required is True
    assert contract.minimum_independent_sources == 1


def test_risk_sensitive_contract_requires_human_approval():
    contract = build_evidence_contract(
        atom_id="atom-0001",
        claim_type=ClaimType.RISK_SENSITIVE,
    )

    assert contract.verification_ready is True
    assert contract.human_approval_required is True


def test_ingest_returns_atoms_and_contracts_deterministically():
    raw = (
        "[INFERENCE] Likely explanation. "
        "[ACTION_STATE] Export completed. "
        "Plain unsupported assertion."
    )

    first = ingest_model_response(raw, authority=TypeAuthority.EXECUTOR)
    second = ingest_model_response(raw, authority=TypeAuthority.EXECUTOR)

    assert first == second
    assert first.normalized.sha256 == second.normalized.sha256
    assert [atom.claim_type for atom in first.atoms] == [
        ClaimType.INFERENCE,
        ClaimType.ACTION_STATE,
        ClaimType.UNCLASSIFIED,
    ]
    assert first.contracts[-1].verification_ready is False
