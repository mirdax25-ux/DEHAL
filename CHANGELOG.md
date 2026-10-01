# Changelog

## v1.2.0 — Research-Agent Evidence Demo candidate

### Added
- Deterministic `run_research_demo(...)` orchestration layer.
- Human-readable report split into VERIFIED FACTS, UNKNOWN/BLOCKED, CONFLICTS, ACTION GATE BLOCKS and ESCALATIONS.
- Measurement output including evidence coverage and blocked unsupported-claim count.
- Reproducible `examples/research_fixture.json`.
- Runnable `examples/research_demo.py`.
- CI research-demo smoke on Python 3.10, 3.11 and 3.13.

### Verification
- TDD RED 1: PR CI failed with `ModuleNotFoundError: bodulskihal_core.research_demo`.
- GREEN 1: implementation produced 45/45 passing tests.
- TDD RED 2: reproducibility test failed with `FileNotFoundError` for the intentionally missing fixture.
- GREEN 2: bundled fixture produced 46/46 passing tests.
- GitHub CI run 36813448513 passed install, compile, 46 tests, original demo smoke and research-demo smoke on Python 3.10, 3.11 and 3.13.
- Independent research-demo code review reported 0 issues.

### Failure → Evolution

#### BH-RD-001 — Research demo did not exist
- FAILURE MODE: new specification tests could not import `bodulskihal_core.research_demo`.
- ROOT CAUSE: behavior was specified before implementation by TDD.
- GUARDRAIL: implement only against the failing acceptance tests.
- REGRESSION TEST: `tests/test_research_demo.py`.
- VERSION CHANGE: package milestone v1.2.

#### BH-RD-002 — Fixture was not reproducible from repository
- FAILURE MODE: fixture reproduction test failed with `FileNotFoundError`.
- ROOT CAUSE: expected fixture intentionally did not exist during RED.
- GUARDRAIL: keep a versioned deterministic fixture in `examples/`.
- REGRESSION TEST: `tests/test_research_fixture.py`.
- VERSION CHANGE: reproducible demo artifact added.

## v1.1.0 — JSON adapter

- Added strict JSON single/compound adapters and schema v1.
- Added 10 adapter behavior/negative tests.
- Added 256 adapter/core differential comparisons.
- GitHub CI validated package installation, compile, 40 tests and demo smoke on Python 3.10, 3.11 and 3.13.

## v1.0.0 — Core reference implementation

- Added deterministic FACT / INFERENCE / ESTIMATE / UNKNOWN / CONFLICT classification.
- Added APPROVE / BLOCK / ESCALATE verdicts.
- Added freshness, directness, contradiction, action-state and human gates.
- Added compound verification, evidence receipts and failure-evolution records.
