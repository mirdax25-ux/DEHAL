# BodulskiHal

Evidence-first verification for AI/agent claims.

## Versions

- **Core algorithm:** v1.0.0
- **JSON transport adapter:** schema v1
- **Package:** v1.3.0
- **Research-Agent Evidence Demo:** v1.2
- **Evaluation Harness / Grant Metrics:** v1.3

## Core rule

`CONFIDENCE <= EVIDENCE`

Atomic claims are classified as:

- `FACT`
- `INFERENCE`
- `ESTIMATE`
- `UNKNOWN`
- `CONFLICT`

Verdicts are:

- `APPROVE`
- `BLOCK`
- `ESCALATE`

## Hard gates

1. Missing eligible evidence cannot become `FACT`.
2. Eligible contradiction yields `CONFLICT`.
3. `INFERENCE` and `ESTIMATE` do not masquerade as `FACT`.
4. Action completion requires fresh, direct post-action/final-state evidence.
5. High-risk claims require human approval before `APPROVE`.
6. Compound verification requires every consequential clause to pass.
7. Duplicate evidence/claim identities are rejected.
8. Naive timestamps, invalid freshness windows and empty compounds fail closed.

## JSON adapter

Use `verify_payload(...)` and `verify_compound_payload(...)`.

The adapter validates supplied JSON-shaped evidence and delegates verdict logic to the core. It does not fetch or authenticate arbitrary external sources.

## Research-Agent Evidence Demo

Run:

```bash
python examples/research_demo.py
```

The bundled deterministic fixture demonstrates:

- supported → `FACT / APPROVE`
- missing evidence → `UNKNOWN / BLOCK`
- contradiction → `CONFLICT / BLOCK`
- action without final-state proof → `FACT / BLOCK`
- high-risk fact without human approval → `FACT / ESCALATE`

See `RESEARCH_DEMO.md`.

## Evaluation Harness

Run:

```bash
python examples/evaluation_demo.py
```

The v1.3 benchmark reports directly measurable system metrics:

- automatic disposition rate
- human-attention queue/rate
- evidence coverage
- unsupported-claim block rate
- contradiction detection rate
- action-completion false-positive rate
- high-risk-without-human-approval approve rate

The bundled five-claim reference benchmark currently yields:

- automatic disposition rate: **0.6**
- human-attention rate: **0.4**
- evidence coverage: **0.8**
- unsupported-claim block rate: **1.0**
- contradiction detection rate: **1.0**
- action-completion false-positive rate: **0.0**
- high-risk-without-human-approval approve rate: **0.0**

These are results on a tiny deterministic reference fixture, not general performance claims.

No timed human-effort study has yet been performed.

See `EVALUATION_HARNESS.md`.

## Tests

```bash
python -m pytest
```

The v1.3 candidate contains 53 tests before final packaging/doc CI.

## Determinism boundary

Receipt determinism requires the same normalized inputs, policy version and explicit `evaluation_time`. Freshness is time-dependent.

## Status boundary

This repository verifies a bounded reference implementation, deterministic research fixture and benchmark harness.

It does **not** prove:

- all hallucinations can be detected,
- supplied external evidence is authentic,
- benchmark rates generalize beyond the defined fixture,
- actual human reviewer time savings,
- the complete BodulAI ecosystem is production ready,
- arbitrary live research workflows are already verified end-to-end.
