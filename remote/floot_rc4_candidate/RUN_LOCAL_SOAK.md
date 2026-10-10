# Local rc.4 test candidate — Windows

This is an isolated copy of Floot rc.4 candidate, NOT the canonical core. Do not deploy or merge automatically.

Prerequisites: Python 3 and Node.js/npm installed. Open PowerShell in this directory after cloning the private branch.

1. `npm install`
2. `npm run test:core` (baseline must PASS before soak)
3. `python soak_runner.py --command "node node_modules/vitest/vitest.mjs run helpers/BodulHalCore.spec.tsx helpers/McpGuardTool.spec.tsx --globals" --hours 8 --output soak-results`

Review `soak-results/summary.json` and `soak-results/iterations.jsonl`. The runner stops on first nonzero exit code. Do not report PASS without the final summary and elapsed duration.

Note: the command exercises local unit tests repeatedly; it does NOT exercise live MCP transport, long-running server uptime, or production load. A separate transport soak is needed for those claims.

Source: Floot project BodulHal RC4 Candidate Test, version 1791317446194.
