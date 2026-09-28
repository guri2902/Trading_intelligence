from __future__ import annotations

from .models import AgentVerdict, DebateResult


def _flip(agent: AgentVerdict, side: str) -> AgentVerdict:
    evidence = list(agent.evidence)
    risks = list(agent.risks)

    if side == "CE":
        score = abs(agent.score)
        stance = "BULLISH"
    else:
        score = -abs(agent.score)
        stance = "BEARISH"

    return AgentVerdict(
        agent=agent.agent,
        stance=stance,
        score=score,
        confidence=agent.confidence,
        evidence=evidence,
        risks=risks,
        questions=agent.questions,
        metadata=agent.metadata,
    )


def build_ce_case(agents: list[AgentVerdict]) -> AgentVerdict:
    scores = []
    evidence = []
    risks = []

    for a in agents:
        if a.stance == "BULLISH":
            scores.append(abs(a.score))
            evidence.extend(a.evidence)
        elif a.stance == "BEARISH":
            risks.extend([f"{a.agent}: {r}" for r in a.risks])

    score = sum(scores)
    return AgentVerdict(
        agent="CE",
        stance="BULLISH" if score > 0 else "NEUTRAL",
        score=min(score, 100),
        confidence=min(100, sum(a.confidence for a in agents) / max(1, len(agents))),
        evidence=evidence[:12],
        risks=risks[:12],
    )


def build_pe_case(agents: list[AgentVerdict]) -> AgentVerdict:
    scores = []
    evidence = []
    risks = []

    for a in agents:
        if a.stance == "BEARISH":
            scores.append(abs(a.score))
            evidence.extend(a.evidence)
        elif a.stance == "BULLISH":
            risks.extend([f"{a.agent}: {r}" for r in a.risks])

    score = sum(scores)
    return AgentVerdict(
        agent="PE",
        stance="BEARISH" if score > 0 else "NEUTRAL",
        score=min(score, 100),
        confidence=min(100, sum(a.confidence for a in agents) / max(1, len(agents))),
        evidence=evidence[:12],
        risks=risks[:12],
    )


def build_contrarian(
    agents: list[AgentVerdict],
    ce_score: float,
    pe_score: float,
) -> AgentVerdict:
    edge = ce_score - pe_score
    risks = []

    if edge > 20:
        risks.append("CE consensus may be crowded; seek invalidation and confirmation.")
        stance = "BEARISH"
        score = -min(edge * 0.35, 80)
    elif edge < -20:
        risks.append("PE consensus may be crowded; seek invalidation and confirmation.")
        stance = "BULLISH"
        score = min(abs(edge) * 0.35, 80)
    else:
        stance = "NEUTRAL"
        score = 0

    return AgentVerdict(
        agent="CONTRARIAN",
        stance=stance,
        score=score,
        confidence=65,
        evidence=[],
        risks=risks,
        questions=[
            "What evidence would invalidate the consensus?",
            "Is the move already extended?",
            "Is the option premium/IV making the directional thesis unattractive?",
        ],
    )


def run_debate(
    agents: list[AgentVerdict],
) -> DebateResult:
    ce = build_ce_case(agents)
    pe = build_pe_case(agents)
    contrarian = build_contrarian(agents, ce.score, pe.score)

    ce_score = ce.score + max(0, contrarian.score)
    pe_score = pe.score + max(0, -contrarian.score)

    conflicts = []
    bullish = [a.agent for a in agents if a.stance == "BULLISH"]
    bearish = [a.agent for a in agents if a.stance == "BEARISH"]

    if bullish and bearish:
        conflicts.append(
            f"Direction conflict: bullish={bullish}, bearish={bearish}"
        )

    option_agent = next((a for a in agents if a.agent == "OPTIONS"), None)
    option_unknown = (
        option_agent is not None
        and option_agent.metadata.get("debate_winner") == "NO_TRADE"
    )

    # An explicit unresolved option-chain verdict is a hard no-trade constraint.
    if option_unknown:
        winner = "NO_TRADE"
        conflicts.append("OPTIONS agent reported no clear CE/PE contract winner.")
    elif ce_score < 35 and pe_score < 35:
        winner = "NO_TRADE"
    elif abs(ce_score - pe_score) < 10:
        winner = "NO_TRADE"
        conflicts.append("CE/PE scores are too close.")
    else:
        winner = "CE" if ce_score > pe_score else "PE"

    reason = (
        "CE has the stronger aggregated case."
        if winner == "CE"
        else "PE has the stronger aggregated case."
        if winner == "PE"
        else "Neither side has sufficient separation."
    )

    return DebateResult(
        ce_case=ce,
        pe_case=pe,
        contrarian=contrarian,
        winner=winner,
        ce_score=round(ce_score, 2),
        pe_score=round(pe_score, 2),
        reason=reason,
        unresolved_conflicts=conflicts,
    )
