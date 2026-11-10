"""DEHAL v2 - 5 obaveznih testova.

Pokretanje: python3 test_dehal_core.py  (radi i pod pytest-om)
"""

from dehal_core import dehal_evaluate

EV_OK = [{
    "id": "e1",
    "content": "Zagreb je glavni grad Hrvatske, potvrđeno izvorom X.",
    "sha256": __import__("hashlib").sha256(
        "Zagreb je glavni grad Hrvatske, potvrđeno izvorom X.".encode("utf-8")
    ).hexdigest(),
    "retrieved_at": "2026-11-10T00:00:00Z",
    "flags": [],
}]

EV_CONTRA = [{
    "id": "e2",
    "content": "CONTRADICTS: Zagreb nije glavni grad prema izvoru Y.",
    "sha256": __import__("hashlib").sha256(
        "CONTRADICTS: Zagreb nije glavni grad prema izvoru Y.".encode("utf-8")
    ).hexdigest(),
    "retrieved_at": "2026-11-10T00:00:00Z",
    "flags": [],
}]

EV_FLAG = [{
    "id": "e3",
    "content": "Zagreb je glavni grad Hrvatske.",
    "sha256": __import__("hashlib").sha256(
        "Zagreb je glavni grad Hrvatske.".encode("utf-8")
    ).hexdigest(),
    "retrieved_at": "2026-11-10T00:00:00Z",
    "flags": ["UNVERIFIED_SOURCE"],
}]


def test_t1_approve_and_determinism():
    a = dehal_evaluate({"claim": "Zagreb je glavni grad Hrvatske", "snapshot": EV_OK,
                        "evaluation_time": "2026-11-10T12:00:00Z"})
    b = dehal_evaluate({"claim": "Zagreb je glavni grad Hrvatske", "snapshot": EV_OK,
                        "evaluation_time": "2026-11-10T12:00:00Z"})
    c = dehal_evaluate({"claim": "Zagreb je glavni grad Hrvatske", "snapshot": EV_OK,
                        "evaluation_time": "2026-11-10T13:00:00Z"})
    assert a["verdict"] == "APPROVE"
    assert a["provenance_sha256"] == b["provenance_sha256"]
    assert a["provenance_sha256"] != c["provenance_sha256"]
    assert len(a["provenance_sha256"]) == 64


def test_t2_contradiction_block_and_veto():
    out = dehal_evaluate({"claim": "Zagreb je glavni grad Hrvatske", "snapshot": EV_CONTRA,
                          "evaluation_time": "2026-11-10T12:00:00Z", "llm_proposal": "ESCALATE"})
    assert out["verdict"] == "BLOCK"
    assert "R_LLM_ESCALATE_VETOED_BY_GROUNDING" in out["reasons"]


def test_t3_flag_escalate():
    out = dehal_evaluate({"claim": "Zagreb je glavni grad Hrvatske", "snapshot": EV_FLAG,
                          "evaluation_time": "2026-11-10T12:00:00Z"})
    assert out["verdict"] == "ESCALATE"
    assert "R_FLAG_ESCALATE" in out["reasons"]


def test_t4_llm_approve_proposal_rejected():
    out = dehal_evaluate({"claim": "Zagreb je glavni grad Hrvatske", "snapshot": [],
                          "evaluation_time": "2026-11-10T12:00:00Z", "llm_proposal": "APPROVE"})
    assert out["verdict"] == "BLOCK"
    assert "R_LLM_PROPOSAL_REJECTED_ONLY_ESCALATE_ALLOWED" in out["reasons"]


def test_t5_empty_snapshot_block_and_sha256_vector():
    out = dehal_evaluate({"claim": "Bilo što", "snapshot": [],
                          "evaluation_time": "2026-11-10T12:00:00Z"})
    assert out["verdict"] == "BLOCK"
    import hashlib
    assert hashlib.sha256(b"abc").hexdigest() == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} testova prolazi")
    raise SystemExit(1 if failed else 0)
