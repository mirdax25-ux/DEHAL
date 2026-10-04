# Failure log

## F1 — S1 overreached into S2 semantics

**Failure mode:** A global anchor bound to a different state version produced BLOCK during S1 integrity validation, while the intended architecture requires this semantic/global-evidence condition to become UNKNOWN in S2.

**Root cause:** The initial S1 implementation checked global_anchor.state_version == current_state.version. This mixed S1's integrity/provenance responsibility with S2's global-goal/freshness decision.

**Guardrail:** S1 only checks checkpoint/transition/current-state/policy/provenance integrity. Global-anchor independence, scope, status and state-version semantics are evaluated only by S2.

**Regression test:** test_global_goal_never_inferred_from_contract_pass includes a stale anchor and requires contract_status=PASS with terminal_status=UNKNOWN.

**Version change:** Experiment remains 0.1.0; this was corrected before branch publication and no production version is claimed.

## Known unresolved boundary — wrong specification

A valid transition, intact checkpoint, PASS S1, PASS S2 implementation and exact-action executor can still enforce a semantically wrong/incomplete policy if the trusted starting specification itself is wrong. This is not classified as fixed. The architecture must preserve bounded claims and use UNKNOWN when independent semantic grounding is unavailable.
