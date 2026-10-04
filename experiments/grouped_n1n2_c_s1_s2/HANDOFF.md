# Handoff

## Scope

Isolated prototype only. No existing core file, deployment, workflow, database, UI or production branch is changed.

## Exact architecture

N1 <-> N2 -> N2(final) -> C -> S1 -> S2 -> N1(read-only) -> OUTPUT

## Validation

Current experiment version: **0.1.8**

Preparation environment:
- python -m pytest experiments/grouped_n1n2_c_s1_s2 --tb=short
  - **444 passed** = prior 441 + 3 specification-scope regressions
- python -m compileall -q experiments/grouped_n1n2_c_s1_s2
  - exit code 0
- multiprocess nonce race: 16 spawned processes attempted one token; exactly 1 consumed it and 15 were rejected

Post-action verification of the actual GitHub branch:
- fresh clone of attack/common-mode-spec-basis-20261004 into a temporary Windows directory
- isolated .venv created because system Python did not have pytest
- pytest on the checked-out experiment: **exit code 0**
- compileall on the checked-out experiment: **exit code 0**

The combined pre-existing repository tests plus this experiment were also run locally after the specification-scope hardening: **739 passed**. One immediately prior combined invocation produced a large transient failure set, but two fresh reruns of the same combined scope passed; the root cause of that transient is UNKNOWN, so it is recorded as a stability warning rather than silently discarded. Hosted GitHub Actions are not claimed here.

## Critical invariants

1. No N component may issue trusted PASS/terminal authorization.
2. N2 receipts bind the exact candidate/parent but remain advisory evidence.
3. C freezes bytes/state bindings; C does not certify truth.
4. S1 and S2 have different responsibilities and both operate on the same checkpoint identity.
5. S2 does not infer global-goal PASS from contract PASS.
6. Final N1 is presentation-only.
7. Execution requires the exact S2 receipt, action hash, state hash/version, current-policy hash/semantics and the S2-derived stable execution token recorded in a trusted file-backed ledger.

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


## Confirmed eighth failure fixed

The durable ledger could still be bypassed because action_nonce was an S2 caller input. Re-running S2 for the same checkpoint with a fresh nonce produced a second valid terminal receipt and the same action executed again. Version 0.1.6 removes caller nonce control and derives a stable execution token from the trusted goal_id. Re-certifying the same goal now reuses the same token and becomes NOOP after the first execution.


## Confirmed tenth failure fixed

A valid authenticated global-anchor receipt could be replayed for a different goal or a changed policy as long as the state version still matched. Version 0.1.7 binds the anchor payload to the exact goal identity and contract hash, and the transition plus S2 independently enforce those bindings. Replaying the old anchor across either dimension now fails closed.

## Stable-operation identity assumption

goal_id is treated as the identity of one intended side effect. Retries must preserve it. A new real operation requires a new trusted goal_id; otherwise upstream goal-ID issuance can still defeat semantic duplicate detection.

## Remaining execution caveat

The local file ledger is at-most-once replay protection, not an exactly-once distributed transaction with a real external side effect. Production execution must rely on idempotent external operations or transactionally coupled idempotency state.

## Next attacks

- Independent semantic grounding outside the same trusted specification chain.
- Independence/authority of global anchors.
- External signer/process isolation for receipt provenance.
- Atomic coupling of durable idempotency with the real external side effect.
- Live N1/N2 model integration only after deterministic invariants remain green.


## Confirmed eleventh failure bounded, not falsely "solved"

A RED regression reproduced the remaining common-mode specification failure: all authenticated inputs and deterministic gates can agree while the trusted starting specification omits a real requirement. The system returned PASS. This cannot be disproved from the same information set without inventing missing semantics.

Version 0.1.8 therefore hardens the claim boundary instead of adding a fake extra verifier. S2 receipts and read-only output now state `epistemic_scope=authenticated_inputs_and_declared_requirements_only` and `global_truth_certified=false`. The executor requires those exact certified fields, so N1/presentation cannot upgrade bounded PASS into a claim of universal truth.

Residual semantic completeness remains UNKNOWN unless grounded outside the same trust chain.
