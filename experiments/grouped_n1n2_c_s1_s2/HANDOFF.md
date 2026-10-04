# Handoff

## Scope

Isolated prototype only. No existing core file, deployment, workflow, database, UI or production branch is changed.

## Exact architecture

N1 <-> N2 -> N2(final) -> C -> S1 -> S2 -> N1(read-only) -> OUTPUT

## Validation

Preparation environment:
- python -m pytest -q experiments/grouped_n1n2_c_s1_s2/test_runner.py
  - **92 passed**
- python -m compileall -q experiments/grouped_n1n2_c_s1_s2
  - exit code 0

Post-action verification of the actual GitHub branch:
- fresh clone of experiment/grouped-n1n2-c-s1-s2-20261004 into a temporary Windows directory
- isolated .venv created because system Python did not have pytest
- pytest on the checked-out experiment: **exit code 0**
- compileall on the checked-out experiment: **exit code 0**

The repository's full pre-existing test suite and hosted GitHub Actions are not claimed here.

## Critical invariants

1. No N component may issue trusted PASS/terminal authorization.
2. N2 receipts bind the exact candidate/parent but remain advisory evidence.
3. C freezes bytes/state bindings; C does not certify truth.
4. S1 and S2 have different responsibilities and both operate on the same checkpoint identity.
5. S2 does not infer global-goal PASS from contract PASS.
6. Final N1 is presentation-only.
7. Execution requires the exact S2 receipt, action hash, state hash/version and unused nonce.

## Confirmed failure fixed during implementation

S1 initially treated a stale global anchor as an integrity failure and returned BLOCK. That mixed S1 and S2 responsibilities. S1 now limits itself to integrity/provenance/state binding; S2 turns a stale/insufficient global anchor into UNKNOWN. The regression is included in test_global_goal_never_inferred_from_contract_pass.

## Next attacks

- Property/fuzz generation over receipt/canonicalization schemas.
- Common-mode specification errors across S1/S2.
- Independence/authority of global anchors.
- Multi-process or external signer boundary for receipt provenance.
- Live N1/N2 model integration only after deterministic invariants remain green.
