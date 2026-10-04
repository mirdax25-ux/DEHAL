# Failure log

## F1 — S1 overreached into S2 semantics

**Failure mode:** A global anchor bound to a different state version produced BLOCK during S1 integrity validation, while the intended architecture requires this semantic/global-evidence condition to become UNKNOWN in S2.

**Root cause:** The initial S1 implementation checked global_anchor.state_version == current_state.version. This mixed S1's integrity/provenance responsibility with S2's global-goal/freshness decision.

**Guardrail:** S1 only checks checkpoint/transition/current-state/policy/provenance integrity. Global-anchor independence, scope, status and state-version semantics are evaluated only by S2.

**Regression test:** test_global_goal_never_inferred_from_contract_pass includes a stale anchor and requires contract_status=PASS with terminal_status=UNKNOWN.

**Version change:** Experiment remains 0.1.0; this was corrected before branch publication and no production version is claimed.

## F2 — unresolved loop/final-N2 dissent was dropped before S2

**Failure mode:** The checkpoint recorded `loop_status` and the final N2 receipt, but S2 used only S1 integrity, contract and global-goal status. Reproduced live in the prototype: loop CONFLICT -> terminal PASS; loop UNKNOWN -> terminal PASS; final N2 CHALLENGE -> terminal PASS; final N2 UNKNOWN -> terminal PASS.

**Root cause:** N2 was treated as advisory provenance only, and its decision plus the loop terminal status were not included in S2's fail-closed status lattice.

**Guardrail:** C now records the final N2 decision/issues explicitly. S2 maps loop PASS/UNKNOWN/CONFLICT and final N2 CLEAR/UNKNOWN/CHALLENGE into terminal statuses and combines them with integrity, contract and global-goal statuses using fail-closed precedence. No unresolved dissent may disappear at C -> S1 -> S2.

**Regression test:** `test_loop_and_final_n2_statuses_reach_s2` covers the four reproduced failures. `test_final_n2_challenge_reaches_terminal_conflict` checks the direct CHALLENGE path.

**Version change:** experiment 0.1.0 -> **0.1.1**.

## F3 — caller could bypass the N1<->N2 loop with a forged plain loop_result

**Failure mode:** A caller could skip `n1_n2_loop`, construct `{"loop_status":"PASS","loop_root":"caller-forged-root","receipts":[]}`, obtain a valid final-N2 receipt and C checkpoint, and reach S2 terminal PASS.

**Root cause:** `final_n2` and `make_checkpoint` trusted plain caller-supplied loop fields. No trusted receipt bound the loop status, final candidate, transition and N2 receipt-chain root as one object.

**Guardrail:** `n1_n2_loop` now emits a signed/bound `LOOP/result` receipt containing transition hash, candidate hash, loop status, loop root and receipt count. `final_n2` and C independently verify that receipt and recompute the receipt-list root. The final N2 receipt is parent-bound to the authoritative loop receipt. S1 verifies the loop receipt again inside C.

**Regression test:** `test_caller_cannot_bypass_loop_with_plain_forged_result` plus `test_loop_result_tamper_cannot_reach_final_n2` cover missing receipt, forged status/root/candidate, removed review receipts and modified MAC.

**Version change:** experiment 0.1.1 -> **0.1.2**.

## Known unresolved boundary — wrong specification

A valid transition, intact checkpoint, PASS S1, PASS S2 implementation and exact-action executor can still enforce a semantically wrong/incomplete policy if the trusted starting specification itself is wrong. This is not classified as fixed. The architecture must preserve bounded claims and use UNKNOWN when independent semantic grounding is unavailable.
