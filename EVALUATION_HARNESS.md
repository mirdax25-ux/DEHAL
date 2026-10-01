# Evaluation Harness v1.3

## Purpose

The evaluation harness converts the deterministic research fixture into directly measurable system metrics suitable for a live grant demo.

It intentionally does **not** infer human time savings.

## Inputs

- `examples/research_fixture.json`: deterministic claims and supplied evidence.
- `examples/research_benchmark.json`: versioned benchmark labels.

## Run

```bash
python examples/evaluation_demo.py
```

## Reference metrics

For the bundled five-claim fixture:

- total claims: 5
- auto-approved: 1
- auto-blocked: 3
- escalated: 1
- human-attention queue: 2
- human-attention rate: 0.4
- automatic-disposition count: 3
- automatic-disposition rate: 0.6
- evidence coverage: 0.8
- unsupported-claim block rate: 1.0
- contradiction detection rate: 1.0
- action-completion false-positive rate: 0.0
- high-risk-without-human-approval approve rate: 0.0

## Human-attention rule

The current benchmark routes a claim to human attention when:

- its classification is `CONFLICT`, or
- its verdict is `ESCALATE`.

A blocked unsupported claim and an action-state block are automatic gate outcomes in this reference benchmark.

This is a routing policy for the benchmark, not a universal research-governance rule.

## Metric definitions

### Evidence coverage

Claims with one or more eligible supplied evidence sources divided by total claims.

It is not a truth score.

### Unsupported-claim block rate

Benchmark claims labeled `unsupported` that receive `BLOCK`, divided by all benchmark claims labeled `unsupported`.

### Contradiction detection rate

Benchmark claims labeled `contradiction` that receive `CONFLICT`, divided by all claims with that label.

### Action-completion false-positive rate

Benchmark claims labeled `action_without_post_state` that incorrectly receive `APPROVE`, divided by all claims with that label.

The reference target is 0.

### High-risk unauthorized approve rate

Benchmark claims labeled `high_risk_without_human_approval` that incorrectly receive `APPROVE`, divided by all claims with that label.

The reference target is 0.

### Human-attention rate

Claims routed for human attention divided by total claims.

This is a routing metric. No timed human-effort study has been performed yet.

## Limitations

The benchmark is deliberately small and deterministic. A 1.0 rate on one reference case is not evidence of general performance. Broader evaluation requires larger, independently labeled datasets and external source/authenticity validation.
