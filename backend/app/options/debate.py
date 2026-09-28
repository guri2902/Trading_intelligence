from __future__ import annotations

from .models import CEPEDebate, OptionCandidate


def _direction_score(candidate: OptionCandidate | None) -> float:
    if candidate is None or not candidate.eligible:
        return 0.0

    q = candidate.quote
    m = candidate.metrics

    score = candidate.rank_score

    if q.open_interest is not None and q.open_interest > 0:
        score += 5.0

    if m.oi_change is not None:
        score += 4.0 if m.oi_change > 0 else -1.0

    if q.volume is not None and q.volume > 0:
        score += min(q.volume / 100000.0, 5.0)

    # Delta magnitude is useful for comparing directional exposure, but it does
    # not become a standalone directional signal.
    if q.delta is not None:
        score += min(abs(q.delta) * 10.0, 5.0)

    return round(score, 2)


def compare_ce_pe(
    *,
    underlying_symbol: str,
    expiry,
    atm_strike: float | None,
    ce_candidate: OptionCandidate | None,
    pe_candidate: OptionCandidate | None,
) -> CEPEDebate:
    ce_score = _direction_score(ce_candidate)
    pe_score = _direction_score(pe_candidate)

    if ce_candidate is None and pe_candidate is None:
        return CEPEDebate(
            underlying_symbol=underlying_symbol,
            expiry=expiry,
            atm_strike=atm_strike,
            ce_candidate=None,
            pe_candidate=None,
            ce_score=0.0,
            pe_score=0.0,
            winner="NO_TRADE",
            reason="No eligible CE or PE contract.",
        )

    if ce_score == pe_score:
        winner = "NO_TRADE"
        reason = "CE and PE candidates are materially tied."
    elif ce_score > pe_score:
        winner = "CE"
        reason = "CE has the stronger liquidity/data/contract-quality profile."
    else:
        winner = "PE"
        reason = "PE has the stronger liquidity/data/contract-quality profile."

    return CEPEDebate(
        underlying_symbol=underlying_symbol,
        expiry=expiry,
        atm_strike=atm_strike,
        ce_candidate=ce_candidate,
        pe_candidate=pe_candidate,
        ce_score=ce_score,
        pe_score=pe_score,
        winner=winner,
        reason=reason,
    )
