# BodulskiHal — Catalyst 2026 Evidence Sheet

## Current implementation evidence

Repository: `mirdax25-ux/Brutala-Hal-`

Current main merge commit for v1.3:
`393a40fec19259ffd1ea7990851cde46af173ce5`

Current package version on `main`:
`1.3.0`

Verified main artifacts:
- `bodulskihal_core/engine.py`
- `bodulskihal_core/adapter.py`
- `bodulskihal_core/research_demo.py`
- `bodulskihal_core/evaluation.py`
- `examples/research_fixture.json`
- `examples/research_benchmark.json`
- `examples/research_demo.py`
- `examples/evaluation_demo.py`
- `EVIDENCE_MANIFEST.json`

## Fresh CI evidence

Final PR-head CI run before v1.3 merge:
`36823577016`

Matrix:
- Python 3.10 — SUCCESS
- Python 3.11 — SUCCESS
- Python 3.13 — SUCCESS

Each job passed:
1. package installation
2. compile
3. 53 tests
4. original demo smoke
5. research demo smoke
6. evaluation harness smoke

Independent evaluation-layer code review:
0 reported issues.

## TDD failure evidence

The project intentionally records failures before fixes.

### BH-EVAL-001
RED:
`ModuleNotFoundError: No module named 'bodulskihal_core.evaluation'`

Evolution:
tests specified the evaluation contract before implementation.

### BH-EVAL-002
First GREEN candidate:
`1 failed, 52 passed`

Failure:
the human-facing benchmark summary repeated a risky performance phrase inside its disclaimer.

Guardrail:
the summary now states only that no timed human-effort result has been measured.

Final:
53/53 tests PASS.

## Reference benchmark

Fixture size:
5 deterministic claims.

Measured result:
- auto-approved: 1
- auto-blocked: 3
- escalated: 1
- automatic disposition rate: 0.60
- human-attention queue: 2
- human-attention rate: 0.40
- evidence coverage: 0.80
- unsupported-claim block rate: 1.00
- contradiction detection rate: 1.00
- action-completion false-positive rate: 0.00
- high-risk-without-human-approval approve rate: 0.00

Human attention IDs:
- `conflict`
- `high-risk`

## Scope boundary

These numbers are only results for the bundled five-claim deterministic benchmark.

They do not establish:
- general hallucination-detection performance,
- authenticity or authority of arbitrary supplied evidence,
- generalization to other research domains,
- measured human labor reduction,
- production readiness of the full BodulAI ecosystem.

## Current product-stage wording

Recommended:
“working reference prototype with deterministic research demo and evaluation harness”

Avoid:
“production-ready”
“solves hallucinations”
“verified for all research”
“reduces reviewer time by X%”
