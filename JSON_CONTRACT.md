# BodulskiHal JSON Contract v1

The JSON adapter is a transport boundary for the deterministic core. It performs strict input parsing and delegates verdict logic to the unchanged core engine.

## Single-claim request

```json
{
  "claim": {
    "id": "send-1",
    "text": "Email sent",
    "type": "action_state",
    "risk": "low",
    "consequential": true
  },
  "evidence": [
    {
      "source_id": "provider-final-state",
      "supports": true,
      "observed_at": "2026-10-01T03:50:00+00:00",
      "directness": "direct",
      "post_action": true,
      "eligible": true
    }
  ],
  "policy": {
    "version": "1.0",
    "max_age_seconds": 300,
    "reject_future_evidence": true
  },
  "evaluation_time": "2026-10-01T03:50:00+00:00",
  "human_approved": false
}
```

## Single-claim response

The response is JSON-safe and contains:

- `schema_version`
- `algorithm_version`
- `classification`
- `verdict`
- `reason`
- `receipt`
- `failure_record`

## Compound request

Use `claims`, `evidence_by_claim`, optional `human_approvals`, one shared `policy`, and one shared `evaluation_time`.

Unknown evidence-map or approval-map claim IDs are rejected rather than silently ignored.

## Fail-closed boundary rules

- Required strings must be present and non-empty.
- Boolean fields must be actual JSON booleans; `0` and `1` are rejected.
- `max_age_seconds` must be an integer and is still checked by the core for non-negativity.
- Datetimes must be ISO 8601 and timezone-aware. `Z` is accepted as UTC.
- Unknown enum values are rejected.
- Core duplicate-source and duplicate-claim protections remain active.

The adapter does not fetch URLs, read files, authenticate sources, or perform external actions.
