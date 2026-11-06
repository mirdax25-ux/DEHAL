# Verification record

Recorded: 2026-11-06 (UTC).
Source baseline: `8afa1fe3d0379f400ee27b96355f233a5c6d6814`.
Environment: Python 3.12.14 / Linux; pytest 8.4.2.

## Observed results

295 tests passed. Wheel build succeeded with LICENSE and NOTICE.

## Reproduce

```text
python -m pytest
python -m build --wheel
```

## Scope

These are bounded source/package checks. They do not establish live deployment availability, source-to-live parity, external evidence authenticity, or production usage. GitHub CI for the cleanup commit must be inspected separately. No tests are counted twice as distinct cases.
