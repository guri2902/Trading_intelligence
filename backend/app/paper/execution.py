from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from math import floor


@dataclass(frozen=True)
class CostConfig:
    brokerage_per_order: float = 20.0
    exchange_txn_rate: float = 0.0003553
    sebi_turnover_rate: float = 0.000001
    gst_rate: float = 0.18
    stamp_duty_buy_rate: float = 0.00003
    stt_sell_rate: float = 0.001
    base_slippage_bps: float = 5.0
    latency_ms: int = 150
    min_fill_fraction: float = 0.0


@dataclass(frozen=True)
class MarketQuote:
    ltp: float
    bid: float | None = None
    ask: float | None = None
    available_qty: int | None = None
    underlying_ltp: float | None = None
    timestamp: datetime | None = None


@dataclass(frozen=True)
class FillResult:
    requested_qty: int
    filled_qty: int
    fill_price: float
    spread_cost: float
    slippage_cost: float
    partial: bool
    latency_ms: int


@dataclass(frozen=True)
class CostBreakdown:
    brokerage: float
    exchange_txn: float
    sebi_turnover: float
    stt: float
    stamp_duty: float
    gst: float
    total: float

    def as_dict(self) -> dict[str, float]:
        return {
            "brokerage": round(self.brokerage, 4),
            "exchange_txn": round(self.exchange_txn, 4),
            "sebi_turnover": round(self.sebi_turnover, 4),
            "stt": round(self.stt, 4),
            "stamp_duty": round(self.stamp_duty, 4),
            "gst": round(self.gst, 4),
            "total": round(self.total, 4),
        }


class RealisticExecutionSimulator:
    """Broker-neutral simulator. All rates are configurable; no broker API is called."""

    def __init__(self, config: CostConfig | None = None):
        self.config = config or CostConfig()

    def fill(self, side: str, quantity: int, quote: MarketQuote) -> FillResult:
        if quantity <= 0:
            raise ValueError("QUANTITY_MUST_BE_POSITIVE")
        side = side.upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError("UNSUPPORTED_SIDE")
        if quote.ltp <= 0:
            raise ValueError("INVALID_MARK_PRICE")
        if side == "BUY":
            reference = quote.ask if quote.ask and quote.ask > 0 else quote.ltp
            spread = max(0.0, reference - (quote.bid or quote.ltp)) if quote.bid else 0.0
            sign = 1.0
        else:
            reference = quote.bid if quote.bid and quote.bid > 0 else quote.ltp
            spread = max(0.0, (quote.ask or quote.ltp) - reference) if quote.ask else 0.0
            sign = -1.0
        slip = reference * self.config.base_slippage_bps / 10000.0
        fill_price = reference + sign * slip
        available = quote.available_qty if quote.available_qty is not None else quantity
        available = max(0, int(available))
        if available < quantity:
            filled = max(int(floor(quantity * self.config.min_fill_fraction)), min(quantity, available))
        else:
            filled = quantity
        return FillResult(
            requested_qty=quantity,
            filled_qty=filled,
            fill_price=round(fill_price, 6),
            spread_cost=round(spread * filled, 6),
            slippage_cost=round(abs(fill_price - reference) * filled, 6),
            partial=filled < quantity,
            latency_ms=self.config.latency_ms,
        )

    def costs(self, buy_turnover: float, sell_turnover: float, orders: int = 2) -> CostBreakdown:
        turnover = max(0.0, buy_turnover) + max(0.0, sell_turnover)
        brokerage = max(0, orders) * self.config.brokerage_per_order
        exchange_txn = turnover * self.config.exchange_txn_rate
        sebi = turnover * self.config.sebi_turnover_rate
        stt = max(0.0, sell_turnover) * self.config.stt_sell_rate
        stamp = max(0.0, buy_turnover) * self.config.stamp_duty_buy_rate
        gst = (brokerage + exchange_txn + sebi) * self.config.gst_rate
        total = brokerage + exchange_txn + sebi + stt + stamp + gst
        return CostBreakdown(brokerage, exchange_txn, sebi, stt, stamp, gst, total)

    @staticmethod
    def expiry_value(option_type: str, strike: float, underlying_ltp: float) -> float:
        option_type = option_type.upper()
        if underlying_ltp <= 0 or strike <= 0:
            raise ValueError("INVALID_EXPIRY_INPUT")
        if option_type == "CE":
            return max(0.0, underlying_ltp - strike)
        if option_type == "PE":
            return max(0.0, strike - underlying_ltp)
        raise ValueError("INVALID_OPTION_TYPE")

    @staticmethod
    def is_expired(expiry: str, ts: datetime) -> bool:
        try:
            d = datetime.fromisoformat(expiry).date()
        except ValueError:
            d = datetime.strptime(expiry, "%Y-%m-%d").date()
        return ts.astimezone(timezone.utc).date() >= d
