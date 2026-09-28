from __future__ import annotations

import json
import math
from pathlib import Path
from threading import RLock

from .models import RiskCalculation, RiskCalculationRequest, RiskConfig


class RiskConfigService:
    def __init__(self, root: str | None = None):
        self.root = Path(root or "data/risk")
        self.file = self.root / "config.json"
        self._lock = RLock()
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.file.exists():
            self.file.write_text(
                json.dumps(RiskConfig().model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )

    def get(self) -> RiskConfig:
        with self._lock:
            return RiskConfig.model_validate(
                json.loads(self.file.read_text(encoding="utf-8"))
            )

    def save(self, config: RiskConfig) -> RiskConfig:
        with self._lock:
            self.file.write_text(
                json.dumps(config.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
        return config


class LotRiskCalculator:
    def __init__(self, service: RiskConfigService | None = None):
        self.service = service or RiskConfigService()

    def calculate(self, req: RiskCalculationRequest) -> RiskCalculation:
        cfg = self.service.get()

        instrument = req.instrument.upper()
        lot_size = req.lot_size or cfg.lot_sizes.get(instrument)
        if lot_size is None:
            raise ValueError(f"LOT_SIZE_NOT_CONFIGURED:{instrument}")

        unit_risk = abs(req.entry_price - req.stop_loss)
        if unit_risk <= 0:
            return RiskCalculation(
                instrument=instrument,
                capital=cfg.capital,
                lot_size=lot_size,
                unit_risk=0,
                risk_per_lot=0,
                configured_per_trade_risk=cfg.per_trade_risk,
                daily_remaining=max(0.0, cfg.daily_risk_budget - req.realized_loss_today),
                weekly_remaining=max(0.0, cfg.weekly_risk_budget - req.realized_loss_week),
                monthly_remaining=max(0.0, cfg.monthly_risk_budget - req.realized_loss_month),
                concurrent_remaining=max(0.0, cfg.max_concurrent_risk - req.open_risk),
                effective_risk_budget=0,
                max_lots_by_risk=0,
                quantity=0,
                estimated_trade_risk=0,
                capital_required=0,
                max_open_positions_reached=req.open_positions >= cfg.max_open_positions,
                max_trades_reached=req.trades_today >= cfg.max_trades_per_day,
                eligible=False,
                reasons=["INVALID_STOP_DISTANCE"],
            )

        risk_per_lot = unit_risk * lot_size
        daily_remaining = max(0.0, cfg.daily_risk_budget - req.realized_loss_today)
        weekly_remaining = max(0.0, cfg.weekly_risk_budget - req.realized_loss_week)
        monthly_remaining = max(0.0, cfg.monthly_risk_budget - req.realized_loss_month)
        concurrent_remaining = max(0.0, cfg.max_concurrent_risk - req.open_risk)

        effective_budget = min(
            cfg.per_trade_risk,
            daily_remaining,
            weekly_remaining,
            monthly_remaining,
            concurrent_remaining,
        )

        max_lots = math.floor(effective_budget / risk_per_lot)
        quantity = max_lots * lot_size
        estimated = risk_per_lot * max_lots
        capital_required = req.entry_price * quantity

        reasons: list[str] = []
        if req.open_positions >= cfg.max_open_positions:
            reasons.append("MAX_OPEN_POSITIONS_REACHED")
        if req.trades_today >= cfg.max_trades_per_day:
            reasons.append("MAX_TRADES_PER_DAY_REACHED")
        if effective_budget <= 0:
            reasons.append("NO_RISK_BUDGET")
        if max_lots < 1:
            reasons.append("LESS_THAN_ONE_LOT")
        if quantity > 0 and capital_required > cfg.capital:
            reasons.append("CAPITAL_REQUIRED_EXCEEDS_CAPITAL")
            max_lots = min(max_lots, math.floor(cfg.capital / (req.entry_price * lot_size)))
            quantity = max_lots * lot_size
            estimated = risk_per_lot * max_lots
            capital_required = req.entry_price * quantity

        eligible = (
            max_lots >= 1
            and not reasons
        )

        return RiskCalculation(
            instrument=instrument,
            capital=cfg.capital,
            lot_size=lot_size,
            unit_risk=round(unit_risk, 6),
            risk_per_lot=round(risk_per_lot, 6),
            configured_per_trade_risk=cfg.per_trade_risk,
            daily_remaining=round(daily_remaining, 6),
            weekly_remaining=round(weekly_remaining, 6),
            monthly_remaining=round(monthly_remaining, 6),
            concurrent_remaining=round(concurrent_remaining, 6),
            effective_risk_budget=round(effective_budget, 6),
            max_lots_by_risk=max_lots,
            quantity=quantity,
            estimated_trade_risk=round(estimated, 6),
            capital_required=round(capital_required, 6),
            max_open_positions_reached=req.open_positions >= cfg.max_open_positions,
            max_trades_reached=req.trades_today >= cfg.max_trades_per_day,
            eligible=eligible,
            reasons=reasons,
        )
