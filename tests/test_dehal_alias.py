"""DEHAL canonical import name contract (Phase A of the rename).

'dehal' must expose the full public surface; the old
'bodulskihal_core' name keeps working as a deprecated alias.
"""
import dehal
import bodulskihal_core


def test_dehal_exposes_engine_surface():
    for name in (
        "Claim",
        "Verdict",
        "Policy",
        "verify_claim",
        "verify_compound",
        "run_guard_loop",
        "evaluate_benchmark",
        "canonical_receipt_sha256",
    ):
        assert hasattr(dehal, name), f"dehal.{name} missing"


def test_dehal_is_the_same_implementation():
    assert dehal.verify_claim is bodulskihal_core.verify_claim
    assert dehal.adapter.SCHEMA_VERSION == bodulskihal_core.adapter.SCHEMA_VERSION


def test_dehal_v2_importable_under_new_name():
    from dehal.dehal_v2 import EvidenceSnapshot, NullObserver, verify
    from dehal.dehal_v2.engine import Verdict as V2Verdict

    assert callable(verify)
    assert V2Verdict is not None
