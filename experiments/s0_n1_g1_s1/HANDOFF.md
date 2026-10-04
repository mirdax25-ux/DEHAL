# BodulskiHal — HANDOFF for ordinary ChatGPT / Engram

Date: 2026-10-04 (Europe/Berlin). Repository: `mirdax25-ux/Brutala-Hal-`.
Originating chat: `Kako se rade testovi`, ID `6ac1e437-bbd4-83ed-9609-1acc1140dc7a`.

## Goal and authorized scope

Only a small experimental **S0 → N1 → G1 → S1** cycle with deterministic
evidence predicates, candidate-only preparation, PASS/BLOCK/UNKNOWN/CONFLICT,
minimal runner, positive/negative/adversarial tests and an external handoff.
No UI, deployment, n8n, Supabase, Vercel, application, N2/G2 or merge to main.
Maximum budget was 60 minutes; work began at 08:13:56 Berlin time.

## Inventory and Git identity

- Actual base/default branch: `main`, commit `cfcb4ac3c3bc1ecc69345b58bb2999e9126235d5`.
- Inventory: 64 tracked files before this experiment; Python package/core 2.1.2,
  existing `bodulskihal_core`, `tests`, `examples`, docs, remote Floot snapshot,
  grants and GitHub CI. No repository-local AGENTS.md was found in that checkout;
  enclosing task instructions were followed.
- Experimental branch: `codex/s0-n1-g1-s1-experiment-20261004`.
- Implementation/test-evidence commit: **`ad1b572a3c9832e35ca0ce9c5c599fd2b0370824`**.
- This HANDOFF is a subsequent documentation-only commit. Resolve the branch
  HEAD for its exact commit; the implementation SHA above is deliberately fixed
  and avoids a self-referential commit hash.
- PR: not created. No main merge is authorized or performed by this task.
- Publication status at the time this file was authored: pending push and remote
  SHA read-back. Consult the task's final Git read-back for publication status;
  do not treat this document's existence as proof of a push.

## Changed files

All changes are additions under `experiments/s0_n1_g1_s1/`:

- `runner.py`: bounded one-cycle runner, candidate protocol, local evidence
  collection, existing-core verification, four outcomes, S1 receipt and demo.
- `test_runner.py`: 37 parameterized positive, negative and adversarial cases.
- `README.md`: contract, execution commands, trust boundaries and limitations.
- `FAILURES.md`: four confirmed setup/specification/implementation failure
  records, each with root cause, guardrail, regression and version decision.
- `evidence/validation.json`: actual subprocess commands, exit codes, outputs,
  counts and SHA-256 hashes of the sources used in final local validation.
- `HANDOFF.md`: this transferable continuation record.

Existing core/package/remote/CI files and versions were not edited. Experiment
version is 0.1.0; there is no production release or additional runtime dependency.

## Architecture and decision semantics

S0 belongs to the operator, specifies expected JSON field values and pinned local
source hashes, and is canonicalized. N1 is a candidate stub with randomized
predicate ordering, or supplied candidate JSON. It has no classification authority.
G1 binds N1 to S0, reads sources itself, checks age/hash/coverage/types, rereads
to signal changes and calls the existing core with computed evidence. S1 has
bounded FACT field equalities only after overall PASS; otherwise state is null.

PASS = every declared predicate and required source satisfied; BLOCK = invalid
contract/candidate or eligible refutation; UNKNOWN = insufficient/invalid/stale/
changed evidence; CONFLICT = eligible support and contradiction of one predicate.
Cross-predicate precedence: CONFLICT > BLOCK > UNKNOWN > PASS. CLI exit codes
are respectively 3, 1, 2 and 0.

## Verification evidence — FACT within the recorded local scope

Final source validation completed at **08:29:37 Berlin time** (06:29:37 UTC),
Windows, Python 3.14.7, pytest 9.1.1:

```text
python -m pytest tests experiments/s0_n1_g1_s1 --junitxml=../work/final-junit.xml --tb=short
332 passed; 295 existing + 37 experimental; 0 failures, 0 errors, 0 skipped
python -m compileall -q bodulskihal_core experiments/s0_n1_g1_s1
exit 0
python -m experiments.s0_n1_g1_s1.runner --demo
exit 0; PASS; 2 bounded facts from fresh synthetic local evidence
```

The experiment tests execute fresh CLI subprocesses for all four exit/status
pairs and reload serialized receipts. They cover missing/partial evidence,
contradiction, stale/future content times, changed pins, mutation between reads,
N1 FACT/evidence/approval injection, skipped predicates, contract substitution,
bad specifications, strict Boolean equality, hostile JSON and path traversal.
The source hashes did not change during the run.

The mandatory installed `detecting-hallucinations/SKILL.md` and its contracts
were read. `response_guard.py verify` actually ran at 06:30:48 UTC: exit 0,
14/14 bounded predicates approved as FACT, direct reads fresh, zero contradictions
or unavailable observations. These checks covered validation records and the
four source/document file hashes; runtime assertions additionally rest on the
actual subprocess executions above. This does not certify arbitrary prose,
source authenticity or an entire application. Full local gate reports are in
the enclosing task's `work/evidence.json` and `work/evidence.md`.

## Failures and remaining limits

1. Missing pytest initially prevented baseline execution. Isolated test venv
   established; baseline then passed 295 tests. No version change.
2. **Confirmed specification limitation:** existence-only S0 can PASS while
   correctness is false. Test demonstrates weak-spec PASS and strengthened-spec
   BLOCK; output facts stay bounded. Semantic completeness remains UNKNOWN.
3. Oversized automatic pytest ID exceeded Windows' 32,767-character environment
   limit (35 passed, 2 setup/teardown errors). Short explicit IDs resolved the
   harness issue, and the oversized evidence test then executed. No version change.
4. `1e9999` overflow crashed G1's Python API. A new test failed first; finite-number
   parsing then made it return UNKNOWN. Regression passed in the final suite.
   No version change outside unreleased experiment 0.1.0.

Complete FAILURE MODE → ROOT CAUSE → GUARDRAIL → REGRESSION TEST → VERSION CHANGE
records are in `FAILURES.md`. No rollback was performed.

**UNKNOWN/UNVERIFIED:** live LLM/BodulLogic integration, external source truth,
source timestamp authenticity, semantic completeness of arbitrary S0, Linux/
other Python versions, hosted CI on this branch, and production readiness.
Existing CI does not include the experiment and does not trigger on this branch;
no CI success is inferred from local tests. No live external integration was part
of this experiment.

**CONFLICT:** contradiction fixtures deliberately return CONFLICT. No unresolved
contradiction was found in the bounded final local validation observations.

**Residual risk:** operator-owned S0/source/clock trust, unsigned receipts,
same-process hostile code, post-final-read changes and ABA races. Two reads are
a TOCTOU signal, not atomicity. Source documents can lie consistently. PASS is
only the specified field predicates, never whole-system READY.

## Next smallest justified step

Review whether the one-cycle contract and the demonstrated bad-spec limitation
meet the intended experiment. If further work is explicitly authorized, choose
one concrete S0 with independently specified success criteria before replacing
the N1 stub. Do not automatically add UI, infrastructure, a second cycle, or merge.

This file is ready to copy/store in Engram. Engram storage was not performed by
this task; availability through ordinary ChatGPT depends on reading this GitHub
file or explicitly saving it in Engram. Recheck GitHub branch/commit state when
continuing; this is a dated handoff, not a live-state authority.
