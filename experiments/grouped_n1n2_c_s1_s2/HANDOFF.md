# Handoff

## Scope

Isolated prototype only. No existing core file, deployment, workflow, database, UI or production branch is changed.

## Exact architecture

N1 <-> N2 -> N2(final) -> C -> S1 -> S2 -> N1(read-only) -> OUTPUT

## Local validation performed before publication

- python -m pytest -q experiments/grouped_n1n2_c_s1_s2/test_runner.py
  - **92 passed**
- python -m compileall -q experiments/grouped_n1n2_c_s1_s2
  - exit code 0

This validates the isolated prototype files in the preparation environment only. Hosted GitHub CI and the repository's full existing suite are not claimed until separately observed.

## Critical invariants

1. No N component may issue trusted PASS/terminal authorization.
2. N2 receipts bind the exact candidate/parent but remain advisory evidence.
3. C freezes bytes/state bindings; C does not certify truth.
4. S1 and S2 have different responsibilities and both operate on the same checkpoint identity.
5. S2 does not infer global-goal PASS from contract PASS.
6. Final N1 is presentation-only.
7. Execution requires the exact S2 receipt, action hash, state hash/version and unused nonce.

## Next attacks

- Property/fuzz generation over receipt/canonicalization schemas.
- Common-mode specification errors across S1/S2.
- Independence/authority of global anchors.
- Multi-process or external signer boundary for receipt provenance.
- Live N1/N2 model integration only after deterministic invariants remain green.
