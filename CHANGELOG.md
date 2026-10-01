# Changelog

## v1.0.0 — reference implementation checkpoint

### Core
- Added deterministic claim classification: FACT / INFERENCE / ESTIMATE / UNKNOWN / CONFLICT.
- Added APPROVE / BLOCK / ESCALATE verdict engine.
- Added evidence freshness, directness, eligibility and contradiction gates.
- Added post-action/final-state evidence requirement for action claims.
- Added human approval gate for high-risk claims.
- Added compound claim verification.
- Added deterministic evidence receipts and failure-evolution records.

### Error → Evolution

#### BH-ALG-001 — Determinism omitted evaluation time
- FAILURE MODE: original design said same input + same policy always yields same receipt.
- ROOT CAUSE: freshness changes as time advances.
- GUARDRAIL: `evaluation_time` is an explicit deterministic input.
- REGRESSION TEST: verifies a 299-second-old source changes from FACT to UNKNOWN when evaluation advances two seconds.
- VERSION CHANGE: specification updated before v1.0 packaging.

#### BH-ALG-002 — Vacuous compound approval
- FAILURE MODE: an empty claim set could otherwise satisfy "all consequential claims passed" vacuously.
- ROOT CAUSE: no minimum-claim precondition.
- GUARDRAIL: empty compounds are rejected.
- REGRESSION TEST: `test_empty_compound_does_not_vacuously_approve`.
- VERSION CHANGE: fail-closed input validation added.

#### BH-ALG-003 — Ambiguous timestamp handling
- FAILURE MODE: naive/aware datetime mixing raised an incidental TypeError.
- ROOT CAUSE: timezone-awareness was not validated at the boundary.
- GUARDRAIL: evaluation and evidence timestamps must be timezone-aware.
- REGRESSION TEST: explicit evaluation/evidence timestamp validation tests.
- VERSION CHANGE: deterministic boundary validation added.

#### BH-ALG-004 — Invariant test overclaimed human-gate precedence
- FAILURE MODE: exhaustive test initially expected every high-risk FACT to ESCALATE even when the action post-state gate already failed.
- ROOT CAUSE: test ignored gate precedence.
- GUARDRAIL: human approval is evaluated only after evidence/action gates pass.
- REGRESSION TEST: exhaustive 128-case invariant test encodes non-human gate precedence.
- VERSION CHANGE: invariant contract clarified; engine behavior unchanged.
