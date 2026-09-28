from __future__ import annotations

from .models import AgentInput, AgentVerdict


class RiskAgent:
    name = "RISK"

    def evaluate(
        self,
        data: AgentInput,
        debate_winner: str,
    ) -> AgentVerdict:
        vetoes = []

        option_status = str(data.options.get("status", "UNKNOWN"))
        if option_status != "OK":
            vetoes.append("OPTION_DATA_NOT_OK")

        risk_rr = None
        best = data.strategies.get("best_setup") or {}
        if best:
            risk_rr = best.get("risk_reward")
            if risk_rr is not None and float(risk_rr) < 1.2:
                vetoes.append(f"R:R_TOO_LOW={risk_rr}")

        if data.market.get("stale"):
            vetoes.append("STALE_MARKET_DATA")

        if debate_winner == "NO_TRADE":
            vetoes.append("NO_CLEAR_DEBATE_WINNER")

        return AgentVerdict(
            agent=self.name,
            stance="VETO" if vetoes else "NEUTRAL",
            score=-100 if vetoes else 0,
            confidence=95 if vetoes else 90,
            risks=vetoes,
        )
