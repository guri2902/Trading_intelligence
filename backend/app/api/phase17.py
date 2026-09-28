from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..agents.models import AgentInput
from ..agents.orchestrator import AgentOrchestrator
from ..llm.multi_agent import MultiAgentLLMOrchestrator
from ..signals.fusion import SignalFusionEngine
from ..data_gates.live_signal import evaluate_live_signal_gate

router = APIRouter(prefix="/phase17", tags=["phase17"])


class SignalRequest(BaseModel):
    data: AgentInput
    use_llm: bool = True
    provider: str | None = None
    model: str | None = None
    enabled_agents: list[str] | None = Field(default=None, max_length=20)


def _clean_optional(value: str | None) -> str | None:
    """
    Treat empty strings and Swagger's generic 'string' placeholder
    as missing values.
    """
    if value is None:
        return None

    value = value.strip()

    if not value or value.lower() == "string":
        return None

    return value


@router.get("/health")
def health():
    return {
        "status": "ok",
        "phase": 17,
        "mode": "signal_fusion",
        "live_execution": False,
    }


@router.post("/signal")
def signal(request: SignalRequest):
    enabled = (
        tuple(request.enabled_agents)
        if request.enabled_agents
        else None
    )

    # ---------------------------------------------------------
    # 1. LIVE DATA SAFETY GATE
    # ---------------------------------------------------------
    # Run this BEFORE LLM/agent processing so stale/closed/
    # inconsistent market data never reaches the reasoning layer.
    gate = evaluate_live_signal_gate(request.data)

    # ---------------------------------------------------------
    # 2. CLEAN OPTIONAL LLM PARAMETERS
    # ---------------------------------------------------------
    provider = _clean_optional(request.provider)
    model = _clean_optional(request.model)

    # ---------------------------------------------------------
    # 3. RUN AGENTS / LLM ONLY WHEN DATA IS ALLOWED
    # ---------------------------------------------------------
    if gate.passed:
        if request.use_llm:
            runner = MultiAgentLLMOrchestrator(
                AgentOrchestrator(),
                enabled_agents=enabled,
            )

            result = runner.run(
                request.data,
                provider=provider,
                model=model,
            )
        else:
            result = AgentOrchestrator().run(request.data)

    else:
        # Do NOT call the external LLM with invalid/stale data.
        # Keep deterministic agent processing so the response
        # retains the normal signal structure.
        result = AgentOrchestrator().run(request.data)

    # ---------------------------------------------------------
    # 4. EXISTING DETERMINISTIC SIGNAL FUSION
    # ---------------------------------------------------------
    decision = SignalFusionEngine().rank(
        request.data,
        result,
    )

    # ---------------------------------------------------------
    # 5. LIVE GATE HAS FINAL AUTHORITY
    # ---------------------------------------------------------
    if not gate.passed:
        decision = decision.model_copy(
            update={
                "action": "NO_TRADE",
                "direction": "NONE",
                "confidence": 0.0,
                "score": 0.0,
                "selected": None,
                "hard_gates": list(
                    dict.fromkeys(
                        [
                            *decision.hard_gates,
                            *gate.reasons,
                        ]
                    )
                ),
            }
        )

    # ---------------------------------------------------------
    # 6. RESPONSE
    # ---------------------------------------------------------
    payload = decision.model_dump(mode="json")
    payload["live_signal_gate"] = gate.as_dict()

    return payload