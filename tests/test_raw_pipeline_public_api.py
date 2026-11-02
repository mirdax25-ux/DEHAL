def test_raw_pipeline_symbols_are_exported_from_package():
    from b_1_2_core import (
        AtomStatus,
        ClaimAtom,
        EvidenceContract,
        RawResponseEnvelope,
        SpeakerRole,
        atomize_raw_response,
        bind_atom,
        build_evidence_contract,
    )

    assert RawResponseEnvelope is not None
    assert SpeakerRole is not None
    assert AtomStatus is not None
    assert ClaimAtom is not None
    assert EvidenceContract is not None
    assert atomize_raw_response is not None
    assert bind_atom is not None
    assert build_evidence_contract is not None
