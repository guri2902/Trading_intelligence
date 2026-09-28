from __future__ import annotations

from .base import BaseAgent
from .models import AgentInput, AgentVerdict


def _trend_stance(trend: str) -> tuple[str, float]:
    if trend == "BULLISH":
        return "BULLISH", 70
    if trend == "BEARISH":
        return "BEARISH", 70
    return "NEUTRAL", 0


class DataAgent(BaseAgent):
    name = "DATA"

    def evaluate(self, data: AgentInput) -> AgentVerdict:
        quality = str(data.market.get("data_quality_status", "UNKNOWN")).upper()
        stale = bool(data.market.get("stale", False))
        option_status = str(data.options.get("status", "UNKNOWN")).upper()

        risks = []
        if quality not in {"PASS", "OK"}:
            risks.append(f"MARKET_DATA_QUALITY={quality}")
        if stale:
            risks.append("MARKET_DATA_STALE")
        if option_status in {"UNAVAILABLE", "FAIL"}:
            risks.append("OPTION_DATA_UNAVAILABLE")

        return AgentVerdict(
            agent=self.name,
            stance="VETO" if risks else "NEUTRAL",
            score=-100 if risks else 0,
            confidence=95 if risks else 90,
            evidence=[
                self.evidence(
                    "DATA_LAYER",
                    f"market_quality={quality}, option_status={option_status}",
                    100,
                )
            ],
            risks=risks,
        )


class TechnicalAgent(BaseAgent):
    name = "TECHNICAL"

    def evaluate(self, data: AgentInput) -> AgentVerdict:
        trend = data.structure.get("trend", "RANGE")
        regime = data.structure.get("regime", "UNKNOWN")
        ema_alignment = data.features.get("ema_alignment")
        vwap = data.features.get("price_vs_vwap")

        stance, score = _trend_stance(trend)
        evidence = [
            self.evidence("STRUCTURE", f"trend={trend}, regime={regime}", 80),
        ]

        if ema_alignment == "BULLISH":
            score += 10
            evidence.append(self.evidence("FEATURES", "EMA alignment bullish", 70))
        elif ema_alignment == "BEARISH":
            score -= 10
            evidence.append(self.evidence("FEATURES", "EMA alignment bearish", 70))

        if vwap == "ABOVE" and score >= 0:
            score += 5
        elif vwap == "BELOW" and score <= 0:
            score -= 5

        score = max(-100, min(100, score))
        stance = "BULLISH" if score > 15 else "BEARISH" if score < -15 else "NEUTRAL"

        return AgentVerdict(
            agent=self.name,
            stance=stance,
            score=score,
            confidence=72,
            evidence=evidence,
            risks=["Mixed EMA/VWAP structure"] if stance == "NEUTRAL" else [],
        )


class OptionsAgent(BaseAgent):
    name = "OPTIONS"

    def evaluate(self, data: AgentInput) -> AgentVerdict:
        debate = data.options.get("debate") or {}
        winner = debate.get("winner", "NO_TRADE")
        ce = float(debate.get("ce_score", 0) or 0)
        pe = float(debate.get("pe_score", 0) or 0)

        score = 0.0
        stance = "NEUTRAL"
        if winner == "CE":
            score = min(100, ce)
            stance = "BULLISH"
        elif winner == "PE":
            score = -min(100, pe)
            stance = "BEARISH"
        else:
            score = 0.0
            stance = "NEUTRAL"

        return AgentVerdict(
            agent=self.name,
            stance=stance,
            score=score,
            confidence=70 if winner != "NO_TRADE" else 35,
            evidence=[
                self.evidence(
                    "OPTION_ENGINE",
                    f"CE={ce:.1f}, PE={pe:.1f}, winner={winner}",
                    85,
                )
            ],
            risks=["No clear CE/PE contract winner"] if winner == "NO_TRADE" else [],
            metadata={"debate_winner": winner},
        )


class StrategyAgent(BaseAgent):
    name = "STRATEGY"

    def evaluate(self, data: AgentInput) -> AgentVerdict:
        best = data.strategies.get("best_setup") or {}
        direction = best.get("direction", "NONE")
        state = best.get("state", "NO_SETUP")
        rr = best.get("risk_reward")
        confidence = float(best.get("confidence", 0) or 0)

        if state != "TRIGGERED":
            return AgentVerdict(
                agent=self.name,
                stance="NEUTRAL",
                score=0,
                confidence=max(20, confidence),
                evidence=[self.evidence("STRATEGIES", f"state={state}", 50)],
                risks=["No triggered strategy"],
            )

        if direction == "LONG":
            stance, score = "BULLISH", min(100, confidence)
        elif direction == "SHORT":
            stance, score = "BEARISH", -min(100, confidence)
        else:
            stance, score = "NEUTRAL", 0

        risks = []
        if rr is not None and rr < 1.2:
            risks.append(f"LOW_RR={rr:.2f}")

        return AgentVerdict(
            agent=self.name,
            stance=stance if not risks else "NEUTRAL",
            score=score if not risks else score * 0.5,
            confidence=confidence,
            evidence=[
                self.evidence(
                    "STRATEGY_ENGINE",
                    f"best={best.get('strategy')}, state={state}, direction={direction}",
                    85,
                )
            ],
            risks=risks,
        )


