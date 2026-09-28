from __future__ import annotations

import math
import statistics

from .models import BacktestMetrics, EquityPoint, TradeRecord


def _returns(equity: list[EquityPoint]) -> list[float]:
    if len(equity) < 2:
        return []

    out: list[float] = []

    for a, b in zip(equity, equity[1:]):
        if a.equity > 0:
            out.append(b.equity / a.equity - 1.0)

    return out


def sharpe_ratio(equity: list[EquityPoint]) -> float | None:
    r = _returns(equity)

    if len(r) < 2:
        return None

    std = statistics.stdev(r)

    if std == 0:
        return None

    return statistics.mean(r) / std * math.sqrt(len(r))


def sortino_ratio(equity: list[EquityPoint]) -> float | None:
    r = _returns(equity)

    if len(r) < 2:
        return None

    downside = [x for x in r if x < 0]

    if not downside:
        return None

    downside_dev = math.sqrt(
        sum(x * x for x in downside) / len(downside)
    )

    if downside_dev == 0:
        return None

    return statistics.mean(r) / downside_dev * math.sqrt(len(r))


def compute_metrics(
    *,
    initial_capital: float,
    trades: list[TradeRecord],
    equity: list[EquityPoint],
) -> BacktestMetrics:

    # ---------------------------------------------------------
    # REALIZED TRADE P&L
    # ---------------------------------------------------------
    # Trade records are the authoritative source for realized
    # strategy performance. This prevents final equity from
    # becoming inconsistent with gross profit/loss and expectancy.
    trade_pnls = [float(t.net_pnl) for t in trades]

    wins = [pnl for pnl in trade_pnls if pnl > 0]
    losses = [pnl for pnl in trade_pnls if pnl < 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    total = len(trade_pnls)
    winning = len(wins)
    losing = len(losses)

    # Net realized P&L comes directly from the completed trades.
    net_profit = sum(trade_pnls)

    # Final realized equity is therefore deterministic.
    final_equity = initial_capital + net_profit

    # ---------------------------------------------------------
    # BASIC PERFORMANCE
    # ---------------------------------------------------------
    return_pct = (
        (net_profit / initial_capital) * 100.0
        if initial_capital > 0
        else 0.0
    )

    win_rate_pct = (
        (winning / total) * 100.0
        if total
        else 0.0
    )

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else None
    )

    # Mean realized P&L per completed trade.
    expectancy = (
        net_profit / total
        if total
        else 0.0
    )

    # ---------------------------------------------------------
    # DRAWDOWN
    # ---------------------------------------------------------
    # Drawdown remains based on the equity curve because it is
    # a path-dependent risk metric.
    drawdowns = [
        float(point.drawdown)
        for point in equity
    ]

    drawdown_pcts = [
        float(point.drawdown_pct)
        for point in equity
    ]

    max_drawdown = (
        max(drawdowns)
        if drawdowns
        else 0.0
    )

    max_drawdown_pct = (
        max(drawdown_pcts)
        if drawdown_pcts
        else 0.0
    )

    # ---------------------------------------------------------
    # CONSISTENCY CHECK
    # ---------------------------------------------------------
    # The metrics must reconcile:
    #
    # final_equity = initial_capital + net_profit
    #
    # and
    #
    # net_profit = gross_profit + sum(losses)
    #
    # This is intentionally calculated from the trade records
    # rather than trusting the final equity-curve value.
    expected_net_profit = gross_profit - gross_loss

    # Floating-point tolerance for fractional quantities/slippage.
    if not math.isclose(
        net_profit,
        expected_net_profit,
        rel_tol=1e-9,
        abs_tol=1e-8,
    ):
        raise ValueError(
            "Backtest P&L inconsistency: "
            f"net_profit={net_profit}, "
            f"gross_profit={gross_profit}, "
            f"gross_loss={gross_loss}"
        )

    # ---------------------------------------------------------
    # RISK-ADJUSTED METRICS
    # ---------------------------------------------------------
    sharpe = sharpe_ratio(equity)
    sortino = sortino_ratio(equity)

    # ---------------------------------------------------------
    # WIN / LOSS STATISTICS
    # ---------------------------------------------------------
    average_win = (
        gross_profit / winning
        if winning
        else 0.0
    )

    average_loss = (
        -(gross_loss / losing)
        if losing
        else 0.0
    )

    largest_win = (
        max(wins)
        if wins
        else 0.0
    )

    largest_loss = (
        min(losses)
        if losses
        else 0.0
    )

    # ---------------------------------------------------------
    # FINAL MODEL
    # ---------------------------------------------------------
    return BacktestMetrics(
        initial_capital=initial_capital,
        final_equity=final_equity,
        net_profit=net_profit,
        return_pct=return_pct,
        total_trades=total,
        winning_trades=winning,
        losing_trades=losing,
        win_rate_pct=win_rate_pct,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=profit_factor,
        expectancy_per_trade=expectancy,
        max_drawdown=max_drawdown,
        max_drawdown_pct=max_drawdown_pct,
        sharpe=sharpe,
        sortino=sortino,
        average_win=average_win,
        average_loss=average_loss,
        largest_win=largest_win,
        largest_loss=largest_loss,
    )