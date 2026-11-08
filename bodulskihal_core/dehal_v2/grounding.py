"""Layer 2 — deterministic grounding against evidence snapshots (VETO authority)."""
from __future__ import annotations
import re
from typing import Iterable

from .snapshot import EvidenceSnapshot

NUMBER_RE = re.compile(r"\d[\d,._ ]*(?:\.\d+)?")

# Rounding tolerance per currency: two decimals for most, whole units for JPY.
TOLERANCE = {"JPY": 1.0}
DEFAULT_TOLERANCE = 0.01


def rounding_tolerance(currency: object) -> float:
    return TOLERANCE.get(currency, DEFAULT_TOLERANCE) if isinstance(currency, str) else DEFAULT_TOLERANCE


def extract_numbers(text: str) -> list[float]:
    """Extract numeric tokens from text. Deliberately conservative and
    documented: this handles plain numbers and thousands separators; it is
    not a full financial-text parser (known limitation, see architecture doc).
    """
    out = []
    for match in NUMBER_RE.findall(text or ""):
        token = re.sub(r"[,_ ]", "", match)
        try:
            out.append(float(token))
        except ValueError:
            continue
    return out


def numeric_match(numbers: Iterable[float], price: float, tolerance: float) -> bool:
    return any(abs(n - price) <= tolerance for n in numbers)


def price_covered(snapshots: list[EvidenceSnapshot], price: float,
                   tolerance: float) -> bool:
    return any(numeric_match(extract_numbers(s.text), price, tolerance) for s in snapshots)


def quorum_agrees(snapshots: list[EvidenceSnapshot], price: float,
                  tolerance: float) -> bool:
    """True when every snapshot that contains any numbers agrees on the price.

    A snapshot with numbers none of which match the claim is a contradiction.
    A snapshot with no extractable numbers abstains (does not contradict).
    """
    for s in snapshots:
        nums = extract_numbers(s.text)
        if nums and not numeric_match(nums, price, tolerance):
            return False
    return True
