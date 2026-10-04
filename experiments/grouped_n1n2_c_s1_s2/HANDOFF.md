# Handoff

## Scope

Isolated prototype only. No existing core file, deployment, workflow, database, UI or production branch is changed.

## Exact architecture

N1 <-> N2 -> N2(final) -> C -> S1 -> S2 -> N1(read-only) -> OUTPUT

## Validation

Current experiment version: **0.1.5**

Preparation environment:
- python -m pytest -q experiments/grouped_n1n2_c_s1_s2/test_runner.py experiments/grouped_n1n2_c_s1_s2/test_fuzz.py
  - **437 passed** = 115 targeted/regression + 322 deterministic fuzz/property
- python -m compileall -q experiments/grouped_n1n2_c_s1_s2
  - exit code 0

Post-action verification of the actual GitHub branch:
- fresh clone of experiment/grouped-n1n2-c-s1-s2-20261004 into a temporary Windows directory
- isolated .venv created because system Python did not have pytest
- pytest on the checked-out experiment: **exit code 0**
- compileall on the checked-out experiment: **exit code 0**

The combined pre-existing repository tests plus this experiment were also run locally: **732 passed**. Hosted GitHub Actions are not claimed here.

## Critical invariants

1. No N component may issue trusted PASS/terminal authorization.
2. N2 receipts bind the exact candidate/parent but remain advisory evidence.
3. C freezes bytes/state bindings; C does not certify truth.
4. S1 and S2 have different responsibilities and both operate on the same checkpoint identity.
5. S2 does not infer global-goal PASS from contract PASS.
6. Final N1 is presentation-only.
7. Execution requires the exact S2 receipt, action hash, state hash/version, current-policy hash/semantics and an unused nonce recorded in a trusted file-backed ledger.

## Confirmed failure fixed during implementation

S1 initially treated a stale global anchor as an integrity failure and returned BLOCK. That mixed S1 and S2 responsibilities. S1 now limits itself to integrity/provenance/state binding; S2 turns a stale/insufficient global anchor into UNKNOWN. The regression is included in test_global_goal_never_inferred_from_contract_pass.

## Confirmed second failure fixed

The initial fuzz-expanded attack found that loop CONFLICT/UNKNOWN and final N2 CHALLENGE/UNKNOWN could be recorded in C but silently disappear before S2, producing PASS. Version 0.1.1 makes both loop status and final-N2 status inputs to S2's terminal lattice. Regression tests cover all four reproduced paths.

## Confirmed third failure fixed

A caller could previously fabricate a plain loop_result with PASS and skip N1<->N2 entirely. Version 0.1.2 introduces an authoritative loop receipt bound to transition, candidate, loop status and receipt-chain root. final N2, C and S1 verify this provenance chain. Six new regression cases cover the reproduced bypass and tampering variants.

## Confirmed fourth failure fixed

A plain JSON global anchor could self-assert `independent=true` and obtain global PASS. Version 0.1.3 requires a separately authenticated anchor receipt for global PASS. Raw/self-asserted anchors now remain UNKNOWN. Targeted regressions cover missing receipt, wrong trust root, receipt tampering and payload mismatch.

## Confirmed fifth failure fixed

The transition previously authenticated only the continuity of an arbitrary evidence_root string, not its provenance. Version 0.1.4 requires a separate evidence-authority receipt bound to evidence root, state version and contract hash for S1 PASS. Missing evidence provenance now yields UNKNOWN; tampered/wrong-root receipts fail closed.


## Confirmed sixth failure fixed

A policy could change after S2 while the state/action stayed the same, and the executor would still execute the stale certification. Version 0.1.5 makes the action boundary verify the current policy hash and re-run the concrete contract check before nonce consumption.

## Confirmed seventh failure fixed

Nonce consumption was previously stored only inside the current TrustedBoundary object. Recreating the boundary with the same keys allowed a previously executed terminal receipt to execute again. Version 0.1.5 requires a file-backed atomic nonce ledger; replay remains NOOP across boundary/process recreation when the same trusted ledger is used.

## Remaining execution caveat

The local file ledger is at-most-once replay protection, not an exactly-once distributed transaction with a real external side effect. Production execution must rely on idempotent external operations or transactionally coupled idempotency state.

## Next attacks

- Common-mode specification errors across S1/S2.
- Independence/authority of global anchors.
- External signer/process isolation for receipt provenance.
- Atomic coupling of durable idempotency with the real external side effect.
- Live N1/N2 model integration only after deterministic invariants remain green.
