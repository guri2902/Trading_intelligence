from __future__ import annotations

import math
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from ..backtest.models import CostConfig
from ..backtest.costs import transaction_cost
from .models import (
    HistoricalOptionBar,
    OptionsBacktestConfig,
    OptionsBacktestResult,
    OptionsTradeRecord,
)


@dataclass(frozen=True)
class _OpenTrade:
    trade_id: int
    contract_key: str
    entry_time: datetime
    entry_price: float
    quantity: int
    option_type: str
    strike: float
    expiry: str
    stop_price: float | None
    target_price: float | None


class HistoricalOptionsBacktestEngine:
    """Execute scheduled long option signals against real historical option OHLC."""

    def _validate(self, rows: list[HistoricalOptionBar]) -> list[HistoricalOptionBar]:
        if not rows:
            raise ValueError("NO_HISTORICAL_OPTION_DATA")

        ordered = sorted(rows, key=lambda r: (r.timestamp, r.contract_key))
        if ordered != rows:
            raise ValueError("OPTION_DATA_MUST_BE_CHRONOLOGICALLY_SORTED")

        seen = set()
        for row in rows:
            key = (row.contract_key, row.timestamp)
            if key in seen:
                raise ValueError("DUPLICATE_OPTION_BAR")
            seen.add(key)

            if row.high < max(row.open, row.close) or row.low > min(row.open, row.close):
                raise ValueError("INVALID_OPTION_OHLC")

            if row.bid is not None and row.ask is not None and row.bid > row.ask:
                raise ValueError("BID_ASK_CROSSED")

        return rows

    @staticmethod
    def _costs(entry: float, exit: float, qty: int, config: OptionsBacktestConfig) -> float:
        cc = CostConfig(
            brokerage_per_order=config.brokerage_per_order,
            exchange_txn_rate=config.exchange_txn_rate,
            sebi_rate=config.sebi_rate,
            gst_rate=config.gst_rate,
            stamp_duty_rate=config.stamp_duty_rate,
            stt_rate=config.stt_sell_rate,
        )
        return transaction_cost(
            entry_value=entry * qty,
            exit_value=exit * qty,
            config=cc,
        )

    @staticmethod
    def _buy_fill(row: HistoricalOptionBar, slippage_bps: float) -> float:
        reference = row.ask if row.ask is not None else row.open
        return max(0.000001, float(reference) * (1 + slippage_bps / 10000))

    @staticmethod
    def _sell_fill(
        row: HistoricalOptionBar,
        slippage_bps: float,
        reference: float | None = None,
    ) -> float:
        ref = reference if reference is not None else (
            row.bid if row.bid is not None else row.open
        )
        return max(0.000001, float(ref) * (1 - slippage_bps / 10000))

    @staticmethod
    def _resolve_levels(
        signal: dict[str, Any],
        entry_price: float,
    ) -> tuple[float | None, float | None]:
        stop = signal.get("stop_price")
        target = signal.get("target_price")

        if stop is not None or target is not None:
            return (
                float(stop) if stop is not None else None,
                float(target) if target is not None else None,
            )

        stop_pct = signal.get("stop_pct")
        target_rr = signal.get("target_rr")
        if stop_pct is None or target_rr is None:
            return None, None

        risk = max(entry_price * float(stop_pct), 0.000001)
        return (
            max(0.000001, entry_price - risk),
            entry_price + risk * float(target_rr),
        )

    def run(
        self,
        rows: list[HistoricalOptionBar],
        signal_fn: Callable[[dict[str, Any]], dict[str, Any] | None],
        *,
        strategy_name: str,
        config: OptionsBacktestConfig | None = None,
        scheduled_signals: dict[datetime, list[dict[str, Any]]] | None = None,
    ) -> OptionsBacktestResult:
        config = config or OptionsBacktestConfig()
        rows = self._validate(rows)

        by_time: dict[datetime, list[HistoricalOptionBar]] = defaultdict(list)
        series: dict[str, list[HistoricalOptionBar]] = defaultdict(list)

        for row in rows:
            by_time[row.timestamp].append(row)
            series[row.contract_key].append(row)

        for values in series.values():
            values.sort(key=lambda r: r.timestamp)

        signal_schedule = scheduled_signals or {}
        signal_times = set(signal_schedule)
        # Include scheduled decision timestamps even if a provider happens to miss
        # a bar at that exact timestamp. This prevents signals from disappearing.
        times = sorted(set(by_time) | signal_times)

        history: list[HistoricalOptionBar] = []
        trades: list[OptionsTradeRecord] = []
        capital = float(config.initial_capital)
        open_trade: _OpenTrade | None = None
        trade_id = 0
        warnings: list[str] = []

        engine_signals_evaluated = 0
        engine_signals_generated = 0
        signals_blocked_open_position = 0
        signals_blocked_same_timestamp = 0
        signals_without_execution_bar = 0
        signals_without_future_exit_bar = 0
        contracts_seen: set[str] = set()
        next_index_by_contract = {k: 0 for k in series}

        first_scheduled_signal = min(signal_times) if signal_times else None
        last_scheduled_signal = max(signal_times) if signal_times else None

        def close_trade(
            trade: _OpenTrade,
            row: HistoricalOptionBar,
            exit_price: float,
            reason: str,
        ) -> None:
            nonlocal capital

            gross = (exit_price - trade.entry_price) * trade.quantity
            costs = self._costs(trade.entry_price, exit_price, trade.quantity, config)
            net = gross - costs
            capital += net

            trades.append(
                OptionsTradeRecord(
                    trade_id=trade.trade_id,
                    contract_key=trade.contract_key,
                    option_type=trade.option_type,
                    strike=trade.strike,
                    expiry=trade.expiry,
                    entry_time=trade.entry_time,
                    exit_time=row.timestamp,
                    entry_price=round(trade.entry_price, 6),
                    exit_price=round(exit_price, 6),
                    quantity=trade.quantity,
                    gross_pnl=round(gross, 6),
                    costs=round(costs, 6),
                    net_pnl=round(net, 6),
                    exit_reason=reason,
                )
            )

        for idx, decision_time in enumerate(times):
            current_bars = by_time.get(decision_time, [])
            history.extend(current_bars)

            # 1) Advance/close the current position using every real option bar up
            # to this point. Do not require the contract bar timestamp to equal the
            # global timeline timestamp.
            if open_trade is not None:
                open_contract_key = open_trade.contract_key
                contract_rows = series.get(open_contract_key, [])
                pos_idx = next_index_by_contract[open_contract_key]

                while pos_idx < len(contract_rows):
                    candidate = contract_rows[pos_idx]

                    if candidate.timestamp <= open_trade.entry_time:
                        pos_idx += 1
                        continue

                    if candidate.timestamp > decision_time:
                        break

                    if (
                        open_trade.stop_price is not None
                        and candidate.low <= open_trade.stop_price
                    ):
                        close_trade(
                            open_trade,
                            candidate,
                            self._sell_fill(
                                candidate,
                                config.slippage_bps,
                                open_trade.stop_price,
                            ),
                            "STOP_LOSS",
                        )
                        open_trade = None
                        pos_idx += 1
                        break

                    if (
                        open_trade.target_price is not None
                        and candidate.high >= open_trade.target_price
                    ):
                        close_trade(
                            open_trade,
                            candidate,
                            self._sell_fill(
                                candidate,
                                config.slippage_bps,
                                open_trade.target_price,
                            ),
                            "TARGET",
                        )
                        open_trade = None
                        pos_idx += 1
                        break

                    if candidate.timestamp.date().isoformat() >= open_trade.expiry:
                        close_trade(
                            open_trade,
                            candidate,
                            self._sell_fill(
                                candidate,
                                config.slippage_bps,
                                candidate.close,
                            ),
                            "EXPIRY",
                        )
                        open_trade = None
                        pos_idx += 1
                        break

                    pos_idx += 1

                next_index_by_contract[open_contract_key] = pos_idx

                # Critical: a selected historical option contract can end before the
                # overall backtest window. If its final real bar is reached without
                # a stop/target/expiry event, do not leave the position permanently
                # open and block every later signal. Close it on the contract's last real historical bar.
                if open_trade is not None and pos_idx >= len(contract_rows):
                    last_bar = contract_rows[-1] if contract_rows else None
                    if last_bar is None:
                        warnings.append(
                            f"OPEN_POSITION_WITHOUT_FINAL_BAR:{open_contract_key}"
                        )
                        open_trade = None
                    else:
                        reason = (
                            "EXPIRY"
                            if last_bar.timestamp.date().isoformat() >= open_trade.expiry
                            else "END_OF_CONTRACT_DATA"
                        )
                        close_trade(
                            open_trade,
                            last_bar,
                            self._sell_fill(
                                last_bar,
                                config.slippage_bps,
                                last_bar.close,
                            ),
                            reason,
                        )
                        open_trade = None

            scheduled = list(signal_schedule.get(decision_time) or [])

            if open_trade is not None and scheduled:
                signals_blocked_open_position += len(scheduled)
                continue

            if not scheduled:
                # Backward-compatible support for callers that still provide a
                # signal function rather than a schedule.
                if signal_times:
                    continue
                if idx >= len(times) - 1:
                    continue

                engine_signals_evaluated += 1
                signal = signal_fn(
                    {
                        "timestamp": decision_time,
                        "history": history,
                        "chain": current_bars,
                    }
                )
                scheduled = [signal] if signal else []

            engine_signals_evaluated += len(scheduled)

            # One active position per engine. When several signals share an identical
            # timestamp, execute the first deterministically and record the rest.
            if len(scheduled) > 1:
                signals_blocked_same_timestamp += len(scheduled) - 1

            signal = scheduled[0]
            if not signal:
                continue

            engine_signals_generated += 1

            contract_key = str(signal.get("contract_key") or "")
            action = str(signal.get("action", "BUY")).upper()

            if action != "BUY" or not contract_key:
                warnings.append(f"INVALID_SIGNAL_CONTRACT:{decision_time.isoformat()}")
                continue

            contracts_seen.add(contract_key)
            contract_rows = series.get(contract_key, [])

            if not contract_rows:
                signals_without_execution_bar += 1
                warnings.append(f"NO_EXECUTION_BAR:{contract_key}:{decision_time.isoformat()}")
                continue

            timestamps = [row.timestamp for row in contract_rows]
            candidate_idx = bisect_right(timestamps, decision_time) + max(
                int(config.latency_bars) - 1,
                0,
            )

            # Same-bar exits are intentionally disallowed to avoid look-ahead.
            # Therefore the chosen entry bar must have a real future candle.
            if candidate_idx >= len(contract_rows):
                signals_without_execution_bar += 1
                warnings.append(
                    f"NO_EXECUTION_BAR:{contract_key}:{decision_time.isoformat()}"
                )
                continue

            if candidate_idx >= len(contract_rows) - 1:
                signals_without_future_exit_bar += 1
                warnings.append(
                    f"NO_FUTURE_EXIT_BAR:{contract_key}:{decision_time.isoformat()}"
                )
                continue

            entry_bar = contract_rows[candidate_idx]
            if entry_bar.timestamp <= decision_time:
                raise ValueError("LOOKAHEAD_DETECTED")

            trade_id += 1
            entry_price = self._buy_fill(entry_bar, config.slippage_bps)
            stop_price, target_price = self._resolve_levels(signal, entry_price)

            open_trade = _OpenTrade(
                trade_id=trade_id,
                contract_key=contract_key,
                entry_time=entry_bar.timestamp,
                entry_price=entry_price,
                quantity=int(signal.get("quantity", config.quantity)),
                option_type=entry_bar.option_type,
                strike=entry_bar.strike,
                expiry=entry_bar.expiry,
                stop_price=stop_price,
                target_price=target_price,
            )
            next_index_by_contract[contract_key] = candidate_idx + 1

            if config.max_trades is not None and len(trades) >= config.max_trades:
                warnings.append("MAX_TRADES_REACHED")
                break

        if open_trade is not None:
            contract_rows = series.get(open_trade.contract_key, [])
            last_bar = contract_rows[-1] if contract_rows else None

            if last_bar is None:
                warnings.append("OPEN_POSITION_WITHOUT_FINAL_BAR")
            else:
                reason = (
                    "EXPIRY"
                    if last_bar.timestamp.date().isoformat() >= open_trade.expiry
                    else "END_OF_DATA"
                )
                close_trade(
                    open_trade,
                    last_bar,
                    self._sell_fill(
                        last_bar,
                        config.slippage_bps,
                        last_bar.close,
                    ),
                    reason,
                )
                open_trade = None

        net_profit = sum(t.net_pnl for t in trades)
        wins = [t.net_pnl for t in trades if t.net_pnl > 0]
        losses = [t.net_pnl for t in trades if t.net_pnl < 0]
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        max_dd = self._max_drawdown(trades, config.initial_capital)

        metrics: dict[str, object] = {
            "initial_capital": config.initial_capital,
            "final_equity": capital,
            "net_profit": net_profit,
            "return_pct": (
                net_profit / config.initial_capital * 100
                if config.initial_capital
                else None
            ),
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate_pct": (
                len(wins) / len(trades) * 100 if trades else 0.0
            ),
            "profit_factor": (
                gross_profit / gross_loss if gross_loss > 0 else None
            ),
            "max_drawdown": max_dd,
            "max_drawdown_pct": (
                max_dd / config.initial_capital * 100
                if config.initial_capital
                else None
            ),
            "engine_signals_evaluated": engine_signals_evaluated,
            "engine_signals_generated": engine_signals_generated,
            "signals_blocked_open_position": signals_blocked_open_position,
            "signals_blocked_same_timestamp": signals_blocked_same_timestamp,
            "signals_without_execution_bar": signals_without_execution_bar,
            "signals_without_future_exit_bar": signals_without_future_exit_bar,
            "contracts_used": len(contracts_seen),
            "first_scheduled_signal": (
                first_scheduled_signal.isoformat()
                if first_scheduled_signal
                else None
            ),
            "last_scheduled_signal": (
                last_scheduled_signal.isoformat()
                if last_scheduled_signal
                else None
            ),
            "first_trade_exit": (
                trades[0].exit_time.isoformat() if trades else None
            ),
            "last_trade_exit": (
                trades[-1].exit_time.isoformat() if trades else None
            ),
            "timeline_last_timestamp": (
                times[-1].isoformat() if times else None
            ),
            "trade_limit": config.max_trades,
            "trade_limit_hit": (
                config.max_trades is not None
                and len(trades) >= config.max_trades
            ),
        }

        for key, value in list(metrics.items()):
            if isinstance(value, float) and not math.isfinite(value):
                metrics[key] = None

        return OptionsBacktestResult(
            strategy=strategy_name,
            metrics=metrics,
            trades=trades,
            warnings=warnings,
        )

    @staticmethod
    def _max_drawdown(
        trades: list[OptionsTradeRecord],
        initial: float,
    ) -> float:
        equity = initial
        peak = initial
        max_dd = 0.0

        for trade in trades:
            equity += trade.net_pnl
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)

        return max_dd