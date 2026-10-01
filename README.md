# BodulskiHal

Evidence-first verification for AI/agent claims.

## Versions

- **Core algorithm:** v1.0.0
- **JSON transport adapter:** schema v1
- **Package:** v1.2.0
- **Research-Agent Evidence Demo:** v1.2 milestone

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

Use:

- `verify_payload(...)`
- `verify_compound_payload(...)`

See `JSON_CONTRACT.md`.

The adapter does not fetch or authenticate external sources. It validates supplied JSON-shaped evidence and delegates verdict logic to the core.

## Research-Agent Evidence Demo

The v1.2 milestone adds a deterministic offline demonstrator:

```
RESEARCH REQUEST
→ CLAIMS
→ SUPPLIED EVIDENCE
→ BODULSKIHAL VERIFICATION
→ EVIDENCE RECEIPTS
→ METRICS
→ HUMAN-READABLE REPORT
```

Run:

```bash
python examples/research_demo.py
```

Bundled fixture:

`examples/research_fixture.json`

The fixture intentionally demonstrates five distinct outcomes:

- supported claim → `FACT / APPROVE`
- missing evidence → `UNKNOWN / BLOCK`
- contradictory evidence → `CONFLICT / BLOCK`
- action without final-state proof → `FACT / BLOCK`
- high-risk fact without human approval → `FACT / ESCALATE`

Metrics include:

- evidence coverage
- verified fact count
- unknown/blocked count
- conflict count
- action-gate block count
- escalation count
- blocked unsupported-claim count

See `RESEARCH_DEMO.md`.

## Tests

```bash
python -m pytest
```

Current v1.2 candidate evidence includes 46 tests and CI on Python 3.10, 3.11 and 3.13.

## Determinism boundary

Receipt determinism requires the same normalized inputs, policy version and explicit `evaluation_time`. Freshness is time-dependent.

## Status boundary

This repository verifies a bounded reference implementation and deterministic research fixture.

It does **not** prove:

- all hallucinations can be detected,
- external evidence is authentic merely because it was supplied,
- the complete BodulAI ecosystem is production ready,
- arbitrary live research workflows are already verified end-to-end.
