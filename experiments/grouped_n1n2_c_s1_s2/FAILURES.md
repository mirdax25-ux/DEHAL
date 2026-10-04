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


## F6 — policy drift after S2 could still execute

**Failure mode:** S2 could certify an action under policy P1, then policy could change to stricter P2 before execution while state/action remained unchanged. The executor checked state hash, action hash and nonce but did not receive or verify the current policy, so the previously certified action still returned EXECUTED even when P2 would BLOCK it.

**Root cause:** contract_hash was present in the S2 terminal receipt but was not enforced at the action boundary. This was a policy TOCTOU gap between decision and execution.

**Guardrail:** execute now requires the current policy, validates it, requires its canonical hash to equal the S2 contract_hash, and re-evaluates the action against the current state/policy before nonce consumption.

**Regression test:** test_executor_rejects_policy_drift_after_s2.

**Version change:** experiment 0.1.4 -> **0.1.5**.

## F7 — in-memory nonce state allowed replay after boundary restart

**Failure mode:** An S2-certified action executed once, then a new TrustedBoundary created with the same trust keys accepted the same old terminal receipt and executed it again because the old consumed_tokens set existed only in the previous process object.

**Root cause:** Replay protection was process-local rather than durable. Cryptographic receipt validity survived restart, but nonce-consumption state did not.

**Guardrail:** The executor now requires FileNonceLedger. Nonce consumption uses atomic exclusive file creation on a trusted local filesystem, so a new boundary/process using the same ledger directory observes the prior consumption. Missing/wrong ledger input fails closed.

**Regression tests:** test_file_nonce_ledger_blocks_replay_after_boundary_restart and test_executor_fails_closed_without_durable_ledger.

**Version change:** remains **0.1.5** in the same execution-boundary hardening batch.


## F8 — caller could rotate the S2 nonce and bypass durable replay protection

**Failure mode:** After one certified action executed, the same checkpoint/S1/state/policy could be submitted to S2 again with a fresh caller-provided action_nonce. S2 signed the new nonce, the durable ledger saw a new key, and the same action executed a second time even though the action hash and checkpoint were unchanged.

**Root cause:** The idempotency identity was caller-controlled. Durable storage cannot prevent duplicate effects when the caller can mint a new replay key for the same trusted operation.

**Guardrail:** Version 0.1.6 removes action_nonce from the S2 API. S2 derives a stable execution_token from the trusted goal identity: SHA-256 over the canonical object {"kind":"goal-execution","goal_id":...}. Re-certifying the same goal therefore yields the same token, and the file-backed ledger returns NOOP after the first execution. A genuinely new intended side effect must use a distinct trusted goal_id.

**Regression test:** test_s2_recertification_cannot_rotate_execution_token.

**Version change:** experiment 0.1.5 -> **0.1.6**.

## Known assumption — goal_id is the operation identity

The replay guarantee now depends on goal_id being stable and unique for one intended external side effect. If an upstream authority deliberately creates a new goal_id for the same real-world action, this layer cannot infer that the two goals are semantically duplicates. Production integration should issue goal/operation IDs from a trusted authority and preserve them through retries.

## Known unresolved execution boundary — external side-effect atomicity

The file ledger provides local at-most-once replay protection across process restart, but it is not a distributed transaction. A real external side effect and nonce-ledger commit cannot be made exactly-once by this prototype alone. Production integration must use an idempotent external operation or a transactionally coupled execution/idempotency store.

## Known unresolved boundary — wrong specification

A valid transition, intact checkpoint, PASS S1, PASS S2 implementation and exact-action executor can still enforce a semantically wrong/incomplete policy if the trusted starting specification itself is wrong. This is not classified as fixed. The architecture must preserve bounded claims and use UNKNOWN when independent semantic grounding is unavailable.

## F9 — transient combined-suite failure remains unexplained

**Failure mode:** One combined invocation of the pre-existing repository suite plus the grouped experiment produced a large experiment-only failure set, including apparently stale/incomplete anchor data. No source edit was intentionally performed during that invocation.

**Root cause:** **UNKNOWN.** The same combined scope subsequently passed twice in fresh pytest processes without a code change. The evidence therefore establishes a transient/flaky run, not a reproducible product defect and not a resolved cause.

**Guardrail:** Do not discard the failed observation. Keep experiment-only, pre-existing-plus-fuzz, pre-existing-plus-targeted, and full combined runs separable; require a fresh-process rerun after any anomalous combined result. Do not call the suite stable solely from one green run.

**Regression / challenge:** The exact combined scope was rerun twice in fresh pytest processes after the anomaly; both passed, with the latest reporting 736 passed. The new multiprocess nonce test independently passed with exactly one of 16 consumers succeeding.

**Version change:** none. No code change is justified without a reproducible failure or new causal evidence; experiment remains 0.1.6.

## F10 ? authenticated global anchor was replayable across goal or contract

**Failure mode:** A correctly authenticated PASS anchor was bound to state version and generic goal scope, but not to the exact goal identity or executable contract. The same signed anchor could therefore be reused for another goal or a changed policy while the local state version remained unchanged.

**Root cause:** Anchor provenance proved who signed the payload, but the payload did not carry goal identity or contract hash. Authentication without context binding permitted semantic replay.

**Guardrail:** Version 0.1.7 adds goal identity and contract hash to the strict anchor schema. The transition rejects any anchor whose goal or contract does not match the transition, and S2 checks the same bindings again before allowing global PASS.

**Regression tests:** test_authenticated_global_anchor_cannot_replay_across_goal and test_authenticated_global_anchor_cannot_replay_across_contract.

**Version change:** experiment 0.1.6 -> **0.1.7**.
