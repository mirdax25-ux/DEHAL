# Research-Agent Evidence Demo v1.2

## Purpose

Provide a small, reproducible demonstration of how a research agent's claims can be separated by evidence state instead of being presented as one confident narrative.

The demo is deliberately offline and deterministic.

## Pipeline

```
Research request
  ↓
Bounded claims
  ↓
Supplied evidence by claim
  ↓
JSON adapter
  ↓
B.1.2 core
  ↓
Per-claim evidence receipt
  ↓
Metrics + human-readable report
```

## Reproduce

After installing the package:

```bash
python examples/research_demo.py
```

The script reads:

`examples/research_fixture.json`

## Expected fixture outcomes

| Claim | Classification | Verdict | Reason |
|---|---|---|---|
| supplied study record exists | FACT | APPROVE | fresh direct support |
| second claim is supported | UNKNOWN | BLOCK | no eligible evidence |
| two supplied sources agree | CONFLICT | BLOCK | eligible contradiction |
| external research export completed | FACT | BLOCK | no post-action/final-state evidence |
| high-risk publication action is ready | FACT | ESCALATE | human approval required |

## Expected metrics

- total claims: 5
- verified facts: 1
- unknown blocked: 1
- conflicts blocked: 1
- action-gate blocks: 1
- escalations: 1
- blocked unsupported claims: 1
- evidence coverage: 0.8

## Interpretation

`evidence_coverage = claims with at least one eligible source / total claims`.

This metric does not measure source truth, source independence, research quality or semantic correctness. It measures only the bounded evidence coverage exposed by this demo.

## Grant relevance

This artifact demonstrates:

- visible provenance/evidence state,
- uncertainty preservation,
- contradiction handling,
- action-state verification,
- human escalation,
- machine-readable receipts,
- a human-readable research summary,
- measurable evidence coverage.

It is a demonstrator, not a production deployment and not a claim of general hallucination elimination.
