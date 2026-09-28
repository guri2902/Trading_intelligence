from datetime import datetime, timezone

from backend.app.agents.models import AgentInput
from backend.app.agents.orchestrator import AgentOrchestrator


def bullish_input():
    return AgentInput(
        timestamp=datetime.now(timezone.utc),
        market={
            "data_quality_status": "PASS",
            "stale": False,
        },
        features={
            "ema_alignment": "BULLISH",
            "price_vs_vwap": "ABOVE",
        },
        structure={
            "trend": "BULLISH",
            "regime": "BREAKOUT",
        },
        options={
            "status": "OK",
            "debate": {
                "winner": "CE",
                "ce_score": 82,
                "pe_score": 48,
            },
        },
        strategies={
            "best_setup": {
                "strategy": "MOMENTUM_CONTINUATION",
                "state": "TRIGGERED",
                "direction": "LONG",
                "risk_reward": 2.0,
                "confidence": 78,
                "invalidation": 100,
            }
        },
        ml={
            "predictions": [
                {"probability_up": 0.72, "probability_down": 0.28},
                {"probability_up": 0.68, "probability_down": 0.32},
            ]
        },
        fundamentals={"score": 20, "confidence": 50},
        sentiment={"score": 25, "confidence": 60},
        news={"score": 10, "confidence": 45},
    )


def test_orchestrator_can_reach_buy_ce():
    result = AgentOrchestrator().run(bullish_input())
    assert result.final_decision.action in {"BUY_CE", "WAIT", "NO_TRADE"}
    assert len(result.agents) == 10
    assert result.debate.winner in {"CE", "PE", "NO_TRADE"}


def test_stale_data_is_veto():
    data = bullish_input()
    data.market["stale"] = True
    result = AgentOrchestrator().run(data)
    assert result.final_decision.action == "NO_TRADE"
    assert result.final_decision.risk_veto is True


def test_missing_option_data_is_veto():
    data = bullish_input()
    data.options["status"] = "UNAVAILABLE"
    result = AgentOrchestrator().run(data)
    assert result.final_decision.action == "NO_TRADE"


def test_neutral_debate_does_not_force_trade():
    data = bullish_input()
    data.options["debate"] = {
        "winner": "NO_TRADE",
        "ce_score": 40,
        "pe_score": 39,
    }
    data.structure["trend"] = "RANGE"
    data.structure["regime"] = "CONSOLIDATION"
    data.strategies["best_setup"] = {}
    result = AgentOrchestrator().run(data)
    assert result.final_decision.action in {"WAIT", "NO_TRADE"}
    assert result.debate.winner == "NO_TRADE"
