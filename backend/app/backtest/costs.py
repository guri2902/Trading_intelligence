from __future__ import annotations

from .models import CostConfig


def apply_slippage(price: float, direction: str, slippage_bps: float) -> float:
    """
    Buy/long fills are worsened upward; sell/short fills worsened downward.
    """
    factor = slippage_bps / 10_000.0
    if direction in {"LONG", "BUY"}:
        return price * (1.0 + factor)
    if direction in {"SHORT", "SELL"}:
        return price * (1.0 - factor)
    return price


def transaction_cost(
    *,
    entry_value: float,
    exit_value: float,
    config: CostConfig,
) -> float:
    turnover = abs(entry_value) + abs(exit_value)

    brokerage = 2.0 * config.brokerage_per_order
    exchange_cost = turnover * config.exchange_txn_rate
    sebi = turnover * config.sebi_rate
    stamp = abs(entry_value) * config.stamp_duty_rate
    stt = abs(exit_value) * config.stt_rate

    taxable_base = brokerage + exchange_cost + sebi
    gst = taxable_base * config.gst_rate

    return brokerage + exchange_cost + sebi + stamp + stt + gst
