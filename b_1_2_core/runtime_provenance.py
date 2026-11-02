from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass


UNVERIFIED = "UNVERIFIED"
_GIT_DIGEST = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")


@dataclass(frozen=True)
class RuntimeProvenance:
    source_commit: str
    source_ref: str
    build_id: str
    verified: bool

    def as_dict(self) -> dict[str, str | bool]:
        return asdict(self)


def _env_value(name: str) -> str:
    raw = os.environ.get(name)
    if raw is None:
        return UNVERIFIED
    value = raw.strip()
    return value if value else UNVERIFIED


def current_runtime_provenance() -> RuntimeProvenance:
    source_commit = _env_value("B_1_2_SOURCE_COMMIT")
    source_ref = _env_value("B_1_2_SOURCE_REF")
    build_id = _env_value("B_1_2_BUILD_ID")

    commit_verified = bool(_GIT_DIGEST.fullmatch(source_commit))
    verified = (
        commit_verified
        and source_ref != UNVERIFIED
        and build_id != UNVERIFIED
    )

    return RuntimeProvenance(
        source_commit=source_commit.lower() if commit_verified else source_commit,
        source_ref=source_ref,
        build_id=build_id,
        verified=verified,
    )
