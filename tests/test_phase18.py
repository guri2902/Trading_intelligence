from datetime import datetime

from backend.app.agents.models import AgentInput, AgentVerdict, Evidence, DebateResult, FinalDecision, AgentRunResult
from backend.app.risk.engine import RiskEngine
from backend.app.risk.models import AccountRiskContext
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
    return AgentRunResult(timestamp=datetime.now(), agents=agents, debate=debate, final_decision=final)


def payload():
    return AgentInput(
        timestamp=datetime.now(),
        market={"symbol": "NIFTY", "data_quality_status": "PASS", "stale": False},
        structure={"trend": "BULLISH"},
        options={"status": "PASS", "candidates": [{"option_type": "CE", "strike": 25000, "expiry": "2026-09-17", "ltp": 120.0, "stop_loss": 116.0, "rank_score": 80, "eligible": True, "lot_size": 75, "source": "UPSTOX"}]},
        strategies={"best_setup": {"state": "TRIGGERED", "direction": "LONG", "risk_reward": 2.0}},
    )


def signal():
    return SignalFusionEngine().rank(payload(), make_result())


def base_account(**kwargs):
    return AccountRiskContext(
        equity=50000,
        risk_per_trade_pct=1.0,
        max_daily_loss=1000,
        daily_profit_lock=2000,
        max_concurrent_risk=1500,
        max_trades_per_day=5,
        max_open_positions=2,
        **kwargs,
    )


def test_sizes_whole_lots_and_approves():
    d = RiskEngine().evaluate(signal(), base_account())
    assert d.approved is True
    assert d.final_action == "BUY_CE"
    assert d.assessment.lots == 1  # 500 rupee budget allows one 75-unit lot at 4 rupees/unit risk
    assert d.assessment.quantity == 75


def test_daily_loss_limit_blocks():
    d = RiskEngine().evaluate(signal(), base_account(realized_pnl_today=-1000))
    assert not d.approved
    assert "DAILY_LOSS_LIMIT_REACHED" in d.assessment.reason_codes


def test_profit_lock_blocks():
    d = RiskEngine().evaluate(signal(), base_account(realized_pnl_today=2000))
    assert not d.approved
    assert "DAILY_PROFIT_LOCK_REACHED" in d.assessment.reason_codes


def test_concurrent_risk_limits_position_size():
    d = RiskEngine().evaluate(signal(), base_account(open_risk=1400))
    assert not d.approved
    assert "RISK_BUDGET_BELOW_ONE_LOT" in d.assessment.reason_codes


def test_trade_count_and_position_count_block():
    assert "MAX_TRADES_PER_DAY_REACHED" in RiskEngine().evaluate(signal(), base_account(trades_today=5)).assessment.reason_codes
    assert "MAX_OPEN_POSITIONS_REACHED" in RiskEngine().evaluate(signal(), base_account(open_positions=2)).assessment.reason_codes


def test_drawdown_and_square_off_block():
    dd = RiskEngine().evaluate(signal(), base_account(peak_equity=60000, max_drawdown_pct=10))
    assert "MAX_DRAWDOWN_REACHED" in dd.assessment.reason_codes
    so = RiskEngine().evaluate(signal(), base_account(square_off_time="15:15", market_timestamp=datetime(2026, 9, 10, 15, 16)))
    assert "SQUARE_OFF_WINDOW" in so.assessment.reason_codes
