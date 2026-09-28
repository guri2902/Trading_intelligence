from __future__ import annotations

from typing import Any

from ..agents.models import AgentInput, AgentRunResult, AgentVerdict
from .models import ScoreComponent, SignalCandidate, SignalDecision, TradePlan


class SignalFusionEngine:
    """Transparent evidence fusion and candidate ranking.

    The engine never invents market values. Missing deterministic evidence reduces
    the score or blocks the trade; LLM metadata is bounded to advisory nudges only.
    """

    WEIGHTS = {
        "TECHNICAL": 0.20,
        "OPTIONS": 0.18,
        "STRATEGY": 0.18,
        "ML": 0.12,
        "FUNDAMENTAL": 0.07,
        "SENTIMENT": 0.07,
        "NEWS_MACRO": 0.06,
        "CONTRARIAN": 0.06,
        "RISK": 0.04,
        "QA": 0.02,
    }

    def rank(self, data: AgentInput, result: AgentRunResult) -> SignalDecision:
        gates = self._hard_gates(data, result)
        verdicts = {a.agent: a for a in result.agents}
        candidates: list[SignalCandidate] = []

        for side, option_type, action, direction in (
            ("CE", "CE", "BUY_CE", "LONG"),
            ("PE", "PE", "BUY_PE", "SHORT"),
        ):
            candidate = self._candidate(
                data,
                result,
                verdicts,
                side,
                option_type,
                action,
                direction,
                gates,
            )
            if candidate is not None:
                candidates.append(candidate)

        candidates.sort(
            key=lambda x: (x.rank_score, x.confidence),
            reverse=True,
        )

        selected = None

        if candidates:
            top = candidates[0]
            minimum_edge = 55.0
            min_separation = 8.0
            second = candidates[1] if len(candidates) > 1 else None
            separation = top.rank_score - (
                second.rank_score if second else 0.0
            )

            if (
                not gates
                and top.plan is not None
                and not top.blockers
                and top.action in {"BUY_CE", "BUY_PE"}
                and top.rank_score >= minimum_edge
                and separation >= min_separation
            ):
                selected = top

        if selected:
            return SignalDecision(
                timestamp=str(data.timestamp),
                symbol=data.market.get("symbol")
                or data.market.get("instrument"),
                action=selected.action,
                direction=selected.direction,
                confidence=selected.confidence,
                score=selected.score,
                selected=selected,
                candidates=candidates,
                hard_gates=gates,
            )

        reason = list(gates)

        if candidates and not gates:
            reason.append(
                "NO_CANDIDATE_PASSED_SCORE_OR_SEPARATION_THRESHOLD"
            )

        return SignalDecision(
            timestamp=str(data.timestamp),
            symbol=data.market.get("symbol")
            or data.market.get("instrument"),
            action="NO_TRADE" if gates else "WAIT",
            direction="NONE",
            confidence=0.0,
            score=0.0,
            selected=None,
            candidates=candidates,
            hard_gates=reason,
        )

    def _hard_gates(
        self,
        data: AgentInput,
        result: AgentRunResult,
    ) -> list[str]:
        gates: list[str] = []

        if result.final_decision.risk_veto:
            gates.append("RISK_VETO")

        if not result.final_decision.qa_pass:
            gates.append("QA_FAILED")

        if bool(data.market.get("stale")):
            gates.append("STALE_MARKET_DATA")

        if (
            str(
                data.market.get(
                    "data_quality_status",
                    "UNKNOWN",
                )
            ).upper()
            not in {"PASS", "OK"}
        ):
            gates.append("MARKET_DATA_QUALITY_NOT_PASS")

        if (
            str(
                data.options.get(
                    "status",
                    "UNKNOWN",
                )
            ).upper()
            not in {"OK", "PASS"}
        ):
            gates.append("OPTION_DATA_NOT_AVAILABLE")

        if result.debate.winner == "NO_TRADE":
            gates.append("DEBATE_NO_TRADE")

        return gates

    def _candidate(
        self,
        data: AgentInput,
        result: AgentRunResult,
        verdicts: dict[str, AgentVerdict],
        side: str,
        option_type: str,
        action: str,
        direction: str,
        gates: list[str],
    ) -> SignalCandidate | None:
        components: list[ScoreComponent] = []
        weighted_sum = 0.0
        total_weight = 0.0

        for name, weight in self.WEIGHTS.items():
            verdict = verdicts.get(name)

            if not verdict or verdict.stance == "VETO":
                continue

            raw = self._directional_score(
                verdict,
                direction,
            )

            llm_adjust = self._llm_adjustment(verdict)

            raw = max(
                -100.0,
                min(100.0, raw + llm_adjust),
            )

            weighted = raw * weight
            weighted_sum += weighted
            total_weight += weight

            components.append(
                ScoreComponent(
                    name=name,
                    raw=round(raw, 3),
                    weighted=round(weighted, 3),
                    weight=weight,
                    evidence=[
                        e.statement
                        for e in verdict.evidence[:3]
                    ],
                )
            )

        if total_weight <= 0:
            return None

        base_score = weighted_sum / total_weight
        debate_edge = self._debate_score(
            result,
            side,
        )

        fusion_score = (
            0.65 * base_score
            + 0.35 * debate_edge
        )

        confidence = self._confidence(
            components,
            fusion_score,
            result,
            side,
        )

        plan = self._build_plan(
            data,
            side,
            option_type,
            direction,
        )

        blockers = list(gates)

        if plan is None:
            blockers.append(
                "NO_ELIGIBLE_OPTION_CONTRACT"
            )

        if (
            data.strategies
            .get("best_setup", {})
            .get("state")
            == "NO_SETUP"
        ):
            blockers.append(
                "NO_STRATEGY_SETUP"
            )

        rationale = [
            f"Evidence fusion score={fusion_score:.1f}",
            f"Debate {side} score={debate_edge:.1f}",
        ]

        if plan:
            rationale.append(
                f"Selected {option_type} contract "
                "from supplied option candidates."
            )

        return SignalCandidate(
            action=action,
            direction=direction,
            score=round(fusion_score, 2),
            confidence=round(confidence, 2),
            rank_score=round(
                max(0.0, fusion_score),
                2,
            ),
            option_type=option_type,
            strike=plan.strike if plan else None,
            expiry=plan.expiry if plan else None,
            plan=plan,
            components=components,
            blockers=blockers,
            rationale=rationale,
        )

    @staticmethod
    def _directional_score(
        verdict: AgentVerdict,
        direction: str,
    ) -> float:
        if direction == "LONG":
            return verdict.score

        return -verdict.score

    @staticmethod
    def _llm_adjustment(
        verdict: AgentVerdict,
    ) -> float:
        review = (
            verdict.metadata.get("llm_review")
            or {}
        )

        try:
            return (
                max(
                    -20.0,
                    min(
                        20.0,
                        float(
                            review.get(
                                "score_adjustment",
                                0,
                            )
                            or 0
                        ),
                    ),
                )
                * 0.25
            )
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _debate_score(
        result: AgentRunResult,
        side: str,
    ) -> float:
        if side == "CE":
            return max(
                0.0,
                min(
                    100.0,
                    result.debate.ce_score,
                ),
            )

        return max(
            0.0,
            min(
                100.0,
                result.debate.pe_score,
            ),
        )

    @staticmethod
    def _confidence(
        components: list[ScoreComponent],
        score: float,
        result: AgentRunResult,
        side: str,
    ) -> float:
        active = sum(
            1
            for c in components
            if abs(c.raw) >= 15
        )

        agreement = min(
            1.0,
            active / max(1, len(components)),
        )

        separation = abs(
            result.debate.ce_score
            - result.debate.pe_score
        )

        debate_alignment = min(
            1.0,
            separation / 40.0,
        )

        llm = (
            result.final_decision.metadata.get(
                "llm_debate"
            )
            or {}
        )

        llm_bonus = 0.0

        if llm.get("winner") == side:
            llm_bonus = 3.0
        elif (
            llm.get("winner") in {"CE", "PE"}
            and llm.get("winner") != side
        ):
            llm_bonus = -3.0

        return max(
            0.0,
            min(
                95.0,
                35
                + abs(score) * 0.45
                + agreement * 12
                + debate_alignment * 8
                + llm_bonus,
            ),
        )

    def _build_plan(
        self,
        data: AgentInput,
        side: str,
        option_type: str,
        direction: str,
    ) -> TradePlan | None:
        options = data.options or {}

        candidates = (
            options.get("candidates")
            or options.get("contracts")
            or []
        )

        if not isinstance(candidates, list):
            return None

        eligible = []

        for item in candidates:
            if not isinstance(item, dict):
                continue

            typ = str(
                item.get("option_type")
                or item.get("type")
                or ""
            ).upper()

            if typ != option_type:
                continue

            if item.get("eligible") is False:
                continue

            ltp = item.get(
                "ltp",
                item.get("price"),
            )

            if ltp is None:
                q = item.get("quote") or {}
                ltp = q.get(
                    "ltp",
                    q.get("last_price"),
                )

            try:
                ltp_f = float(ltp)
            except (TypeError, ValueError):
                continue

            if ltp_f <= 0:
                continue

            rank = float(
                item.get(
                    "rank_score",
                    item.get(
                        "liquidity_score",
                        0,
                    ),
                )
                or 0
            )

            eligible.append(
                (
                    rank,
                    ltp_f,
                    item,
                )
            )

        if not eligible:
            # Some providers send one selected contract at options.selected.
            selected = (
                options.get("selected")
                or options.get(
                    f"selected_{option_type.lower()}"
                )
            )

            if isinstance(selected, dict):
                selected_ltp = float(
                    selected.get("ltp", 0)
                    or 0
                )

                if selected_ltp > 0:
                    eligible = [
                        (
                            float(
                                selected.get(
                                    "rank_score",
                                    0,
                                )
                                or 0
                            ),
                            selected_ltp,
                            selected,
                        )
                    ]

        # NEW:
        # Phase 8 currently exposes the strongest CE/PE contracts
        # through best_ce / best_pe. Use those as a deterministic
        # fallback when candidate/selected structures are unavailable.
        if not eligible:
            best_key = (
                "best_ce"
                if option_type == "CE"
                else "best_pe"
            )

            best = options.get(best_key)

            if isinstance(best, dict):
                quote = best.get("quote") or {}
                contract = quote.get("contract") or {}
                metrics = best.get("metrics") or {}

                best_ltp = quote.get(
                    "ltp",
                    quote.get("last_price"),
                )

                try:
                    best_ltp = float(best_ltp)
                except (TypeError, ValueError):
                    best_ltp = None

                if (
                    best_ltp is not None
                    and best_ltp > 0
                ):
                    best_rank = float(
                        best.get(
                            "rank_score",
                            metrics.get(
                                "liquidity_score",
                                0,
                            ),
                        )
                        or 0
                    )

                    eligible = [
                        (
                            best_rank,
                            best_ltp,
                            {
                                "option_type": contract.get(
                                    "option_type",
                                    option_type,
                                ),
                                "strike": contract.get(
                                    "strike"
                                ),
                                "expiry": contract.get(
                                    "expiry"
                                ),
                                "ltp": best_ltp,
                                "rank_score": best_rank,
                                "lot_size": contract.get(
                                    "lot_size"
                                ),
                                "tick_size": contract.get(
                                    "tick_size"
                                ),
                                "source": quote.get(
                                    "source"
                                ),
                            },
                        )
                    ]

        if not eligible:
            return None

        _, ltp, item = max(
            eligible,
            key=lambda x: x[0],
        )

        setup = (
            data.strategies.get(
                "best_setup"
            )
            or {}
        )

        rr = setup.get(
            "risk_reward"
        )

        try:
            rr_f = (
                float(rr)
                if rr is not None
                else None
            )
        except (TypeError, ValueError):
            rr_f = None

        # Contract-level protective defaults are only used when no explicit option plan is supplied.
        explicit_sl = item.get(
            "stop_loss",
            item.get("sl"),
        )

        explicit_tp1 = item.get(
            "target_1",
            item.get("tp1"),
        )

        explicit_tp2 = item.get(
            "target_2",
            item.get("tp2"),
        )

        if explicit_sl is None:
            stop = round(
                ltp * 0.70,
                4,
            )
        else:
            stop = float(explicit_sl)

        if explicit_tp1 is None:
            tp1 = round(
                ltp * 1.20,
                4,
            )
        else:
            tp1 = float(explicit_tp1)

        if explicit_tp2 is None:
            tp2 = round(
                ltp * 1.50,
                4,
            )
        else:
            tp2 = float(explicit_tp2)

        risk = abs(
            ltp - stop
        )

        reward = abs(
            tp1 - ltp
        )

        derived_rr = (
            reward / risk
            if risk > 0
            else None
        )

        return TradePlan(
            option_type=option_type,
            strike=self._float_or_none(
                item.get("strike")
            ),
            expiry=(
                str(item.get("expiry"))
                if item.get("expiry") is not None
                else None
            ),
            entry=round(
                ltp,
                4,
            ),
            stop_loss=round(
                stop,
                4,
            ),
            target_1=round(
                tp1,
                4,
            ),
            target_2=round(
                tp2,
                4,
            ),
            risk_reward=round(
                rr_f
                if rr_f is not None
                else derived_rr,
                3,
            )
            if (
                rr_f is not None
                or derived_rr is not None
            )
            else None,
            quantity=(
                int(item.get("quantity"))
                if item.get("quantity") is not None
                else None
            ),
            lot_size=(
                int(item.get("lot_size"))
                if item.get("lot_size") is not None
                else None
            ),
            contract_source=item.get(
                "source"
            ),
            invalidation=[
                f"Option premium falls to {stop:.4f}",
                "Underlying strategy invalidation applies when supplied",
            ],
        )

    @staticmethod
    def _float_or_none(
        value: Any,
    ) -> float | None:
        try:
            return (
                float(value)
                if value is not None
                else None
            )
        except (TypeError, ValueError):
            return None