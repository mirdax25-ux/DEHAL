# DEHAL v2 reference architecture

This page describes the implementation in [`v2_reference/dehal_core.py`](../v2_reference/dehal_core.py). The core evaluates a claim against a supplied evidence snapshot; fetching evidence and choosing the evaluation time are responsibilities of the caller.

## Deterministic evaluation

`dehal_evaluate` accepts a claim, an `evaluation_time`, and a list of evidence records. The core does not fetch sources or read the current time. For the same inputs, it applies the same checks and constructs the same provenance value.

The evaluation order is:

1. Invalid input returns `BLOCK` with `R_INVALID_INPUT`.
2. An empty evidence snapshot returns `BLOCK` with `R_NO_EVIDENCE_FAIL_CLOSED`.
3. Any evidence record with flags results in `ESCALATE`.
4. Evidence content beginning with `CONTRADICTS:` results in `BLOCK`.
5. Otherwise, a case-insensitive occurrence of the normalized claim in evidence content results in `APPROVE`; unsupported claims result in `ESCALATE`.

This is a deterministic check over supplied text. It does not certify the authenticity or truth of the source itself.

## LLM boundary and grounding veto

The optional `llm_proposal` input accepts only `ESCALATE`. Other proposal values are rejected and do not produce an approval. A valid escalation proposal can move a non-`BLOCK` result to `ESCALATE`, but cannot override a grounding `BLOCK`. The grounding decision therefore retains veto authority.

## Fail-closed behavior and provenance

Missing or malformed required inputs and an empty evidence snapshot do not produce an approval. Contradictions block; flagged or unsupported evidence escalates.

For evaluated inputs, `provenance_sha256` is SHA-256 over the core version, supplied evaluation time, trimmed claim, and sorted evidence SHA-256 values. The output also includes the reasons, evaluation time, and core version. Invalid input returns an empty provenance string because no evaluation was performed.
