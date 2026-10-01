import json
from pathlib import Path

from bodulskihal_core.research_demo import run_research_demo


def test_bundled_research_fixture_is_reproducible():
    fixture_path = Path(__file__).parents[1] / "examples" / "research_fixture.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    first = run_research_demo(payload)
    second = run_research_demo(payload)

    assert first == second
    assert first["metrics"] == {
        "total_claims": 5,
        "verified_fact_count": 1,
        "unknown_blocked_count": 1,
        "conflict_blocked_count": 1,
        "action_gate_blocked_count": 1,
        "escalated_count": 1,
        "blocked_unsupported_claim_count": 1,
        "evidence_coverage": 0.8,
    }
