"""DEHAL v2 mandatory tests (architecture doc section 6).

Five mandatory gates plus regression coverage. These tests define
"done": the implementation is not finished until all of them pass,
in CI, on a machine that did not write them.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone

import pytest

from bodulskihal_core.dehal_v2 import EvidenceSnapshot, NullObserver, verify
from bodulskihal_core.dehal_v2.engine import Verdict

ET = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)


def snap(source_id, text):
    return EvidenceSnapshot(
        source_id=source_id,
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        fetched_at="2026-11-07T10:00:00+00:00",
    )


GOOD_CLAIM = {
    "ticker": "AAPL",
    "price": 342.37,
    "currency": "USD",
    "datetime": "2026-11-06T16:00:00-05:00",
    "price_type": "close",
    "exchange": "NASDAQ",
    "raw_text": "AAPL closed at 342.37 on Nov 6.",
}
GOOD_SNAP = snap("s1", "AAPL close 342.37 on 2026-11-06.")


def test_1_fake_price_with_pretty_format_is_blocked():
    """Mandatory test 1 (finding B): perfect JSON, invented price -> BLOCK."""
    claim = dict(GOOD_CLAIM, price=342.99)  # not in any snapshot
    v = verify(claim, [GOOD_SNAP], ET)
    assert v.decision == "BLOCK"
    assert "price_not_found_in_snapshots" in v.reasons


def test_2_nan_price_is_blocked():
    claim = dict(GOOD_CLAIM, price=float("nan"))
    v = verify(claim, [GOOD_SNAP], ET)
    assert v.decision == "BLOCK"
    assert "price_not_finite" in v.reasons


def test_3_substring_overflow_is_blocked():
    """'342.37' must not be covered by a source saying '1342.37'."""
    overflow = snap("s2", "Ticker closed at 1342.37 yesterday.")
    v = verify(GOOD_CLAIM, [overflow], ET)
    assert v.decision == "BLOCK"


def test_4_observer_conflict_is_always_escalate_never_block():
    class FlakyObserver:
        calls = 0

        def observe(self, raw_text, claim):
            FlakyObserver.calls += 1
            from bodulskihal_core.dehal_v2.semantic import Observations
            return Observations(suggests_conflict=True, notes=("looks_wrong",))

    o1, o2 = FlakyObserver(), FlakyObserver()
    v1 = verify(GOOD_CLAIM, [GOOD_SNAP], ET, observer=o1)
    v2 = verify(GOOD_CLAIM, [GOOD_SNAP], ET, observer=o2)
    assert v1.decision == "ESCALATE" and v2.decision == "ESCALATE"
    assert "looks_wrong" in v1.reasons


def test_5_ten_runs_byte_identical():
    """Mandatory test 5: same inputs -> 10 byte-identical verdicts."""
    outs = {verify(GOOD_CLAIM, [GOOD_SNAP], ET).to_json() for _ in range(10)}
    assert len(outs) == 1
    payload = json.loads(next(iter(outs)))
    assert payload["decision"] == "APPROVE"


def test_missing_field_blocks():
    v = verify({"ticker": "AAPL"}, [GOOD_SNAP], ET)
    assert v.decision == "BLOCK"
    assert "missing_field:price" in v.reasons


def test_future_date_blocks():
    claim = dict(GOOD_CLAIM, datetime="2026-11-08T16:00:00-05:00")
    assert verify(claim, [GOOD_SNAP], ET).decision == "BLOCK"


def test_corrupt_snapshot_escalates_never_approves():
    bad = EvidenceSnapshot("s3", "AAPL close 342.37", sha256="0" * 64,
                           fetched_at="2026-11-07T10:00:00+00:00")
    v = verify(GOOD_CLAIM, [bad], ET)
    assert v.decision == "ESCALATE"
    assert "corrupt_snapshot:s3" in v.reasons


def test_source_disagreement_escalates():
    s_a = snap("a", "AAPL close 342.37")
    s_b = snap("b", "AAPL close 999.11")
    v = verify(GOOD_CLAIM, [s_a, s_b], ET)
    assert v.decision == "ESCALATE"
    assert "source_disagreement" in v.reasons


def test_rounding_tolerance_covers():
    rounded = snap("r", "AAPL closed 342.4")
    v = verify(GOOD_CLAIM, [rounded], ET)
    assert v.decision == "APPROVE"


def test_raw_text_contradiction_escalates():
    claim = dict(GOOD_CLAIM, raw_text="AAPL closed at 500.00 on Nov 6.")
    v = verify(claim, [GOOD_SNAP], ET)
    assert v.decision == "ESCALATE"
    assert "raw_text_numbers_differ" in v.reasons


def test_verdict_carries_provenance():
    v = verify(GOOD_CLAIM, [GOOD_SNAP], ET)
    assert v.claim_hash and len(v.claim_hash) == 64
    assert v.evidence_hashes == (GOOD_SNAP.sha256,)
