# Changelog

## v1.1.0 — JSON adapter release candidate

### Adapter
- Added strict JSON-shaped single and compound verification adapters.
- Added schema version `1` and JSON-safe result serialization.
- Added timezone-aware ISO 8601 parsing with `Z` support.
- Added strict boolean/integer validation and unknown-ID rejection.
- Preserved the v1.0 deterministic core without verdict-logic changes.

### Verification
- Added 10 adapter behavior/negative tests.
- Added a differential test covering 128 boolean core cases with both human-approval states (256 adapter/core comparisons).
- Full local source suite: 40 tests.
- Independent adapter code review reported 0 issues.

### Error → Evolution

#### BH-ADP-001 — Direct demo execution before installation
- FAILURE MODE: `python examples/demo.py` from an uninstalled source checkout could not import `bodulskihal_core`.
- ROOT CAUSE: direct script execution sets the import root to the examples directory and the package had not been installed.
- GUARDRAIL: installation smoke precedes demo claims; CI installs the package before tests.
- REGRESSION TEST: system editable-install smoke followed by demo returned `FACT APPROVE`.
- VERSION CHANGE: packaging/test procedure clarified; core logic unchanged.

#### BH-ADP-002 — Clean venv build backend unavailable in current runner
- FAILURE MODE: editable install in a newly created Python 3.13 venv failed before project metadata loading.
- ROOT CAUSE: the runner venv could not import `setuptools.build_meta`.
- GUARDRAIL: classify as environment/setup until independent CI install proves the package path; do not convert it to product failure or PASS.
- REGRESSION TEST: GitHub PR CI is required before merge.
- VERSION CHANGE: v1.1 remains release-candidate branch until CI evidence is observed.

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
