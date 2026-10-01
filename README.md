# BodulskiHal Core Algorithm v1.0

Deterministic, evidence-first reference engine for AI/agent claim verification.

## Core rule

`CONFIDENCE <= EVIDENCE`

The engine classifies each atomic claim as one of:

- `FACT`
- `INFERENCE`
- `ESTIMATE`
- `UNKNOWN`
- `CONFLICT`

and returns one of:

- `APPROVE`
- `BLOCK`
- `ESCALATE`

## Hard gates

1. Missing eligible evidence cannot become `FACT`.
2. Eligible contradiction yields `CONFLICT`.
3. `INFERENCE` and `ESTIMATE` do not masquerade as `FACT`.
4. Action-completion claims require fresh, direct, post-action/final-state evidence.
5. High-risk claims require human approval before `APPROVE`.
6. Compound verification requires every consequential clause to pass.
7. Duplicate evidence identities and duplicate compound claim IDs are rejected.
8. Naive timestamps, negative freshness windows, and empty compounds fail closed.

## Determinism boundary

Receipt determinism is defined over the same normalized claim/evidence inputs, the same policy version **and the same `evaluation_time`**. Freshness is time-dependent, so `evaluation_time` is an explicit algorithm input.

## Example

```python
from datetime import datetime, timezone
from bodulskihal_core import (
    Claim, ClaimType, Directness, Evidence, Policy, verify_claim
)

now = datetime.now(timezone.utc)
result = verify_claim(
    Claim("send-1", "Email sent", ClaimType.ACTION_STATE),
    [
        Evidence(
            source_id="provider-final-state",
            supports=True,
            observed_at=now,
            directness=Directness.DIRECT,
            post_action=True,
        )
    ],
    policy=Policy(version="1.0", max_age_seconds=300),
    evaluation_time=now,
)

print(result.classification.value)  # FACT
print(result.verdict.value)         # APPROVE
print(result.receipt)
```

## JSON adapter (package v1.1.0)

The v1.1 package adds a strict transport adapter without changing the v1.0 core algorithm. Use `verify_payload(...)` or `verify_compound_payload(...)` for JSON-shaped input. See `JSON_CONTRACT.md`.

The adapter is deliberately offline: it parses and validates supplied data, then delegates to the deterministic core. It does not fetch or authenticate external sources.

## Tests

Run:

```bash
python -m pytest
```

Current source checkpoint includes:

- strict JSON adapter tests
- 128-case adapter/core differential check (256 human-gate comparisons)

- unit/negative tests
- deterministic receipt tests
- compound-gate tests
- timestamp/freshness boundary tests
- exhaustive 128-case boolean invariant test
- mutation checks for post-action and human-approval gates

## Status boundary

This package is a **reference implementation** of the v1.0 core verification algorithm. It is not, by itself, a claim that the complete BodulAI product, external integrations, deployment, or production environment are verified ready.
