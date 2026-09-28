from __future__ import annotations

import math
from datetime import date, datetime, time, timezone


def intrinsic_value(spot: float, strike: float, option_type: str) -> float:
    if option_type == "CE":
        return max(spot - strike, 0.0)
    if option_type == "PE":
        return max(strike - spot, 0.0)
    raise ValueError("option_type must be CE or PE")


def extrinsic_value(ltp: float, spot: float, strike: float, option_type: str) -> float:
    return max(ltp - intrinsic_value(spot, strike, option_type), 0.0)


def mid_price(bid: float | None, ask: float | None, ltp: float | None) -> float | None:
    if bid is not None and ask is not None and ask >= bid:
        return (bid + ask) / 2.0
    return ltp


def spread_metrics(
    bid: float | None,
    ask: float | None,
    ltp: float | None,
) -> tuple[float | None, float | None]:
    if bid is None or ask is None or ask < bid:
        return None, None

    spread = ask - bid
    reference = ltp if ltp and ltp > 0 else (bid + ask) / 2
    return spread, spread / reference if reference else None


def oi_change(current_oi: float | None, previous_oi: float | None) -> float | None:
    if current_oi is None or previous_oi is None:
        return None
    return current_oi - previous_oi


def moneyness(spot: float, strike: float) -> float | None:
    if strike <= 0:
        return None
    return spot / strike


def days_to_expiry(
    expiry: date, 
    now: datetime | None = None,
) -> float:

    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    expiry_dt = datetime.combine(
        expiry,
        time.min,
        tzinfo=timezone.utc,
    )
    return max(
        (expiry_dt - now).total_seconds() / 86400.0, 0.0,)


def liquidity_score(
    *,
    ltp: float | None,
    volume: float | None,
    oi: float | None,
    spread_pct: float | None,
    max_spread_pct: float = 0.05,
) -> float:
    """
    Conservative normalized 0-100 score. It ranks contracts rather than
    pretending to be a probability of fills.
    """
    if ltp is None or ltp <= 0:
        return 0.0

    score = 0.0

    if volume is not None and volume > 0:
        score += min(math.log10(volume + 1) / 6.0, 1.0) * 35.0

    if oi is not None and oi > 0:
        score += min(math.log10(oi + 1) / 7.0, 1.0) * 35.0

    if spread_pct is not None:
        if spread_pct <= max_spread_pct:
            score += 30.0 * (1.0 - spread_pct / max_spread_pct)
        else:
            score += max(0.0, 5.0 * (1.0 - spread_pct))

    return round(min(score, 100.0), 2)


def quality_score(
    *,
    has_ltp: bool,
    has_bid_ask: bool,
    has_iv: bool,
    has_greeks: bool,
    spread_pct: float | None,
) -> float:
    score = 0.0
    score += 30 if has_ltp else 0
    score += 20 if has_bid_ask else 0
    score += 20 if has_iv else 0
    score += 20 if has_greeks else 0

    if spread_pct is not None:
        score += 10 if spread_pct <= 0.05 else 5 if spread_pct <= 0.10 else 0

    return score
