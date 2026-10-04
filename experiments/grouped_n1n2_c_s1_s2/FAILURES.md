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

## F4 — caller could self-assert an "independent" global anchor

**Failure mode:** A plain caller-supplied JSON anchor such as `{"status":"PASS","independent":true,"scope":["goal"],"state_version":7}` was accepted into the transition and could yield global-goal PASS without any separate provenance proving who issued the anchor.

**Root cause:** `validate_anchor` checked shape and semantics only. The word `independent` was trusted as data instead of being bound to a distinct trust root.

**Guardrail:** Version 0.1.3 introduces a separate global-anchor receipt signed with a distinct anchor trust key. S-boundary verifies that receipt before marking the anchor provenance-verified. S1 revalidates anchor-receipt integrity inside C, and S2 allows global PASS only when the anchor receipt is valid, payload-matched, in-scope, current and marked independent. A raw self-asserted anchor without receipt is allowed only as untrusted context and yields global UNKNOWN.

**Regression test:** `test_self_asserted_independent_anchor_without_receipt_stays_unknown`, `test_tampered_global_anchor_receipt_rejected`, `test_global_anchor_receipt_from_wrong_trust_root_rejected`, and `test_global_anchor_receipt_payload_mismatch_rejected`.

**Version change:** experiment 0.1.2 -> **0.1.3**.

## F5 — evidence_root was an unauthenticated label

**Failure mode:** A caller could set `evidence_root="no-real-evidence"` without any evidence receipt. The transition, checkpoint and S1 all accepted the label, and the system reached terminal PASS despite no provenance proving that the root came from an evidence authority.

**Root cause:** The transition bound the evidence-root string cryptographically after receipt creation, but did not authenticate who supplied that root. S1 therefore checked continuity of an untrusted label rather than evidence provenance.

**Guardrail:** Version 0.1.4 introduces a distinct evidence-authority receipt and trust key. The receipt binds `evidence_root + state_version + contract_hash`. S-boundary validates the receipt before marking evidence provenance verified; C carries it forward; S1 re-verifies it. Missing evidence receipt yields S1 UNKNOWN; wrong key, tampering or binding mismatch fail closed.

**Regression test:** `test_self_asserted_evidence_root_without_receipt_stays_unknown`, `test_tampered_evidence_receipt_rejected`, `test_evidence_receipt_from_wrong_trust_root_rejected`, and `test_evidence_receipt_binding_mismatch_rejected`.

**Version change:** experiment 0.1.3 -> **0.1.4**.

## Known unresolved boundary — wrong specification

A valid transition, intact checkpoint, PASS S1, PASS S2 implementation and exact-action executor can still enforce a semantically wrong/incomplete policy if the trusted starting specification itself is wrong. This is not classified as fixed. The architecture must preserve bounded claims and use UNKNOWN when independent semantic grounding is unavailable.
