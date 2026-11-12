"""Run one deterministic verification using DEHAL's public v2 API."""

import hashlib
from datetime import datetime, timezone

from dehal.dehal_v2 import EvidenceSnapshot, verify


def main() -> None:
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


if __name__ == "__main__":
    main()
