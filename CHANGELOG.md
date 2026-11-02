# Changelog

## v2.1.2 — Integrated boundary and quorum hardening

Continues the merged MAIN + v2 CORE + RAW PIPELINE + INGESTION + GUARD LOOP
integration on `integration/b-1-2-benchmark-20261004`. JSON schema stays 3;
the live Floot/native transport is outside this repository change.

### Failure → Evolution

- **BH-TYPE-AUTHORITY-003**
  - FAILURE MODE: a string or other non-enum authority could promote an executor-declared observation to FACT/APPROVE.
  - ROOT CAUSE: enum identity comparison assumed callers obeyed Python annotations.
  - GUARDRAIL: require a real `TypeAuthority` before clause typing.
  - REGRESSION TEST: malformed authority inputs through typing and ingestion verification, with valid executor/trusted-authority controls.
  - VERSION CHANGE: package/algorithm 2.1.1 → 2.1.2.
- **BH-INGESTION-GROUP-003**
  - FAILURE MODE: ingestion rejected the core's `independence_group` evidence field.
  - ROOT CAUSE: the earlier adapter addition did not update the ingestion allowlist and constructor.
  - GUARDRAIL: validate and preserve optional independence metadata through ingestion.
  - REGRESSION TEST: valid groups survive to receipts; malformed groups fail; omitted groups remain compatible.
  - VERSION CHANGE: 2.1.2 ingestion contract correction, schema remains 3.
- **BH-INDEPENDENCE-003**
  - FAILURE MODE: adding different group labels or optional references split a known source into independent quorum votes.
  - ROOT CAUSE: choosing one priority identity discarded overlapping provenance identifiers.
  - GUARDRAIL: count connected groups sharing source IDs, references or group labels; metadata can only merge known identities.
  - REGRESSION TEST: `test_independence_alias_regressions.py` covers conflicting labels, partial metadata, source aliases, transitive overlap, all input orders and separate namespaces.
  - VERSION CHANGE: 2.1.2 quorum semantics tightened.
- **BH-LIFECYCLE-BOOL-003**
  - FAILURE MODE: truthy strings/integers could satisfy freeze checkpoint or freeze/reopen human approval gates.
  - ROOT CAUSE: lifecycle transitions used truthiness and receipt coercion instead of validating boolean types.
  - GUARDRAIL: reject non-booleans before transition dispatch, including idempotent paths.
  - REGRESSION TEST: `test_lifecycle_runtime_types.py` exercises invalid inputs across ACTIVE/FROZEN paths and preserves boolean behavior.
  - VERSION CHANGE: 2.1.2 lifecycle input validation correction.

Validation records belong to the tested commit's PR/CI and external test artifacts;
this entry alone is not proof of a passed run or live deployment.

## v2.1.1 ? Source-independence hardening

### Fixed
- Medium-risk quorum no longer treats two aliases of the same provenance reference as two independent sources.
- Added optional `independence_group` to evidence. When present it is the primary independence identity; otherwise `source_ref`, then `source_id`, is used.
- Verification receipts now report `independent_supporting_group_count` and preserve each evidence item's `independence_group`.

### Failure ? Evolution
- BH-INDEPENDENCE-002 ? different source IDs pointing to the same source reference could satisfy an independence quorum.
- ROOT CAUSE: quorum counted caller-provided `source_id` values rather than provenance identity.
- GUARDRAIL: independence quorum is computed from `independence_group`, falling back to `source_ref`, then `source_id`.
- REGRESSION TESTS: aliased identical `source_ref` must remain one independent group; explicit same groups collapse; distinct groups can satisfy quorum.
- VERSION CHANGE: algorithm/package 2.1.0 ? 2.1.1.

## v2.1.0 ? Integrated deterministic verification candidate

### Integrated
- MAIN + v2 core algorithm + raw-response evidence pipeline + ingestion pipeline + Guard Loop.
- Strict human-approval, provenance-identifier and runtime boolean hardening.
- Exact Floot rc.3 source snapshot and SHA-256 manifest for audit continuity.

