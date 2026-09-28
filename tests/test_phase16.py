from datetime import datetime, timezone

from backend.app.agents.models import AgentInput
from backend.app.agents.orchestrator import AgentOrchestrator
from backend.app.llm.multi_agent import MultiAgentLLMOrchestrator


def fake_client(prompt):
    if prompt.agent_name == "CE_PE_DEBATE":
        return {"response": {"winner": "CE", "ce_case": "Trend aligned", "pe_case": "Weaker counter-case", "contrarian_attack": "Watch extension", "unresolved_conflicts": []}, "provider": "fake", "model": "fake-1", "request_id": "r2"}
    return {"response": {"agent_name": prompt.agent_name, "stance": "NEUTRAL", "score_adjustment": 3, "confidence": 80, "evidence": ["Structured review"], "risks": [], "unresolved": []}, "provider": "fake", "model": "fake-1", "request_id": "r1"}


def payload():
    return AgentInput(
        timestamp=datetime.now(timezone.utc),
        market={"symbol": "NIFTY", "data_quality_status": "PASS", "stale": False},
        features={"ema_alignment": "BULLISH", "price_vs_vwap": "ABOVE"},
        structure={"trend": "BULLISH", "regime": "BULLISH"},
        options={"status": "PASS", "debate": {"winner": "CE", "ce_score": 70, "pe_score": 20}},
        strategies={"best_setup": {"state": "TRIGGERED", "direction": "LONG", "confidence": 70, "risk_reward": 2.0, "invalidation": 25000}},
    )


def test_llm_layer_is_advisory_and_auditable():
    result = MultiAgentLLMOrchestrator(AgentOrchestrator(), enabled_agents=("TECHNICAL", "OPTIONS")).run(payload(), client=fake_client)
    assert result.final_decision.action in {"BUY_CE", "BUY_PE", "WAIT", "NO_TRADE"}
    assert result.final_decision.metadata["llm_debate"]["winner"] == "CE"
    tech = next(a for a in result.agents if a.agent == "TECHNICAL")
    assert tech.metadata["llm_review"]["provider"] == "fake"


def test_llm_output_does_not_bypass_veto():
    data = payload()
    data.market["stale"] = True
    result = MultiAgentLLMOrchestrator(AgentOrchestrator(), enabled_agents=("TECHNICAL",)).run(data, client=fake_client)
    assert result.final_decision.action == "NO_TRADE"
    assert result.final_decision.risk_veto is True or result.final_decision.qa_pass is False
