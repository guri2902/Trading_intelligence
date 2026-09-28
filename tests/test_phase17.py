from datetime import datetime, timezone

from backend.app.agents.models import AgentInput, AgentVerdict, Evidence, DebateResult, FinalDecision, AgentRunResult
from backend.app.signals.fusion import SignalFusionEngine


def make_result():
    agents = [
        AgentVerdict(agent="TECHNICAL", stance="BULLISH", score=80, confidence=85, evidence=[Evidence(source="x", statement="uptrend", strength=90)]),
        AgentVerdict(agent="OPTIONS", stance="BULLISH", score=75, confidence=80),
        AgentVerdict(agent="STRATEGY", stance="BULLISH", score=70, confidence=80),
        AgentVerdict(agent="ML", stance="BULLISH", score=60, confidence=70),
        AgentVerdict(agent="FUNDAMENTAL", stance="NEUTRAL", score=0, confidence=50),
        AgentVerdict(agent="SENTIMENT", stance="BULLISH", score=40, confidence=60),
        AgentVerdict(agent="NEWS_MACRO", stance="BULLISH", score=35, confidence=55),
        AgentVerdict(agent="CONTRARIAN", stance="BEARISH", score=-20, confidence=65),
        AgentVerdict(agent="RISK", stance="NEUTRAL", score=0, confidence=90),
        AgentVerdict(agent="QA", stance="NEUTRAL", score=0, confidence=90),
    ]
    debate = DebateResult(ce_case=agents[0], pe_case=agents[0].model_copy(update={"score": 20}), contrarian=agents[-3], winner="CE", ce_score=80, pe_score=15, reason="CE stronger")
    final = FinalDecision(action="BUY_CE", direction="LONG", confidence=80, score=70, debate=debate, risk_veto=False, qa_pass=True)
    return AgentRunResult(timestamp=datetime.now(timezone.utc), agents=agents, debate=debate, final_decision=final)


def payload(stale=False):
    return AgentInput(
        timestamp=datetime.now(timezone.utc),
        market={"symbol": "NIFTY", "data_quality_status": "PASS", "stale": stale},
        structure={"trend": "BULLISH"},
        options={"status": "PASS", "candidates": [{"option_type": "CE", "strike": 25000, "expiry": "2026-09-17", "ltp": 120.0, "rank_score": 80, "eligible": True, "lot_size": 75, "source": "UPSTOX"}, {"option_type": "PE", "strike": 24900, "expiry": "2026-09-17", "ltp": 105.0, "rank_score": 70, "eligible": True, "lot_size": 75}]},
        strategies={"best_setup": {"state": "TRIGGERED", "direction": "LONG", "risk_reward": 2.0}},
    )


def test_rank_selects_ce_when_edge_and_contract_exist():
    d = SignalFusionEngine().rank(payload(), make_result())
    assert d.action == "BUY_CE"
    assert d.selected is not None
    assert d.selected.plan is not None
    assert d.selected.plan.entry == 120.0


def test_hard_stale_gate_fails_closed():
    d = SignalFusionEngine().rank(payload(stale=True), make_result())
    assert d.action == "NO_TRADE"
    assert "STALE_MARKET_DATA" in d.hard_gates


def test_missing_contract_prevents_trade():
    p = payload()
    p.options["candidates"] = []
    d = SignalFusionEngine().rank(p, make_result())
    assert d.action == "WAIT"
    assert d.selected is None
