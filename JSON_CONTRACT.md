# BodulskiHal JSON Contract — schema v3

Schema v3 keeps the deterministic JSON adapter boundary and adds epistemic metadata needed by the real conversation benchmark.

## Single-claim request

```json
{
  "claim": {
    "id": "count-1",
    "text": "Conversation has 30 questions",
    "type": "observation",
    "risk": "low",
    "consequential": true,
    "authority_scope": "external_fact",
    "answerability": "answerable"
  },
  "evidence": [
    {
      "source_id": "count-tool",
      "evidence_id": "count-tool-1",
      "supports": true,
      "observed_at": "2026-10-03T21:30:00+00:00",
      "directness": "direct",
      "post_action": false,
      "eligible": true,
      "source_role": "external",
      "source_ref": "tool://conversation-counter",
      "independence_group": "conversation-counter",
      "origin": "tool_observation",
      "authority_scope": "external_fact"
    }
  ],
  "policy": {
    "version": "3.0",
    "max_age_seconds": 300,
    "reject_future_evidence": true,
    "require_independent_action_evidence": true,
    "medium_risk_min_independent_sources": 2,
    "require_runtime_provenance": false
  },
  "evaluation_time": "2026-10-03T21:30:00+00:00",
  "human_approved": false
}
```

New claim fields are optional in the Python adapter and default fail-safely to:
- `authority_scope = external_fact`
- `answerability = answerable`

New evidence fields are optional and default to:
- `origin = external_source`
- `authority_scope = external_fact`
- `independence_group = null`

For source-independence quorum, eligible direct supporting evidence is grouped by
shared `source_id`, `source_ref`, or `independence_group`, including transitive
overlap. Values are trimmed and compared within their own field namespace.
Optional metadata can merge identities; it cannot split a known source into
independent votes. Different group labels on the same provenance reference still
count as one group. No URL canonicalization or external source authentication is
implied by this deterministic comparison.

The ingestion evidence boundary accepts the same optional `independence_group`
field. The Python ingestion API requires a real `TypeAuthority` enum member;
strings and other runtime values are rejected before claim typing. Lifecycle
checkpoint/approval flags likewise require actual booleans.

## Classification

Schema v3 supports:
- FACT
- INFERENCE
- ESTIMATE
- UNKNOWN
- REFUTED
- CONFLICT

Pure eligible counterevidence is REFUTED. Mixed supporting and contradicting evidence is CONFLICT.

## Evidence origin

Allowed values:
- external_source
- tool_observation
- computed_result
- memory
- user_assertion
- user_self_report
- user_preference
- user_instruction

## Authority scope

Allowed values:
- external_fact
- system_state
- user_self_report
- user_preference
- user_instruction

A user assertion is not sufficient evidence for an external fact merely because it was supplied by the caller.

## Answerability

Allowed values:
- answerable
- partially_answerable
- underspecified
- false_premise
- contradictory_input
- needs_clarification
- out_of_scope

Non-answerable claims fail closed before ordinary fact approval. `needs_clarification` escalates.

## Runtime provenance

Every receipt contains runtime provenance fields. A policy may set:

`require_runtime_provenance = true`

Then the verifier requires:
- `BODULSKIHAL_SOURCE_COMMIT`
- `BODULSKIHAL_SOURCE_REF`
- `BODULSKIHAL_BUILD_ID`

to identify a verified build.

## Compound request

Use `claims`, `evidence_by_claim`, optional `human_approvals`, one shared policy and one evaluation time.

Unknown claim ids in evidence or approval maps are rejected.

## Fail-closed boundary rules

- Required strings must be non-empty.
- Boolean fields must be actual booleans.
- Datetimes must be ISO 8601 and timezone-aware.
- Evidence/claim identities must be unique.
- Provenance enum values must be known.
- Content SHA-256, when supplied, must be a valid 64-character hexadecimal digest.
- Memory and user-origin evidence are subject to authority policy; origin does not imply truth.
- The adapter does not fetch URLs, authenticate arbitrary external sources or perform external actions.

## Conversation contract

Conversation goal/referent/constraint verification is exposed through `conversation_gate.py` as a deterministic internal gate. Semantic extraction of those fields is upstream work for BodulLogic/PRECICA or another preparation layer.
