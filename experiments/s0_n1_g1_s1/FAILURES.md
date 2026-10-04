# Failure and challenge record — experiment 0.1.0

## F1 — missing local test runner

- FAILURE MODE: initial `python -m pytest` could not start (`No module named pytest`).
- ROOT CAUSE: the selected system Python did not have the repository's development test runner.
- GUARDRAIL: use an isolated `.venv` and the same pytest dependency as existing CI.
- REGRESSION TEST: baseline existing suite executed in the venv: 295 tests passed before code changes; repeat together with the experiment in final validation.
- VERSION CHANGE: no version change; local development environment only, no production dependency added.

## F2 — incomplete specification can imply a false broad PASS

- FAILURE MODE: an existence-only specification passes although the actual result is incorrect. This is a reproduced specification-level counterexample, not a production failure claim.
- ROOT CAUSE: the required correctness condition was absent from S0; a deterministic gate cannot recover missing semantic intent.
- GUARDRAIL: reject empty/invalid contracts; bind N1 to exact S0; emit only bounded field facts; require operator review of required predicates. Do not relabel local PASS as whole-goal success.
- REGRESSION TEST: `test_poor_spec_can_pass_while_real_goal_fails_and_must_stay_bounded` reproduces weak-spec PASS and stronger-spec BLOCK; `test_bad_spec_cannot_pass_vacuously` covers mechanically invalid contracts.
- VERSION CHANGE: no version change; explicit limitation and guards in unreleased experiment 0.1.0. Semantic completeness remains UNKNOWN.

## F3 — adversarial fixture broke pytest on Windows

- FAILURE MODE: the 65,537-byte oversized-input parameter generated a huge test ID. Pytest setup and teardown raised `ValueError: the environment variable is longer than 32767 characters`; the test body did not run. First run: 35 passed, 2 errors.
- ROOT CAUSE: pytest placed the full automatic parameter ID into `PYTEST_CURRENT_TEST`, exceeding the Windows environment-variable limit.
- GUARDRAIL: explicit short parameter IDs for binary/large hostile inputs.
- REGRESSION TEST: `test_invalid_evidence_is_unknown[oversized]`, rerun as part of the passing experiment suite after shortening IDs.
- VERSION CHANGE: no version change; test harness correction inside unreleased experiment 0.1.0.

## F4 — exponent overflow escaped the G1 API

- FAILURE MODE: JSON `1e9999` parsed to an infinite float; comparing it crashed `g1` with `ValueError: Out of range float values are not JSON compliant: inf` instead of producing UNKNOWN. The targeted test failed before the correction.
- ROOT CAUSE: `parse_constant` rejects explicit NaN/Infinity tokens but does not catch numeric exponent overflow in the normal JSON float parser.
- GUARDRAIL: bounded JSON readers now use a float parser that rejects nonfinite results during evidence collection. Invalid evidence remains UNKNOWN.
- REGRESSION TEST: `test_overflowing_json_number_is_unknown_without_api_crash`, observed failing before the correction and passing afterward. Final full run is recorded in the handoff/evidence.
- VERSION CHANGE: no version change; fix contained in unreleased experiment 0.1.0, existing package/core stays 2.1.2.

## Other attacks exercised

Missing sources/fields, partial evidence, stale/future content timestamps,
changed pinned content, mutation between reads, eligible contradictory sources,
candidate FACT/approval/evidence injection, omitted/duplicate predicate IDs,
contract substitution, Boolean/number confusion, invalid/duplicate-key JSON,
instruction strings in evidence and path traversal. These are intentionally
hostile inputs with asserted outcomes, not additional observed production bugs.

Residual risks: dishonest operator-owned sources/specification, clock trust,
post-final-read mutations and ABA races; no process security sandbox; no real
model integration. No rollback was performed.
