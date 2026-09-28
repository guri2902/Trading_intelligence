
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional, Sequence
import hashlib
import json
import math


@dataclass(frozen=True)
class ImprovementCandidate:
    candidate_id: str
    base_version: str
    params: Dict[str, Any]
    rationale: str
    created_at: str = ""


@dataclass
class CandidateEvaluation:
    candidate_id: str
    in_sample: Dict[str, float]
    out_of_sample: Dict[str, float]
    baseline_oos: Dict[str, float]
    improvement_pct: Dict[str, float]
    eligible: bool
    reasons: list[str] = field(default_factory=list)


@dataclass
class PromotionDecision:
    promoted: bool
    candidate_id: Optional[str]
    from_version: str
    to_version: Optional[str]
    reasons: list[str]
    evaluation: Optional[CandidateEvaluation] = None


@dataclass
class SelfImprovementRecord:
    signal_id: str
    outcome: Dict[str, Any]
    agent_feedback: Dict[str, Any]
    candidate_ids: list[str]
    promotion: PromotionDecision


class SelfImprovementEngine:
    """
    Governance layer for iterative improvement.

    The engine never edits strategy source code. Candidate generation and
    evaluation are injected, while promotion is controlled by explicit gates.
    """

    def __init__(
        self,
        candidate_generator: Callable[[Mapping[str, Any], str], Sequence[ImprovementCandidate]],
        evaluator: Callable[[ImprovementCandidate], CandidateEvaluation],
        *,
        min_oos_pnl_improvement_pct: float = 5.0,
        min_oos_expectancy_improvement_pct: float = 2.0,
        max_oos_drawdown_increase_pct: float = 5.0,
        require_positive_oos: bool = True,
    ):
        self.candidate_generator = candidate_generator
        self.evaluator = evaluator
        self.min_oos_pnl_improvement_pct = min_oos_pnl_improvement_pct
        self.min_oos_expectancy_improvement_pct = min_oos_expectancy_improvement_pct
        self.max_oos_drawdown_increase_pct = max_oos_drawdown_increase_pct
        self.require_positive_oos = require_positive_oos

    @staticmethod
    def candidate_id(base_version: str, params: Mapping[str, Any]) -> str:
        blob = json.dumps({"base": base_version, "params": dict(sorted(params.items()))},
                          sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    @staticmethod
    def _num(m: Mapping[str, Any], *keys: str, default: float = 0.0) -> float:
        for key in keys:
            value = m.get(key)
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                return float(value)
        return default

    def gate(self, evaluation: CandidateEvaluation) -> CandidateEvaluation:
        reasons = list(evaluation.reasons)
        oos = evaluation.out_of_sample
        base = evaluation.baseline_oos
        pnl_imp = evaluation.improvement_pct.get("net_pnl", 0.0)
        exp_imp = evaluation.improvement_pct.get("expectancy", 0.0)
        cand_pnl = self._num(oos, "net_pnl", "pnl")
        base_dd = abs(self._num(base, "max_drawdown_pct", "drawdown_pct"))
        cand_dd = abs(self._num(oos, "max_drawdown_pct", "drawdown_pct"))

        if pnl_imp < self.min_oos_pnl_improvement_pct:
            reasons.append(f"oos_pnl_improvement:{pnl_imp:.4f}<{self.min_oos_pnl_improvement_pct}")
        if exp_imp < self.min_oos_expectancy_improvement_pct:
            reasons.append(
                f"oos_expectancy_improvement:{exp_imp:.4f}<{self.min_oos_expectancy_improvement_pct}"
            )
        if cand_dd > base_dd + self.max_oos_drawdown_increase_pct:
            reasons.append(
                f"oos_drawdown_increase:{cand_dd-base_dd:.4f}>{self.max_oos_drawdown_increase_pct}"
            )
        if self.require_positive_oos and cand_pnl <= 0:
            reasons.append("oos_pnl_not_positive")

        evaluation.reasons = reasons
        evaluation.eligible = len(reasons) == 0
        return evaluation

    def improve(
        self,
        *,
        signal_context: Mapping[str, Any],
        current_version: str,
        outcome: Mapping[str, Any],
        agent_feedback: Optional[Mapping[str, Any]] = None,
    ) -> SelfImprovementRecord:
        feedback = dict(agent_feedback or {})
        candidates = list(self.candidate_generator(
            {**dict(signal_context), "outcome": dict(outcome), "agent_feedback": feedback},
            current_version,
        ))
        evaluated = [self.gate(self.evaluator(c)) for c in candidates]
        eligible = [e for e in evaluated if e.eligible]
        best = max(
            eligible,
            key=lambda e: (
                e.improvement_pct.get("net_pnl", -math.inf),
                e.improvement_pct.get("expectancy", -math.inf),
            ),
            default=None,
        )

        if best is None:
            promotion = PromotionDecision(
                promoted=False,
                candidate_id=None,
                from_version=current_version,
                to_version=None,
                reasons=["no_candidate_passed_promotion_gate"],
                evaluation=None,
            )
        else:
            # Version promotion is immutable and deterministic: candidate ID
            # becomes the proposed version. No runtime code is rewritten.
            to_version = f"{current_version}+{best.candidate_id}"
            promotion = PromotionDecision(
                promoted=True,
                candidate_id=best.candidate_id,
                from_version=current_version,
                to_version=to_version,
                reasons=["passed_all_promotion_gates"],
                evaluation=best,
            )

        return SelfImprovementRecord(
            signal_id=str(signal_context.get("signal_id", "")),
            outcome=dict(outcome),
            agent_feedback=feedback,
            candidate_ids=[c.candidate_id for c in candidates],
            promotion=promotion,
        )
