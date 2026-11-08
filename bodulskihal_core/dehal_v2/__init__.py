"""DEHAL v2 — deterministic claim verification core.

Architecture: hard core (BLOCK/APPROVE/ESCALATE) + advisory outer layers.
LLM observers may only suggest ESCALATE. No network, no wall-clock, no LLM
calls inside this package. See docs/DEHAL_V2_ARCHITECTURE.md.
"""
from .engine import Verdict, verify
from .snapshot import EvidenceSnapshot
from .semantic import NullObserver

__all__ = ["Verdict", "verify", "EvidenceSnapshot", "NullObserver"]
