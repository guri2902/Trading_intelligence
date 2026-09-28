from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromotionGate:
    passed: bool
    reasons: list[str]
    checks: dict[str, bool]


def evaluate_promotion(
    *,
    in_sample_score: float,
    validation_score: float,
    oos_score: float,
    max_score_decay: float = 0.40,
    robustness_pass: bool = False,
    baseline_outperformance: bool = False,
    paper_validation_pass: bool = False,
) -> PromotionGate:
    reasons = []

    if in_sample_score <= 0:
        reasons.append("invalid_in_sample_score")

    minimum_oos = in_sample_score * (1.0 - max_score_decay)
    oos_stable = oos_score >= minimum_oos

    if not oos_stable:
        reasons.append(
            f"oos_decay_exceeds_limit:{oos_score:.2f}<{minimum_oos:.2f}"
        )

    if validation_score <= 0:
        reasons.append("validation_score_not_positive")

    if not robustness_pass:
        reasons.append("regime_robustness_not_passed")

    if not baseline_outperformance:
        reasons.append("did_not_beat_baseline")

    if not paper_validation_pass:
        reasons.append("paper_validation_not_passed")

    checks = {
        "oos_stability": oos_stable,
        "validation_positive": validation_score > 0,
        "regime_robustness": robustness_pass,
        "baseline_outperformance": baseline_outperformance,
        "paper_validation": paper_validation_pass,
    }

    return PromotionGate(
        passed=not reasons,
        reasons=reasons,
        checks=checks,
    )
