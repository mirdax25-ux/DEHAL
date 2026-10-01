# Changelog

## v1.3.0 — Evaluation Harness / Grant Metrics candidate

### Added
- Deterministic `evaluate_benchmark(...)` evaluator.
- Versioned `examples/research_benchmark.json` labels.
- Runnable `examples/evaluation_demo.py`.
- Direct metrics for automatic disposition, human attention, evidence coverage, unsupported claims, contradictions and false-positive approval risks.
- `EVALUATION_HARNESS.md` with explicit formulas and limitations.
- CI evaluation-harness smoke.

### Verification
- TDD RED: GitHub CI failed with `ModuleNotFoundError: bodulskihal_core.evaluation`.
- First GREEN candidate exposed a grant-facing wording regression: test correctly rejected the literal phrase prohibited from the summary; CI showed 1 failed / 52 passed.
- Wording guardrail fixed the output to state only that no timed human-effort result has been measured.
- GREEN suite: 53/53 tests.
- GitHub CI run 36823378550 passed on Python 3.10, 3.11 and 3.13.
- Independent evaluation-harness code review reported 0 issues.

### Reference benchmark results
- total claims: 5
- auto-approved: 1
- auto-blocked: 3
- escalated: 1
- human-attention queue: 2
- human-attention rate: 0.4
- automatic-disposition rate: 0.6
- evidence coverage: 0.8
- unsupported-claim block rate: 1.0
- contradiction detection rate: 1.0
- action-completion false-positive rate: 0.0
- high-risk unauthorized approve rate: 0.0

### Failure → Evolution

#### BH-EVAL-001 — Evaluation layer missing
- FAILURE MODE: specification tests could not import `bodulskihal_core.evaluation`.
- ROOT CAUSE: TDD specification preceded implementation.
- GUARDRAIL: implement only after RED evidence.
- REGRESSION TEST: `tests/test_evaluation_harness.py`.

#### BH-EVAL-002 — Grant-facing wording contained a prohibited performance phrase
- FAILURE MODE: summary included wording that could be mistaken for a human-effort claim.
- ROOT CAUSE: disclaimer repeated the prohibited phrase while denying it.
- GUARDRAIL: benchmark summary states only that no timed human-effort result has been measured.
- REGRESSION TEST: `test_human_summary_does_not_claim_hours_saved`.

## v1.2.0 — Research-Agent Evidence Demo

- Added deterministic research demo, fixture, evidence receipts, metrics and human-readable state-separated report.
- Final PR-head CI: 46 tests PASS on Python 3.10, 3.11 and 3.13.

## v1.1.0 — JSON adapter

- Added strict JSON single/compound adapters and schema v1.
- Added 256 adapter/core differential comparisons.
- CI validated installation, compile, 40 tests and demo smoke on Python 3.10, 3.11 and 3.13.

## v1.0.0 — Core reference implementation

- Added deterministic FACT / INFERENCE / ESTIMATE / UNKNOWN / CONFLICT classification.
- Added APPROVE / BLOCK / ESCALATE verdicts.
- Added freshness, directness, contradiction, action-state and human gates.
- Added compound verification, evidence receipts and failure-evolution records.
