from __future__ import annotations

import time
from typing import Any, Callable

from pydantic import BaseModel, Field

from .agent_bridge import LLMResearchBridge
from .models import StructuredAgentPrompt
from ..agents.models import AgentInput, AgentRunResult, AgentVerdict


class LLMReview(BaseModel):
    agent_name: str
    stance: str = "UNKNOWN"
    score_adjustment: float = Field(default=0, ge=-20, le=20)
    confidence: float = Field(default=0, ge=0, le=100)
    evidence: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    request_id: str | None = None
    latency_ms: float | None = None


class LLMDebate(BaseModel):
    winner: str = "NO_TRADE"
    ce_case: str = ""
    pe_case: str = ""
    contrarian_attack: str = ""
    unresolved_conflicts: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    request_id: str | None = None
    latency_ms: float | None = None


class MultiAgentLLMOrchestrator:
    """Optional LLM critic layer over the deterministic Phase 13/15 pipeline.

    The deterministic AgentOrchestrator always runs first. LLM outputs are
    attached as audit metadata and can only contribute bounded score nudges to
    the review view; they cannot bypass data/risk/QA vetoes.
    """

    DEFAULT_AGENTS = (
        "TECHNICAL",
        "OPTIONS",
        "STRATEGY",
        "ML",
        "FUNDAMENTAL",
        "SENTIMENT",
        "NEWS_MACRO",
        "CONTRARIAN",
    )

    def __init__(
        self,
        base_orchestrator: Any,
        bridge: LLMResearchBridge | None = None,
        *,
        enabled_agents: tuple[str, ...] | None = None,
    ) -> None:
        self.base = base_orchestrator
        self.bridge = bridge or LLMResearchBridge()
        self.enabled_agents = enabled_agents or self.DEFAULT_AGENTS

    def run(
        self,
        data: AgentInput,
        *,
        provider: str | None = None,
        model: str | None = None,
        client: Callable[[StructuredAgentPrompt], dict[str, Any]] | None = None,
    ) -> AgentRunResult:
        result = self.base.run(data)
        for verdict in result.agents:
            if verdict.agent not in self.enabled_agents:
                continue
            review = self._review(verdict, data, provider, model, client)
            verdict.metadata["llm_review"] = review.model_dump(mode="json")
            verdict.metadata["provider"] = review.provider
            verdict.metadata["model"] = review.model
            verdict.metadata["request_id"] = review.request_id
            verdict.metadata["latency_ms"] = review.latency_ms
            verdict.questions.extend(review.unresolved[:3])
            verdict.risks.extend(review.risks[:3])

        debate_review = self._debate(result, data, provider, model, client)
        result.final_decision.metadata["llm_debate"] = debate_review.model_dump(mode="json")
        result.final_decision.metadata["llm_review_policy"] = (
            "LLM is advisory only; deterministic market/risk/QA gates remain authoritative."
        )
        return result

    def _review(
        self,
        verdict: AgentVerdict,
        data: AgentInput,
        provider: str | None,
        model: str | None,
        client: Callable[[StructuredAgentPrompt], dict[str, Any]] | None,
    ) -> LLMReview:
        prompt = StructuredAgentPrompt(
            agent_name=verdict.agent,
            task=(
                "Audit the deterministic agent verdict. Identify only evidence-grounded "
                "supporting facts, contradictions, missing evidence, and risk flags. "
                "Do not replace the deterministic verdict. Keep score_adjustment within ±20."
            ),
            data={
                "agent_verdict": verdict.model_dump(mode="json"),
                "market": data.market,
                "features": data.features,
                "structure": data.structure,
                "options": data.options,
                "strategies": data.strategies,
                "ml": data.ml,
                "fundamentals": data.fundamentals,
                "sentiment": data.sentiment,
                "news": data.news,
            },
            schema={
                "agent_name": "string",
                "stance": "BULLISH|BEARISH|NEUTRAL|UNKNOWN",
                "score_adjustment": "number between -20 and 20",
                "confidence": "0 to 100",
                "evidence": "array of strings",
                "risks": "array of strings",
                "unresolved": "array of strings",
            },
            constraints=[
                "Use only supplied structured data.",
                "Do not invent prices, Greeks, OI, IV, news, or fundamentals.",
                "Do not override deterministic gates.",
            ],
        )
        started = time.perf_counter()
        response = client(prompt) if client else self.bridge.analyze(prompt, provider=provider, model=model)
        latency = (time.perf_counter() - started) * 1000
        payload = response.get("response", response)
        return LLMReview(
            agent_name=verdict.agent,
            stance=str(payload.get("stance", "UNKNOWN")).upper(),
            score_adjustment=max(-20, min(20, float(payload.get("score_adjustment", 0) or 0))),
            confidence=max(0, min(100, float(payload.get("confidence", 0) or 0))),
            evidence=[str(x) for x in payload.get("evidence", [])][:6],
            risks=[str(x) for x in payload.get("risks", [])][:6],
            unresolved=[str(x) for x in payload.get("unresolved", [])][:6],
            provider=response.get("provider"),
            model=response.get("model"),
            request_id=response.get("request_id"),
            latency_ms=round(latency, 3),
        )

    def _debate(
        self,
        result: AgentRunResult,
        data: AgentInput,
        provider: str | None,
        model: str | None,
        client: Callable[[StructuredAgentPrompt], dict[str, Any]] | None,
    ) -> LLMDebate:
        prompt = StructuredAgentPrompt(
            agent_name="CE_PE_DEBATE",
            task=(
                "Challenge the deterministic CE/PE debate. Compare both cases, attack the "
                "stronger side, and identify unresolved conflicts. You may recommend CE, PE, "
                "or NO_TRADE, but the recommendation is advisory and must not override gates."
            ),
            data={
                "deterministic_debate": result.debate.model_dump(mode="json"),
                "agents": [a.model_dump(mode="json") for a in result.agents],
                "market": data.market,
                "options": data.options,
                "risk": data.risk,
            },
            schema={
                "winner": "CE|PE|NO_TRADE",
                "ce_case": "string",
                "pe_case": "string",
                "contrarian_attack": "string",
                "unresolved_conflicts": "array of strings",
            },
            constraints=[
                "No guaranteed outcome.",
                "No invented market facts.",
                "NO_TRADE is valid when evidence conflicts or is insufficient.",
            ],
        )
        started = time.perf_counter()
        response = client(prompt) if client else self.bridge.analyze(prompt, provider=provider, model=model)
        latency = (time.perf_counter() - started) * 1000
        payload = response.get("response", response)
        winner = str(payload.get("winner", "NO_TRADE")).upper()
        if winner not in {"CE", "PE", "NO_TRADE"}:
            winner = "NO_TRADE"
        return LLMDebate(
            winner=winner,
            ce_case=str(payload.get("ce_case", ""))[:1200],
            pe_case=str(payload.get("pe_case", ""))[:1200],
            contrarian_attack=str(payload.get("contrarian_attack", ""))[:1200],
            unresolved_conflicts=[str(x) for x in payload.get("unresolved_conflicts", [])][:8],
            provider=response.get("provider"),
            model=response.get("model"),
            request_id=response.get("request_id"),
            latency_ms=round(latency, 3),
        )
