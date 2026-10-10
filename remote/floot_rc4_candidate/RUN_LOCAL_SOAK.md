# Local rc.4 test candidate — Windows

This is an isolated copy of Floot rc.4 candidate, NOT the canonical core. Do not deploy or merge automatically.

Prerequisites: Python 3 and Node.js/npm installed. Open PowerShell in this directory after cloning the private branch.

1. `npm install`
2. `npm run test:core` (baseline must PASS before soak)
3. `python soak_runner.py --command "node node_modules/vitest/vitest.mjs run helpers/BodulHalCore.spec.tsx helpers/McpGuardTool.spec.tsx --globals" --hours 8 --output soak-results`

Review `soak-results/summary.json` and `soak-results/iterations.jsonl`. The runner stops on first nonzero exit code. Do not report PASS without the final summary and elapsed duration.

Note: the command exercises local unit tests repeatedly; it does NOT exercise live MCP transport, long-running server uptime, or production load. A separate transport soak is needed for those claims.

Source: Floot project BodulHal RC4 Candidate Test, version 1791317446194.

## Soak runner v1.0.1 — deadline boundary fix (2026-10-10)
- The overall deadline prevents NEW iterations, but does not truncate a test already started.
- Per-iteration timeout remains 1800 seconds; real errors and per-iteration timeouts remain FAIL.
- Final elapsed time may exceed requested duration by one started iteration; always report measured elapsed time.
- Re-run regression tests: `python -m unittest -v test_soak_runner_deadline.py`.
- The historical 8-hour `soak-results/summary.json` remains FAIL (one deadline-induced timeout); do not relabel it PASS. A fresh 8-hour run is required for a new 8-hour PASS claim.
