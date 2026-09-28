from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..agents.models import AgentInput
from ..agents.orchestrator import AgentOrchestrator
from ..llm.multi_agent import MultiAgentLLMOrchestrator
from ..risk.engine import RiskEngine
from ..risk.models import AccountRiskContext
from ..signals.fusion import SignalFusionEngine
from ..data_gates.live_signal import evaluate_live_signal_gate

router = APIRouter(prefix="/phase18", tags=["phase18"])


class RiskSignalRequest(BaseModel):
    data: AgentInput
    account: AccountRiskContext
    use_llm: bool = True
    provider: str | None = None
    model: str | None = None


@router.get("/health")
def health():
    return {"status": "ok", "phase": 18, "mode": "portfolio_risk", "live_execution": False}


@router.post("/risk-check")
def risk_check(request: RiskSignalRequest):
    if request.use_llm:
        result = MultiAgentLLMOrchestrator(AgentOrchestrator()).run(
            request.data, provider=request.provider, model=request.model
        )
    else:
        result = AgentOrchestrator().run(request.data)
    signal = SignalFusionEngine().rank(request.data, result)
    gate = evaluate_live_signal_gate(request.data)
    if not gate.passed:
        signal = signal.model_copy(
            update={
                "action": "NO_TRADE",
                "direction": "NONE",
                "confidence": 0.0,
                "score": 0.0,
                "selected": None,
                "hard_gates": list(dict.fromkeys([*signal.hard_gates, *gate.reasons])),
            }
        )
    risk = RiskEngine().evaluate(signal, request.account)
    return {
        "signal": signal.model_dump(mode="json"),
        "risk": risk.model_dump(mode="json"),
        "live_signal_gate": gate.as_dict(),
    }