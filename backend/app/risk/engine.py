from __future__ import annotations

from datetime import datetime
from math import floor
from zoneinfo import ZoneInfo

from ..signals.models import SignalDecision, TradePlan
from .models import AccountRiskContext, RiskAssessment, RiskDecision


class RiskEngine:
    """Portfolio-level risk gate and position-sizing engine.

    This layer changes an otherwise valid signal into BUY/WAIT/NO_TRADE only by
    applying explicit account constraints. It never submits an order.
    """

    IST = ZoneInfo("Asia/Kolkata")

    def evaluate(self, decision: SignalDecision, account: AccountRiskContext) -> RiskDecision:
        if decision.action not in {"BUY_CE", "BUY_PE"} or decision.selected is None or decision.selected.plan is None:
            assessment = RiskAssessment(
                approved=False,
                action="NO_TRADE" if decision.action == "NO_TRADE" else decision.action,
                reason_codes=["NO_EXECUTABLE_SIGNAL"],
                notes=["Risk engine only sizes and approves executable BUY candidates."],
            )
            return self._decision(decision, assessment, None)

        if not account.enabled:
            return self._blocked(decision, ["RISK_ENGINE_DISABLED"])

        plan = decision.selected.plan
        blockers = self._account_gates(account)
        square_off = self._square_off_required(account)
        if square_off:
            blockers.append("SQUARE_OFF_WINDOW")

        if blockers:
            assessment = RiskAssessment(
                approved=False,
                action="NO_TRADE",
                reason_codes=blockers,
                square_off_required=square_off,
                remaining_daily_loss_capacity=self._daily_loss_capacity(account),
                remaining_profit_lock_capacity=self._profit_lock_capacity(account),
            )
            return self._decision(decision, assessment, plan)

        lot_size = int(plan.lot_size or 0)
        if lot_size <= 0:
            return self._blocked(decision, ["MISSING_LOT_SIZE"], plan)
        if plan.entry is None or plan.stop_loss is None:
            return self._blocked(decision, ["MISSING_ENTRY_OR_STOP"], plan)

        entry = float(plan.entry)
        stop = float(plan.stop_loss)
        unit_risk = abs(entry - stop)
        if unit_risk <= 0:
            return self._blocked(decision, ["ZERO_UNIT_RISK"], plan)

        risk_budget = account.equity * account.risk_per_trade_pct / 100.0
        daily_capacity = self._daily_loss_capacity(account)
        if daily_capacity is not None:
            risk_budget = min(risk_budget, daily_capacity)
        concurrent_capacity = self._concurrent_risk_capacity(account)
        if concurrent_capacity is not None:
            risk_budget = min(risk_budget, concurrent_capacity)
        if risk_budget <= 0:
            return self._blocked(decision, ["NO_RISK_BUDGET_REMAINING"], plan)

        raw_units = floor(risk_budget / unit_risk)
        lots = raw_units // lot_size
        quantity = lots * lot_size
        if lots < 1:
            return self._blocked(decision, ["RISK_BUDGET_BELOW_ONE_LOT"], plan)

        estimated = quantity * unit_risk
        resulting_open_risk = account.open_risk + estimated
        max_concurrent = account.max_concurrent_risk
        if max_concurrent > 0 and resulting_open_risk > max_concurrent + 1e-9:
            return self._blocked(decision, ["MAX_CONCURRENT_RISK_EXCEEDED"], plan)

        # Hard sanity check for generated plan values.
        if plan.target_1 is not None and float(plan.target_1) <= entry:
            return self._blocked(decision, ["INVALID_LONG_PREMIUM_TARGET"], plan)

        assessment = RiskAssessment(
            approved=True,
            action=decision.action,
            reason_codes=[],
            risk_budget=round(risk_budget, 2),
            unit_risk=round(unit_risk, 4),
            quantity=quantity,
            lot_size=lot_size,
            lots=lots,
            estimated_trade_risk=round(estimated, 2),
            resulting_open_risk=round(resulting_open_risk, 2),
            risk_pct_of_equity=round(estimated / account.equity * 100, 4),
            remaining_daily_loss_capacity=round(max(0.0, (daily_capacity - estimated) if daily_capacity is not None else 0.0), 2) if daily_capacity is not None else None,
            remaining_profit_lock_capacity=self._profit_lock_capacity(account),
            square_off_required=False,
            notes=[
                "Quantity is rounded down to whole option lots.",
                "Risk is based on premium entry-to-stop distance multiplied by quantity.",
                "No broker/order API is called by this risk layer.",
            ],
        )
        sized_plan = plan.model_copy(update={"quantity": quantity, "lot_size": lot_size})
        return self._decision(decision, assessment, sized_plan)

    def _account_gates(self, account: AccountRiskContext) -> list[str]:
        out: list[str] = []
        if account.max_daily_loss > 0 and account.realized_pnl_today <= -account.max_daily_loss:
            out.append("DAILY_LOSS_LIMIT_REACHED")
        if account.daily_profit_lock > 0 and account.realized_pnl_today >= account.daily_profit_lock:
            out.append("DAILY_PROFIT_LOCK_REACHED")
        if account.max_trades_per_day > 0 and account.trades_today >= account.max_trades_per_day:
            out.append("MAX_TRADES_PER_DAY_REACHED")
        if account.max_open_positions > 0 and account.open_positions >= account.max_open_positions:
            out.append("MAX_OPEN_POSITIONS_REACHED")
        if account.max_drawdown_pct > 0 and account.peak_equity:
            dd = max(0.0, (account.peak_equity - account.equity) / account.peak_equity * 100)
            if dd >= account.max_drawdown_pct:
                out.append("MAX_DRAWDOWN_REACHED")
        return out

    def _daily_loss_capacity(self, account: AccountRiskContext) -> float | None:
        if account.max_daily_loss <= 0:
            return None
        return max(0.0, account.max_daily_loss + account.realized_pnl_today)

    def _profit_lock_capacity(self, account: AccountRiskContext) -> float | None:
        if account.daily_profit_lock <= 0:
            return None
        return max(0.0, account.daily_profit_lock - account.realized_pnl_today)

    def _concurrent_risk_capacity(self, account: AccountRiskContext) -> float | None:
        if account.max_concurrent_risk <= 0:
            return None
        return max(0.0, account.max_concurrent_risk - account.open_risk)

    def _square_off_required(self, account: AccountRiskContext) -> bool:
        if not account.square_off_time or account.market_timestamp is None:
            return False
        try:
            hour, minute = [int(x) for x in account.square_off_time.split(":")]
            market_time = account.market_timestamp
            if market_time.tzinfo is None:
                market_time = market_time.replace(tzinfo=self.IST)
            return (market_time.hour, market_time.minute) >= (hour, minute)
        except (ValueError, AttributeError):
            return False

    @staticmethod
    def _blocked(decision: SignalDecision, reasons: list[str], plan: TradePlan | None = None) -> RiskDecision:
        assessment = RiskAssessment(
            approved=False,
            action="NO_TRADE",
            reason_codes=reasons,
            notes=["Signal was rejected by an explicit portfolio risk rule."],
        )
        return RiskDecision(
            timestamp=decision.timestamp,
            symbol=decision.symbol,
            signal_action=decision.action,
            final_action="NO_TRADE",
            approved=False,
            assessment=assessment,
            trade_plan=plan.model_dump(mode="json") if plan else None,
        )

    @staticmethod
    def _decision(decision: SignalDecision, assessment: RiskAssessment, plan: TradePlan | None) -> RiskDecision:
        final_action = decision.action if assessment.approved else "NO_TRADE"
        return RiskDecision(
            timestamp=decision.timestamp,
            symbol=decision.symbol,
            signal_action=decision.action,
            final_action=final_action,
            approved=assessment.approved,
            assessment=assessment,
            trade_plan=plan.model_dump(mode="json") if plan else None,
        )
