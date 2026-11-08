"""Evidence snapshots with SHA-256 integrity (DEHAL v2)."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvidenceSnapshot:
    """Immutable piece of source evidence produced by the host layer.

    The core never fetches sources; the host supplies text plus its hash.
    A snapshot whose hash does not match its content is corrupt and cannot
    serve as evidence (-> ESCALATE, never APPROVE).
    """
    source_id: str
    text: str
    sha256: str
    fetched_at: str  # ISO 8601, set by the host

    def compute_sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def is_corrupt(self) -> bool:
        return self.compute_sha256() != self.sha256