### Added from the real conversation benchmark
- `REFUTED` classification for pure eligible counterevidence.
- Evidence `origin` and `authority_scope`; user assertions no longer certify external facts by themselves.
- Claim `answerability` and deterministic fail-closed handling for underspecified, false-premise, contradictory, clarification and out-of-scope states.
- Structured `UnknownRecord` with severity, reviewed/resolved/blocking separation.
- Deterministic conversation contract gate for goal, referent and active constraints.
- Runtime source/build provenance receipt and optional hard gate.
- Benchmark regression suite covering anchoring, referent drift, language/constraint persistence, counterevidence semantics, source independence and provenance.

### Compatibility
- Algorithm v2.1.0 and JSON schema v3.
- New claim/evidence metadata has backward-compatible defaults inside the Python adapter.
- Live Floot/native rc.3 transport is not modified by this integration candidate.

### Verification so far
- Local integrated suite: 208/208 PASS before GitHub CI.
- `compileall` PASS.
- `git diff --check` PASS.
- Independent expert review of `engine.py`, `guard_loop.py` and `conversation_gate.py`: 0 issues reported.
- GitHub CI and live deployment remain required before merge/release.

### Failure ? Evolution
- BH-REFUTED-001: UNKNOWN could hide direct refutation ? add REFUTED.
- BH-AUTHORITY-001: user anchor could be represented as supplied fact ? add origin/authority gate.
- BH-UNKNOWN-BLOCK-001: reviewed did not mean resolved ? add structured blocking unknowns.
- BH-REFERENT-001: wrong active referent could survive to final answer ? add conversation contract gate.
- BH-PROVENANCE-001: live build lacked immutable Git/build binding ? add runtime provenance receipt/gate.

## v1.3.1 — Strict Human-Approval Gate

### Fixed
- High-risk verification now rejects non-boolean `human_approved` values instead of accepting truthy objects or strings.
- Compound verification no longer coerces approval values through `bool(...)`; each supplied approval must be an actual boolean.

### Verification
- TDD RED: PR CI run 36979300994 failed on Python 3.10, 3.11 and 3.13.
- RED evidence: 2 failed / 66 passed because non-boolean approval inputs did not raise `TypeError`.
- GREEN: PR CI run 36979396967 passed on Python 3.10, 3.11 and 3.13.
- GREEN suite: 68/68 tests on Python 3.10.

### Failure → Evolution

#### BH-GATE-001 — Truthy non-boolean value could satisfy the human-approval gate
- FAILURE MODE: values such as `"yes"`, `1`, or compound-map string `"false"` could be treated as approved because Python truthiness / `bool(...)` was accepted.
- ROOT CAUSE: the core approval boundary relied on truthiness instead of exact boolean type validation.
- GUARDRAIL: human approval is valid only when `type(value) is bool`; compound values are validated before verification and are no longer coerced.
- REGRESSION TESTS: `test_high_risk_rejects_non_boolean_human_approval` and `test_compound_rejects_non_boolean_human_approval_values`.
- VERSION CHANGE: package v1.3.0 → v1.3.1.

## v1.3.0 — Evaluation Harness / Grant Metrics candidate

### Added
- Deterministic `evaluate_benchmark(...)` evaluator.
- Versioned `examples/research_benchmark.json` labels.
- Runnable `examples/evaluation_demo.py`.
- Direct metrics for automatic disposition, human attention, evidence coverage, unsupported claims, contradictions and false-positive approval risks.
- `EVALUATION_HARNESS.md` with explicit formulas and limitations.
- CI evaluation-harness smoke.

### Verification
- TDD RED: GitHub CI failed with `ModuleNotFoundError: b_1_2_core.evaluation`.
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
- FAILURE MODE: specification tests could not import `b_1_2_core.evaluation`.
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
