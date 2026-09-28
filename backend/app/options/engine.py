from __future__ import annotations

from datetime import date, datetime

from .debate import compare_ce_pe
from .models import CEPEDebate, OptionCandidate, OptionQuoteState
from .selection import (
    nearest_atm_strike,
    rank_candidates,
    select_expiry,
)


class OptionsEngine:
    def analyze(
        self,
        quotes: list[OptionQuoteState],
        *,
        preferred_expiry: date | None = None,
        now: datetime | None = None,
        atm_distance: float | None = None,
    ) -> dict:
        if not quotes:
            return {
                "status": "UNAVAILABLE",
                "reason": "No option-chain quotes received.",
                "expiry": None,
                "atm_strike": None,
                "ce": [],
                "pe": [],
                "debate": None,
            }

        expiry = select_expiry(
            quotes,
            preferred_expiry=preferred_expiry,
        )

        if expiry is None:
            return {
                "status": "UNAVAILABLE",
                "reason": "No valid non-expired expiry available.",
                "expiry": None,
                "atm_strike": None,
                "ce": [],
                "pe": [],
                "debate": None,
            }

        atm = nearest_atm_strike(quotes, expiry)

        if atm is None:
            return {
                "status": "UNAVAILABLE",
                "reason": "Underlying spot/strike information is insufficient.",
                "expiry": expiry,
                "atm_strike": None,
                "ce": [],
                "pe": [],
                "debate": None,
            }

        distance = atm_distance or 100000.0

        ce = rank_candidates(
            quotes,
            expiry=expiry,
            option_type="CE",
            now=now,
        )
        pe = rank_candidates(
            quotes,
            expiry=expiry,
            option_type="PE",
            now=now,
        )

        ce_best = self._best_near_atm(
            ce,
            atm,
            distance,
        )
        pe_best = self._best_near_atm(
            pe,
            atm,
            distance,
        )

        underlying = quotes[0].contract.underlying_symbol

        debate = compare_ce_pe(
            underlying_symbol=underlying,
            expiry=expiry,
            atm_strike=atm,
            ce_candidate=ce_best,
            pe_candidate=pe_best,
        )

        return {
            "status": "OK",
            "underlying_symbol": underlying,
            "expiry": expiry.isoformat(),
            "atm_strike": atm,
            "ce": [c.model_dump(mode="json") for c in ce[:10]],
            "pe": [c.model_dump(mode="json") for c in pe[:10]],
            "best_ce": ce_best.model_dump(mode="json") if ce_best else None,
            "best_pe": pe_best.model_dump(mode="json") if pe_best else None,
            "debate": debate.model_dump(mode="json"),
        }

    @staticmethod
    def _best_near_atm(
        candidates: list[OptionCandidate],
        atm: float,
        max_distance: float,
    ) -> OptionCandidate | None:
        eligible = [
            c for c in candidates
            if c.eligible
            and abs(c.quote.contract.strike - atm) <= max_distance
        ]
        if not eligible:
            return None

        # Prefer useful directional exposure near ATM, then liquidity.
        return max(
            eligible,
            key=lambda c: (
                -abs(c.quote.contract.strike - atm),
                c.metrics.liquidity_score,
                c.metrics.quality_score,
            ),
        )
