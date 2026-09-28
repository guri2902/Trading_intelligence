from __future__ import annotations

from datetime import date, datetime, timezone

from .metrics import (
    days_to_expiry,
    extrinsic_value,
    intrinsic_value,
    liquidity_score,
    mid_price,
    moneyness,
    oi_change,
    quality_score,
    spread_metrics,
)
from .models import OptionCandidate, OptionQuoteState


def select_expiry(
    quotes: list[OptionQuoteState],
    *,
    preferred_expiry: date | None = None,
    min_days: float = 0.0,
) -> date | None:
    expiries = sorted({
        q.contract.expiry
        for q in quotes
        if days_to_expiry(q.contract.expiry) >= min_days
    })

    if preferred_expiry:
        if preferred_expiry in expiries:
            return preferred_expiry
        return None

    return expiries[0] if expiries else None


def nearest_atm_strike(
    quotes: list[OptionQuoteState],
    expiry: date,
) -> float | None:
    eligible = [
        q for q in quotes
        if q.contract.expiry == expiry
        and q.underlying_spot is not None
    ]
    if not eligible:
        return None

    spot = eligible[0].underlying_spot
    strikes = sorted({q.contract.strike for q in eligible})
    if spot is None or not strikes:
        return None

    return min(strikes, key=lambda strike: abs(strike - spot))


def enrich_candidate(
    quote: OptionQuoteState,
    *,
    now: datetime | None = None,
    min_ltp: float = 0.0,
    max_spread_pct: float = 0.10,
    min_liquidity_score: float = 25.0,
) -> OptionCandidate:
    reasons: list[str] = []
    c = quote.contract
    spot = quote.underlying_spot

    if spot is None or spot <= 0:
        reasons.append("MISSING_UNDERLYING_SPOT")

    if quote.ltp is None or quote.ltp <= min_ltp:
        reasons.append("MISSING_OR_INVALID_LTP")

    spread, spread_pct = spread_metrics(
        quote.bid,
        quote.ask,
        quote.ltp,
    )

    if spread_pct is None:
        reasons.append("BID_ASK_UNAVAILABLE")
    elif spread_pct > max_spread_pct:
        reasons.append("WIDE_SPREAD")

    if quote.volume is None or quote.volume <= 0:
        reasons.append("LOW_OR_MISSING_VOLUME")

    if quote.open_interest is None or quote.open_interest <= 0:
        reasons.append("LOW_OR_MISSING_OI")

    intrinsic = None
    extrinsic = None
    moneyness_value = None

    if spot is not None:
        intrinsic = intrinsic_value(spot, c.strike, c.option_type)
        if quote.ltp is not None:
            extrinsic = extrinsic_value(
                quote.ltp,
                spot,
                c.strike,
                c.option_type,
            )
        moneyness_value = moneyness(spot, c.strike)

    oi_delta = oi_change(
        quote.open_interest,
        quote.previous_oi,
    )

    liq = liquidity_score(
        ltp=quote.ltp,
        volume=quote.volume,
        oi=quote.open_interest,
        spread_pct=spread_pct,
        max_spread_pct=max_spread_pct,
    )

    has_greeks = all(
        value is not None
        for value in (
            quote.delta,
            quote.gamma,
            quote.theta,
            quote.vega,
        )
    )

    qscore = quality_score(
        has_ltp=quote.ltp is not None,
        has_bid_ask=quote.bid is not None and quote.ask is not None,
        has_iv=quote.iv is not None,
        has_greeks=has_greeks,
        spread_pct=spread_pct,
    )

    if liq < min_liquidity_score:
        reasons.append("INSUFFICIENT_LIQUIDITY")

    dte = days_to_expiry(c.expiry, now)

    if dte <= 0:
        reasons.append("EXPIRED_OR_EXPIRING")

    # Do not prefer a contract simply because it is cheap.
    # The rank score rewards liquidity, data quality and moderate spreads.
    rank = (
        liq * 0.45
        + qscore * 0.25
        + max(0.0, 100.0 - min((spread_pct or 1.0) * 1000.0, 100.0)) * 0.20
        + (10.0 if quote.iv is not None else 0.0)
    )

    metrics = {
        "intrinsic_value": intrinsic,
        "extrinsic_value": extrinsic,
        "mid_price": mid_price(quote.bid, quote.ask, quote.ltp),
        "spread": spread,
        "spread_pct": spread_pct,
        "oi_change": oi_delta,
        "moneyness": moneyness_value,
        "days_to_expiry": dte,
        "liquidity_score": liq,
        "quality_score": qscore,
    }

    return OptionCandidate(
        quote=quote,
        metrics=metrics,
        rejection_reasons=reasons,
        eligible=len(reasons) == 0,
        rank_score=round(rank, 2),
    )


def rank_candidates(
    quotes: list[OptionQuoteState],
    *,
    expiry: date,
    option_type: str | None = None,
    now: datetime | None = None,
) -> list[OptionCandidate]:
    candidates = []

    for quote in quotes:
        if quote.contract.expiry != expiry:
            continue
        if option_type and quote.contract.option_type != option_type:
            continue

        candidates.append(enrich_candidate(
            quote,
            now=now,
        ))

    return sorted(
        candidates,
        key=lambda c: (
            c.eligible,
            c.rank_score,
        ),
        reverse=True,
    )


def choose_near_atm(
    candidates: list[OptionCandidate],
    *,
    atm_strike: float,
    max_strike_distance: float,
) -> OptionCandidate | None:
    eligible = [
        c for c in candidates
        if c.eligible
        and abs(c.quote.contract.strike - atm_strike) <= max_strike_distance
    ]
    if not eligible:
        return None

    return max(
        eligible,
        key=lambda c: (
            -abs(c.quote.contract.strike - atm_strike),
            c.rank_score,
        ),
    )
