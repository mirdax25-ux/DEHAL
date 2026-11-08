"""Layer 3 — semantic checks: deterministic extraction first, LLM advisory only.

LLM observers are supplied by the host. The core only consumes their
suggestion; an observer can never produce BLOCK or APPROVE.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from .grounding import extract_numbers, numeric_match, rounding_tolerance


def raw_text_numbers_differ(claim: dict) -> bool:
    """Deterministic: do numbers in raw_text contradict the structured price?"""
    raw = claim.get("raw_text")
    if not isinstance(raw, str):
        return False  # no raw text -> nothing to contradict
    numbers = extract_numbers(raw)
    if not numbers:
        return False  # abstains
    price = claim.get("price")
    if not isinstance(price, (int, float)):
        return True
    tol = rounding_tolerance(claim.get("currency"))
    return not numeric_match(numbers, price, tol)


@dataclass(frozen=True)
class Observations:
    suggests_conflict: bool = False
    notes: tuple = field(default_factory=tuple)


class NullObserver:
    """Default observer: deterministic system, never conflicts. The host can
    substitute an LLM-backed observer; it can only suggest ESCALATE."""

    def observe(self, raw_text: str, claim: dict) -> Observations:
        return Observations(suggests_conflict=False)
