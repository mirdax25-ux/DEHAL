from datetime import datetime, timezone
from itertools import permutations

import pytest

from b_1_2_core import (
    Claim, ClaimType, Directness, Evidence, Policy, RiskLevel, Verdict, verify_claim,
)


NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def verify_sources(sources):
    return verify_claim(
        Claim("quorum", "A medium-risk fact", ClaimType.OBSERVATION, risk=RiskLevel.MEDIUM),
        [Evidence(evidence_id=f"e-{index}", supports=True, observed_at=NOW,
                  directness=Directness.DIRECT, **source)
         for index, source in enumerate(sources)],
        policy=Policy("alias-regression", 300),
        evaluation_time=NOW,
    )


@pytest.mark.parametrize("sources", [
    [dict(source_id="a", source_ref="same-ref", independence_group="group-a"),
     dict(source_id="b", source_ref="same-ref", independence_group="group-b")],
    [dict(source_id="a", source_ref="same-ref", independence_group="group-a"),
     dict(source_id="b", source_ref="same-ref")],
    [dict(source_id="same-source", source_ref="ref-a", independence_group="group-a"),
     dict(source_id="same-source", source_ref="ref-b", independence_group="group-b")],
    [dict(source_id="same-source"),
     dict(source_id="same-source", source_ref="ref-b")],
])
def test_optional_identity_metadata_cannot_split_known_source(sources):
    result = verify_sources(sources)
    assert result.verdict is Verdict.ESCALATE
    assert result.receipt["gates"]["independent_supporting_group_count"] == 1


def test_overlapping_provenance_is_transitive_and_order_independent():
    sources = [
        dict(source_id="a", source_ref="ref-one", independence_group="group-one"),
        dict(source_id="b", source_ref="ref-two", independence_group="group-two"),
        dict(source_id="bridge", source_ref="ref-one", independence_group="group-two"),
    ]
    for order in permutations(sources):
        result = verify_sources(order)
        assert result.verdict is Verdict.ESCALATE
        assert result.receipt["gates"]["independent_supporting_group_count"] == 1


def test_identity_namespaces_do_not_merge_unrelated_sources():
    result = verify_sources([
        dict(source_id="source-a", source_ref="shared-spelling"),
        dict(source_id="source-b", independence_group="shared-spelling"),
    ])
    assert result.verdict is Verdict.APPROVE
    assert result.receipt["gates"]["independent_supporting_group_count"] == 2
