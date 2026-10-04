# Grouped N1<->N2 -> N2 -> C -> S1 -> S2 -> N1(read-only) prototype

This isolated experiment implements the currently selected architecture exactly at the trust-boundary level:

```text
        N1 (READ-ONLY) -> OUTPUT
        ^
       S2   terminal policy + exact-action decision
        ^
       S1   integrity/provenance/state validation
        ^
        C   immutable checkpoint
        ^
       N2   final advisory challenge
        ^
     N1 <-> N2   bounded revision/challenge loop
```

The experiment does **not** call an LLM and does not claim universal correctness. N1/N2 are represented as untrusted structured data so the architecture itself can be attacked deterministically.

## Trust rules implemented

- Group-transition data are issued by a deterministic boundary and bind goal, contract, state hash/version, evidence root, prior receipt and global-anchor metadata.
- S1 PASS requires a separate evidence-authority receipt bound to `evidence_root + state_version + contract_hash`. A raw evidence-root label without that receipt yields UNKNOWN.
- Global-goal PASS requires a separate anchor receipt bound to a distinct anchor trust key. The authenticated anchor is also bound to the exact goal identity and contract hash, preventing replay across goals or policy revisions. A caller-supplied `independent=true` flag without that receipt is only untrusted context and yields UNKNOWN.
- N1/N2 cannot author trusted PASS receipts.
- Each N2 review is bound to the exact candidate and parent receipt. Its receipt proves what N2 said, **not that N2 was correct**.
- The N1<->N2 loop stops on CLEAR, UNKNOWN, unresolved CHALLENGE, repeated candidate, or max-round budget.
- C freezes the exact transition/candidate/loop/final-N2 bundle. C means integrity, not truth.
- S1 checks checkpoint, transition, current state/policy and provenance bindings. It does not decide the global semantic goal.
- S2 independently checks the concrete action/policy, global-goal anchor and S1 receipt. It emits the only terminal receipt.
- Final N1 is read-only presentation: it controls only explanation text. Trusted status/action fields are copied directly from S2.
- Executor accepts only the S2 terminal receipt, exact action hash, exact current-state hash/version, exact current-policy hash/semantics, and an S2-derived stable execution token consumed through a trusted file-backed ledger.

## Bounded status semantics

PASS, UNKNOWN, BLOCK, and CONFLICT are separate terminal states. A contract PASS does not imply global-goal PASS. If the global goal is not independently grounded for the current state, terminal output is UNKNOWN even when the concrete contract passes.

## Tests

Run from repository root:

```text
python -m pytest -q experiments/grouped_n1n2_c_s1_s2/test_runner.py experiments/grouped_n1n2_c_s1_s2/test_fuzz.py
python -m compileall -q experiments/grouped_n1n2_c_s1_s2
```

Experiment version **0.1.8** currently has **443 passing experiment tests** in the local isolated environment: the prior 441 plus 2 specification-scope regressions. The combined existing repository suite plus this experiment has **738 passing tests** locally. Hosted GitHub CI is not claimed until separately observed.

## Explicit limitations

- HMAC is an in-process provenance mechanism for the experiment; separate boundary, anchor and evidence keys model distinct trust roots, but there is no production key-management or process-isolation design here.
- Arbitrary hostile Python running in the same process can access memory and is outside this prototype's threat model.
- An N2 receipt authenticates the message path, not the truth of N2's claim.
- A separately authenticated global anchor can still be wrong, compromised or share a common upstream source. Provenance is not truth, and the prototype's second HMAC key models a distinct trust root rather than production-grade key isolation.
- The remaining fundamental boundary is specification validation: a perfectly implemented kernel can faithfully enforce the wrong rule.
- The file-backed ledger provides local at-most-once replay protection across process restart, not a distributed exactly-once transaction. A production executor must couple idempotency to the real external side effect.
- goal_id is now the stable idempotency identity for one intended side effect; trusted upstream code must not mint a new goal_id merely to retry the same operation.
- No deploy, merge, UI, network service, database or production action is performed.
