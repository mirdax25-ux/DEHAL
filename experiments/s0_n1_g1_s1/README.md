# S0 → N1 → G1 → S1: one-cycle experiment 0.1.0

This directory is an isolated experiment. It reuses `bodulskihal_core.engine`
2.1.2 without changing the existing core, package version, CI, remote code or
application behavior. It has no UI, deployment, service, database, n8n,
Supabase, Vercel, or N2/G2 cycle. Runtime uses the Python standard library and
the existing repository core; pytest is a development-only test dependency.

## Exact contract

1. **S0** is an operator-owned JSON specification: schema version, maximum
   evidence age and a nonempty set of predicates. Each predicate names a field,
   a scalar expected value and every required source with its SHA-256 snapshot.
   G1 canonicalizes and copies it. Empty/duplicate/unsupported contracts block.
2. **N1** produces a candidate bound to the S0 digest and an exact list of its
   predicate IDs. The built-in candidate stub randomizes their order. Alternatively,
   `--candidate` reads externally generated JSON. This is a candidate boundary,
   not a real model/BodulLogic integration. No model calls or candidate code execute.
3. **G1** reads the local sources itself, checks pins, content observation times,
   field equality, required-source coverage and changes across two reads. It
   supplies computed support/counterevidence to the existing BodulskiHal engine.
   N1 cannot provide evidence, approval, classification, a weaker contract or a
   skipped predicate. Extra candidate fields block.
4. **S1** is JSON with a receipt and, only for overall PASS, a state containing
   the exact field equalities. Other outcomes have `state: null`. A receipt has
   hashes of S0/candidate, evaluation time, per-predicate evidence and the core
   receipts. Its checksum detects accidental changes; it is not a signature.

| Outcome | Meaning | CLI exit |
|---|---|---|
| PASS | Every specified predicate satisfied; every required source eligible | 0 |
| BLOCK | Invalid contract/candidate/path, or an eligible predicate is refuted | 1 |
| UNKNOWN | Missing, malformed, stale, future or changed evidence; no eligible conclusion | 2 |
| CONFLICT | Eligible sources both support and contradict the same predicate | 3 |

Across predicates the precedence is CONFLICT, BLOCK, UNKNOWN, PASS. A valid
counterexample can block even when another source is unavailable. Disagreement
on different predicates is not a source contradiction. No majority vote hides
counterevidence. The outer receipt is authoritative for the entire transition;
an individual core receipt cannot authorize a partially evidenced S1.

## Run from repository root

Python 3.10+ is required. A local development environment can be prepared with:

```text
python -m venv .venv
.venv\Scripts\python.exe -m pip install pytest
.venv\Scripts\python.exe -m experiments.s0_n1_g1_s1.runner --demo
.venv\Scripts\python.exe -m pytest tests experiments/s0_n1_g1_s1
```

On non-Windows systems use `.venv/bin/python`. The root pytest configuration
discovers only `tests/`; include the experiment path explicitly. Existing CI
is intentionally unchanged and does not run this experiment automatically.

The demo creates fresh **synthetic** evidence in a temporary directory, checks
`answer == 42` and `units == "items"`, prints a receipt, then removes its temporary
files. A demo PASS proves those local checks, not an external system's health.

For real local experiment inputs:

```text
python -m experiments.s0_n1_g1_s1.runner --s0 s0.json --root evidence-folder
python -m experiments.s0_n1_g1_s1.runner --s0 s0.json --root evidence-folder --candidate n1.json
```

S0 shape (replace the timestamp, file and hash with the actual observation;
the placeholder hash is intentionally not executable proof):

```json
{
  "schema_version": 1,
  "max_age_seconds": 60,
  "predicates": [{
    "id": "answer",
    "field": "answer",
    "expected": 42,
    "sources": [{"path": "observation.json", "sha256": "<actual 64-character sha256>"}]
  }]
}
```

Source shape: `{"observed_at":"<actual ISO timestamp with timezone>","values":{"answer":42}}`.
N1 shape: `{"s0_sha256":"<digest of canonical S0>","predicate_ids":["answer"]}`.
`n1(s0)` constructs that candidate; `digest(s0)` uses sorted compact JSON.

Limits: 64 KiB per file; at most 16 predicates and 8 sources per predicate;
maximum evidence age 1–3600 seconds; expected values are string, integer,
boolean or null. Boolean true differs from number 1. Duplicate JSON keys and
nonfinite numbers are rejected. Absolute/escaping source paths block. There
are no network reads. CLI emits JSON on stdout; no output file is overwritten
by the runner. Save stdout to a new path if persistence is wanted.

## What the evidence does not establish

**A bad specification can still give PASS for the wrong real-world goal.**
`test_poor_spec_can_pass_while_real_goal_fails_and_must_stay_bounded` deliberately
shows `artifact_exists == true` passing while `result_correct == false`. Adding
the missing correctness predicate blocks. G1 does not infer requirements or
claim that S0 is semantically complete. It emits no free-text application-level
FACT. This is a demonstrated limitation, not a claim that bad specifications
have been solved.

The trusted boundary is the operator-owned S0, evidence root, code and clock.
A pinned local document proves only what that document contains. Neither a
hash nor a supplied timestamp authenticates its author, truth, source authority
or genuine acquisition time. Malicious control of S0 and evidence can fabricate
a consistent PASS. N1's **JSON output** is constrained; executing arbitrary
hostile N1 Python in the same process is not sandboxed by this experiment.

Hash pinning detects changes since S0; a second read detects common TOCTOU
changes during collection. This is not a multi-file transaction, file lock,
ABA-proof monitor or guarantee about time after the final read. S1 is an
observation receipt, not authority to perform a later external action. Re-read
at the actual action boundary for any future integration.

No production readiness, deployment, live LLM integration, universal factual
correctness or measured improvement is claimed. See `FAILURES.md` and `HANDOFF.md`.
