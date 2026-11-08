"""Layer 1 — deterministic hard checks (BLOCK authority)."""
from __future__ import annotations
import math
from datetime import datetime

REQUIRED_FIELDS = ("ticker", "price", "currency", "datetime", "price_type")
ALLOWED_PRICE_TYPES = frozenset({"open", "close", "intraday"})

# Per-currency inclusive upper bounds. A claim outside its currency bound is
# structurally impossible, independent of any source.
CURRENCY_BOUNDS = {
    "USD": (0.0, 100_000.0),
    "EUR": (0.0, 100_000.0),
    "GBP": (0.0, 100_000.0),
    "JPY": (0.0, 10_000_000.0),
    "BTC": (0.0, 10_000_000.0),
}
DEFAULT_BOUND = (0.0, 100_000.0)


def parse_iso_datetime(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("datetime must be an ISO 8601 string")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("datetime must carry a timezone offset")
    return parsed


def check_hard(claim: dict, evaluation_time: datetime) -> list[str]:
    """Return a list of hard errors. Empty list == structurally valid claim."""
    errors: list[str] = []
    for f in REQUIRED_FIELDS:
        if f not in claim or claim[f] is None:
            errors.append(f"missing_field:{f}")

    price = claim.get("price")
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        errors.append("price_not_numeric")
    else:
        if not math.isfinite(price):  # NaN/inf pass comparisons silently
            errors.append("price_not_finite")
        elif price <= 0:
            errors.append("price_not_positive")

    currency = claim.get("currency")
    if isinstance(price, (int, float)) and isinstance(price, float) and math.isfinite(price) and price > 0:
        low, high = CURRENCY_BOUNDS.get(currency, DEFAULT_BOUND) if isinstance(currency, str) else DEFAULT_BOUND
        if not (low < price <= high):
            errors.append("price_out_of_currency_bound")

    if "price_type" in claim and claim["price_type"] not in ALLOWED_PRICE_TYPES:
        errors.append("bad_price_type")

    try:
        claim_dt = parse_iso_datetime(claim["datetime"])
        if claim_dt > evaluation_time:
            errors.append("datetime_in_future")
    except (KeyError, ValueError, TypeError):
        pass  # already reported via missing_field / parse failure handled above

    return errors