class MLAgent(BaseAgent):
    name = "ML"

    def evaluate(self, data: AgentInput) -> AgentVerdict:
        predictions = data.ml.get("predictions") or []
        if not predictions:
            return AgentVerdict(
                agent=self.name,
                stance="UNKNOWN",
                score=0,
                confidence=20,
                risks=["ML prediction unavailable"],
            )

        up = []
        down = []
        for p in predictions:
            if p.get("probability_up") is not None:
                up.append(float(p["probability_up"]))
            if p.get("probability_down") is not None:
                down.append(float(p["probability_down"]))

        if not up:
            return AgentVerdict(
                agent=self.name,
                stance="UNKNOWN",
                score=0,
                confidence=20,
                risks=["ML probabilities unavailable"],
            )

        up_avg = sum(up) / len(up)
        down_avg = sum(down) / len(down)
        edge = up_avg - down_avg

        if edge > 0.08:
            stance = "BULLISH"
        elif edge < -0.08:
            stance = "BEARISH"
        else:
            stance = "NEUTRAL"

        return AgentVerdict(
            agent=self.name,
            stance=stance,
            score=max(-100, min(100, edge * 100)),
            confidence=max(up_avg, down_avg) * 100,
            evidence=[
                self.evidence(
                    "ML",
                    f"avg_up={up_avg:.3f}, avg_down={down_avg:.3f}",
                    75,
                )
            ],
        )


class FundamentalAgent(BaseAgent):
    name = "FUNDAMENTAL"

    def evaluate(self, data: AgentInput) -> AgentVerdict:
        score = float(data.fundamentals.get("score", 0) or 0)
        score = max(-100, min(100, score))
        stance = (
            "BULLISH" if score > 15
            else "BEARISH" if score < -15
            else "NEUTRAL"
        )

        return AgentVerdict(
            agent=self.name,
            stance=stance,
            score=score,
            confidence=float(data.fundamentals.get("confidence", 30) or 30),
            evidence=[
                self.evidence(
                    "FUNDAMENTALS",
                    str(data.fundamentals.get("summary", "No fundamental data")),
                    50,
                )
            ],
            risks=data.fundamentals.get("risks", []) or [],
        )


class SentimentAgent(BaseAgent):
    name = "SENTIMENT"

    def evaluate(self, data: AgentInput) -> AgentVerdict:
        score = float(data.sentiment.get("score", 0) or 0)
        score = max(-100, min(100, score))
        stance = (
            "BULLISH" if score > 15
            else "BEARISH" if score < -15
            else "NEUTRAL"
        )
        return AgentVerdict(
            agent=self.name,
            stance=stance,
            score=score,
            confidence=float(data.sentiment.get("confidence", 30) or 30),
            evidence=[
                self.evidence(
                    "SENTIMENT",
                    str(data.sentiment.get("summary", "No sentiment data")),
                    45,
                )
            ],
        )


class NewsMacroAgent(BaseAgent):
    name = "NEWS_MACRO"

    def evaluate(self, data: AgentInput) -> AgentVerdict:
        score = float(data.news.get("score", 0) or 0)
        score = max(-100, min(100, score))

        # High-impact event flags reduce confidence without forcing a side.
        event_risk = bool(data.news.get("high_impact_event", False))
        stance = (
            "BULLISH" if score > 15
            else "BEARISH" if score < -15
            else "NEUTRAL"
        )

        risks = list(data.news.get("risks", []) or [])
        if event_risk:
            risks.append("HIGH_IMPACT_MACRO_EVENT")

        return AgentVerdict(
            agent=self.name,
            stance=stance,
            score=score,
            confidence=(
                float(data.news.get("confidence", 30) or 30)
                * (0.6 if event_risk else 1.0)
            ),
            evidence=[
                self.evidence(
                    "NEWS_MACRO",
                    str(data.news.get("summary", "No news/macro data")),
                    50,
                )
            ],
            risks=risks,
        )


class QAAgent(BaseAgent):
    name = "QA"

    def evaluate(self, data: AgentInput) -> AgentVerdict:
        issues = []

        if not data.timestamp:
            issues.append("MISSING_TIMESTAMP")
        if not data.features:
            issues.append("MISSING_FEATURES")
        if not data.structure:
            issues.append("MISSING_STRUCTURE")
        if not data.options:
            issues.append("MISSING_OPTIONS")
        if not data.strategies:
            issues.append("MISSING_STRATEGIES")

        return AgentVerdict(
            agent=self.name,
            stance="VETO" if issues else "NEUTRAL",
            score=-100 if issues else 0,
            confidence=95 if issues else 90,
            evidence=[
                self.evidence(
                    "QA",
                    "Required analytic state present" if not issues else str(issues),
                    100,
                )
            ],
            risks=issues,
        )


SPECIALIST_AGENTS = [
    DataAgent,
    TechnicalAgent,
    OptionsAgent,
    StrategyAgent,
    MLAgent,
    FundamentalAgent,
    SentimentAgent,
    NewsMacroAgent,
]
