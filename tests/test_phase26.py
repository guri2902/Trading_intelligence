
from self_improvement.engine import (
    CandidateEvaluation, ImprovementCandidate, SelfImprovementEngine
)


def make_engine(cands, evals):
    def gen(_ctx, _version):
        return cands
    def ev(c):
        return evals[c.candidate_id]
    return SelfImprovementEngine(
        gen, ev, min_oos_pnl_improvement_pct=5, min_oos_expectancy_improvement_pct=2,
        max_oos_drawdown_increase_pct=3
    )


def test_best_candidate_promotes_with_immutable_version():
    c = ImprovementCandidate("good1234", "v1", {"x": 2}, "validated change")
    e = CandidateEvaluation(
        "good1234", {"net_pnl": 100}, {"net_pnl": 120, "expectancy": 12, "max_drawdown_pct": 5},
        {"net_pnl": 100, "expectancy": 10, "max_drawdown_pct": 5},
        {"net_pnl": 20, "expectancy": 20}, False
    )
    r = make_engine([c], {"good1234": e}).improve(
        signal_context={"signal_id": "s1"}, current_version="v1",
        outcome={"pnl": 20}
    )
    assert r.promotion.promoted
    assert r.promotion.to_version == "v1+good1234"


def test_candidate_with_insufficient_oos_improvement_is_rejected():
    c = ImprovementCandidate("weak1111", "v1", {"x": 1}, "weak")
    e = CandidateEvaluation(
        "weak1111", {}, {"net_pnl": 103, "expectancy": 10.1, "max_drawdown_pct": 5},
        {"net_pnl": 100, "expectancy": 10, "max_drawdown_pct": 5},
        {"net_pnl": 3, "expectancy": 1}, False
    )
    r = make_engine([c], {"weak1111": e}).improve(
        signal_context={"signal_id": "s2"}, current_version="v1",
        outcome={"pnl": 3}
    )
    assert not r.promotion.promoted
    assert "no_candidate_passed_promotion_gate" in r.promotion.reasons


def test_drawdown_increase_blocks_promotion():
    c = ImprovementCandidate("dd22222", "v1", {"x": 3}, "higher DD")
    e = CandidateEvaluation(
        "dd22222", {}, {"net_pnl": 130, "expectancy": 12, "max_drawdown_pct": 9},
        {"net_pnl": 100, "expectancy": 10, "max_drawdown_pct": 5},
        {"net_pnl": 30, "expectancy": 20}, False
    )
    r = make_engine([c], {"dd22222": e}).improve(
        signal_context={"signal_id": "s3"}, current_version="v1",
        outcome={"pnl": 30}
    )
    assert not r.promotion.promoted


def test_negative_oos_is_blocked():
    c = ImprovementCandidate("neg3333", "v1", {"x": 4}, "negative")
    e = CandidateEvaluation(
        "neg3333", {}, {"net_pnl": -5, "expectancy": 9, "max_drawdown_pct": 4},
        {"net_pnl": 100, "expectancy": 10, "max_drawdown_pct": 5},
        {"net_pnl": -105, "expectancy": -10}, False
    )
    r = make_engine([c], {"neg3333": e}).improve(
        signal_context={"signal_id": "s4"}, current_version="v1",
        outcome={"pnl": -5}
    )
    assert not r.promotion.promoted


def test_candidate_hash_is_stable():
    a = SelfImprovementEngine.candidate_id("v1", {"a": 1, "b": 2})
    b = SelfImprovementEngine.candidate_id("v1", {"b": 2, "a": 1})
    assert a == b
