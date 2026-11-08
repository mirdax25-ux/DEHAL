#!/usr/bin/env python3
"""DEHAL v2 demo: verification of a market-data claim (AAPL close).

Runnable without network: evidence snapshots are static, supplied by the
"host" here (normally fetched upstream, hashed, then handed to the core).

Three verdicts in one run:
  1. honest claim, covered price      -> APPROVE
  2. invented price, perfect JSON     -> BLOCK  (pretty format buys nothing)
  3. observer (advisory) conflict     -> ESCALATE (never BLOCK, never APPROVE)
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from bodulskihal_core.dehal_v2 import EvidenceSnapshot, verify
from bodulskihal_core.dehal_v2.semantic import Observations

EVAL_TIME = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)


def snapshot(source_id: str, text: str) -> EvidenceSnapshot:
    return EvidenceSnapshot(
        source_id=source_id,
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        fetched_at="2026-11-07T10:00:00+00:00",
    )


HONEST_CLAIM = {
    "ticker": "AAPL",
    "price": 342.37,
    "currency": "USD",
    "datetime": "2026-11-06T16:00:00-05:00",
    "price_type": "close",
    "exchange": "NASDAQ",
    "raw_text": "AAPL closed at 342.37 on Nov 6.",
}

INVENTED_CLAIM = dict(HONEST_CLAIM, price=342.99)  # perfect format, no coverage

SOURCE = snapshot("market-feed", "AAPL close 342.37 on 2026-11-06 (NASDAQ).")


class SuspiciousObserver:
    """Advisory layer only: it can never BLOCK or APPROVE."""

    def observe(self, raw_text: str, claim: dict) -> Observations:
        return Observations(suggests_conflict=True, notes=("semantic_mismatch",))


def main() -> None:
    print("== DEHAL v2 — market claim demo ==")
    print()

    v1 = verify(HONEST_CLAIM, [SOURCE], EVAL_TIME)
    print(f"1. Honest claim            -> {v1.decision}  reasons={list(v1.reasons)}")
    print(f"   claim_hash={v1.claim_hash[:16]}...  evidence={v1.evidence_hashes[0][:16]}...")

    v2 = verify(INVENTED_CLAIM, [SOURCE], EVAL_TIME)
    print(f"2. Invented price (pretty) -> {v2.decision}  reasons={list(v2.reasons)}")

    v3 = verify(HONEST_CLAIM, [SOURCE], EVAL_TIME, observer=SuspiciousObserver())
    print(f"3. Observer conflict       -> {v3.decision}  reasons={list(v3.reasons)}")
    print()

    # Determinism proof: same inputs -> byte-identical verdict, 10 runs.
    outputs = {verify(HONEST_CLAIM, [SOURCE], EVAL_TIME).to_json() for _ in range(10)}
    print(f"Determinism: {len(outputs)} unique verdict(s) over 10 runs -> "
          f"{'OK' if len(outputs) == 1 else 'BROKEN'}")

    print()
    print("Rule demonstrated: a beautiful JSON structure can never buy")
    print("passage for an invented number. LLM advice escalates, it never rules.")


if __name__ == "__main__":
    main()
