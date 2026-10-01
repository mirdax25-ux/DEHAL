from datetime import datetime, timezone
from pprint import pprint

from bodulskihal_core import Claim, ClaimType, Directness, Evidence, Policy, verify_claim

now = datetime.now(timezone.utc)
result = verify_claim(
    Claim("demo-action", "External action completed", ClaimType.ACTION_STATE),
    [
        Evidence(
            source_id="provider-final-state",
            supports=True,
            observed_at=now,
            directness=Directness.DIRECT,
            post_action=True,
        )
    ],
    policy=Policy(version="1.0", max_age_seconds=300),
    evaluation_time=now,
)

print(result.classification.value, result.verdict.value)
pprint(result.receipt)
