from __future__ import annotations

from .base import BaseAgent
from .debate import run_debate
from .models import AgentInput, AgentRunResult, FinalDecision, AgentVerdict
from .risk import RiskAgent
from .specialists import QAAgent, SPECIALIST_AGENTS


class AgentOrchestrator:
    def __init__(self):
        self.specialists: list[BaseAgent] = [
            cls() for cls in SPECIALIST_AGENTS
        ]
        self.risk = RiskAgent()
        self.qa = QAAgent()

    def run(self, data: AgentInput) -> AgentRunResult:
        specialist_results: list[AgentVerdict] = []

        for agent in self.specialists:
            specialist_results.append(agent.evaluate(data))

        debate = run_debate(specialist_results)
        risk = self.risk.evaluate(data, debate.winner)
        qa = self.qa.evaluate(data)

        all_agents = specialist_results + [risk, qa]

        decision = self._finalize(
            data,
            debate=debate,
            risk=risk,
            qa=qa,
        )

        return AgentRunResult(
            timestamp=data.timestamp,
            agents=all_agents,
            debate=debate,
            final_decision=decision,
        )

    def _finalize(
        self,
        data: AgentInput,
        *,
        debate,
        risk: AgentVerdict,
        qa: AgentVerdict,
    ) -> FinalDecision:
        blockers = list(risk.risks) + list(qa.risks)
        rationale = [debate.reason]
        invalidation = []

        if risk.stance == "VETO":
            return FinalDecision(
                action="NO_TRADE",
                direction="NONE",
                confidence=0,
                score=-100,
                rationale=rationale,
                invalidation=invalidation,
                blockers=blockers,
                debate=debate,
                risk_veto=True,
                qa_pass=False,
            )

        if qa.stance == "VETO":
            return FinalDecision(
                action="NO_TRADE",
                direction="NONE",
                confidence=0,
                score=-100,
                rationale=rationale,
                blockers=blockers,
                debate=debate,
                risk_veto=False,
                qa_pass=False,
            )

        if debate.winner == "CE":
            action = "BUY_CE"
            direction = "LONG"
            raw_score = debate.ce_score - debate.pe_score
        elif debate.winner == "PE":
            action = "BUY_PE"
            direction = "SHORT"
            raw_score = debate.pe_score - debate.ce_score
        else:
            action = "WAIT"
            direction = "NONE"
            raw_score = 0

        confidence = min(95.0, max(0.0, raw_score * 1.2))

        best = data.strategies.get("best_setup") or {}
        if best.get("invalidation") is not None:
            invalidation.append(
                f"Underlying invalidation={best['invalidation']}"
            )

        return FinalDecision(
            action=action,
            direction=direction,
            confidence=confidence,
            score=raw_score,
            rationale=rationale,
            invalidation=invalidation,
            blockers=blockers,
            debate=debate,
            risk_veto=False,
            qa_pass=True,
        )
