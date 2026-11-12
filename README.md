# DEHAL

[![CI](https://github.com/mirdax25-ux/DEHAL/actions/workflows/ci.yml/badge.svg)](https://github.com/mirdax25-ux/DEHAL/actions/workflows/ci.yml)

DEHAL is a Python verification engine for structured claims and supplied evidence. Its deterministic v2 engine returns `APPROVE`, `BLOCK`, or `ESCALATE`. It evaluates provided evidence snapshots rather than fetching sources, and the evaluation time is an explicit input.

DEHAL is intended for teams integrating AI or agent workflows that need to check structured claims against evidence before relying on them. The v2 engine applies deterministic checks; an optional observer can only cause an `ESCALATE`. Each verdict includes SHA-256 claim and evidence hashes for provenance. These hashes identify inputs; they do not establish that an external source is authentic.

## Minimal example

This uses the public `dehal.dehal_v2` API and the same executable example in [`examples/minimal_check.py`](examples/minimal_check.py):

```python
import hashlib
from datetime import datetime, timezone

from dehal.dehal_v2 import EvidenceSnapshot, verify

claim = {
    "ticker": "AAPL",
    "price": 342.37,
    "currency": "USD",
    "datetime": "2026-11-06T16:00:00-05:00",
    "price_type": "close",
    "exchange": "NASDAQ",
    "raw_text": "AAPL closed at 342.37.",
}
text = "AAPL closed at 342.37 USD."
snapshot = EvidenceSnapshot(
    source_id="example",
    text=text,
    sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    fetched_at="2026-11-07T10:00:00+00:00",
)

verdict = verify(
    claim,
    [snapshot],
    datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc),
)
print(verdict.to_json())
```

## Quickstart

1. Clone the repository:

   ```bash
   git clone https://github.com/mirdax25-ux/DEHAL.git
   ```

2. Enter the repository:

   ```bash
   cd DEHAL
   ```

3. Install the package and run the example:

   ```bash
   python -m pip install -e ".[test]"
   python examples/minimal_check.py
   ```

Python 3.10 or newer is required. Run the test suite with `python -m pytest`.

## v2 reference behavior

The independent reference implementation in [`v2_reference/dehal_core.py`](v2_reference/dehal_core.py) documents a small claim-and-evidence API. It fails closed for invalid input and missing evidence, blocks contradictions, and escalates flagged or unsupported evidence. Its optional LLM proposal accepts only `ESCALATE`; deterministic grounding can veto that proposal. See [the v2 architecture note](docs/architecture.md) for the evaluation order and provenance fields.

## License

DEHAL is licensed under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution information.
