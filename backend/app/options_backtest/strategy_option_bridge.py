from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from collections import Counter
from .engine import HistoricalOptionsBacktestEngine
from .models import OptionsBacktestConfig, HistoricalOptionBar
from .upstox_loader import UpstoxHistoricalOptionLoader, UpstoxOptionContract
from ..backtest.strategy_adapter import StrategyBacktestAdapter
from ..features.service import FeatureService
from ..structure.service import StructureService
from ..strategies.models import StrategyContext


@dataclass(frozen=True)
class SelectedContract:
    instrument_key: str
    underlying_symbol: str
    expiry: str
    strike: float
    option_type: str
    trading_symbol: str
    lot_size: int


def normalize_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        # Persisted phase5 candles are naive IST timestamps.
        from zoneinfo import ZoneInfo
        value = value.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    return value.astimezone(timezone.utc)


def build_underlying_context(history: list[dict]) -> StrategyContext:
    features = FeatureService().calculate(history, session_ids=None)
    structure = StructureService().analyze(history)
    return StrategyContext(
        timestamp=history[-1]["timestamp"],
        candles=history,
        features=features,
        structure=structure,
        options=None,
        regime=structure.get("regime"),
    )


def normalize_rows(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        item = dict(row)
        ts = item.get("timestamp")
        ts = normalize_datetime(ts)
        if ts is None:
            raise ValueError("Every underlying row must contain timestamp")
        item["timestamp"] = ts
        out.append(item)
    out.sort(key=lambda x: x["timestamp"])
    return out


def _as_result_payload(result: Any) -> dict[str, Any]:
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)


def _strategy_signals(
    underlying: list[dict],
    *,
    preferred_strategy: str,
    signal_start: datetime | None,
    signal_end: datetime | None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    adapter = StrategyBacktestAdapter(
        build_underlying_context,
        preferred_strategy=preferred_strategy,
    )

    events: list[dict[str, Any]] = []
    diagnostics = {
        "signals_evaluated": 0,
        "signals_generated": 0,
    }
    previous_triggered = False

    for idx in range(15, len(underlying) + 1):
        ts = underlying[idx - 1]["timestamp"]
        if signal_start and ts < signal_start:
            continue
        if signal_end and ts > signal_end:
            break

        diagnostics["signals_evaluated"] += 1
        signal = adapter.signal(underlying[:idx])
        triggered = bool(signal)

        if not triggered:
            previous_triggered = False
            continue

        if previous_triggered:
            continue

        previous_triggered = True
        diagnostics["signals_generated"] += 1
        current = underlying[idx - 1]
        events.append(
            {
                "timestamp": ts,
                "direction": str(signal.get("direction", "")).upper(),
                "strategy": signal.get("strategy") or preferred_strategy,
                "entry": signal.get("entry"),
                "invalidation": signal.get("invalidation"),
                "target_1": signal.get("target_1"),
                "target_2": signal.get("target_2"),
                "underlying_close": float(current.get("close")) if current.get("close") is not None else None,
            }
        )

    return events, diagnostics


def _select_upstox_contract(
    loader: UpstoxHistoricalOptionLoader,
    *,
    event: dict[str, Any],
    strike_reference: float,
    expiry: str | None,
    strike_mode: str,
    strike_offset: int,
) -> UpstoxOptionContract:
    mode = strike_mode.upper()
    # ATM/ATM_OFFSET must use the underlying price at the actual signal time,
    # not a hard-coded strike reference. Fixed strike-reference remains available
    # for OFFSET mode and explicit research experiments.
    effective_reference = (
        event.get("underlying_close")
        if mode in {"ATM", "ATM_OFFSET"} and event.get("underlying_close") is not None
        else strike_reference
    )
    return loader.select_contract(
        signal_time=normalize_datetime(event["timestamp"]),
        direction=event["direction"],
        strike_reference=float(effective_reference),
        expiry=expiry,
        strike_mode=mode,
        strike_offset=int(strike_offset),
    )



def _cache_rows_payload(rows: list[dict]) -> str:
    payload = []
    for row in rows:
        payload.append(
            {
                "timestamp": normalize_datetime(row["timestamp"]).isoformat(),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("volume"),
                "open_interest": row.get("open_interest"),
            }
        )
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _market_cache_key(*parts: Any) -> str:
    raw = json.dumps([str(part) if part is not None else None for part in parts], separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _prepare_option_market(
    underlying: list[dict],
    *,
    preferred_strategy: str,
    strike_reference: float,
    expiry: str | None,
    strike_mode: str,
    strike_offset: int,
    signal_start: datetime | None,
    signal_end: datetime | None,
    upstox: UpstoxHistoricalOptionLoader,
) -> dict[str, Any]:
    events, signal_diag = _strategy_signals(
        underlying,
        preferred_strategy=preferred_strategy,
        signal_start=signal_start,
        signal_end=signal_end,
    )

    option_rows: list[HistoricalOptionBar] = []
    prepared_events: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []
    skipped: list[str] = []

    if not events:
        return {
            "events": [],
            "signal_diag": signal_diag,
            "option_rows": [],
            "prepared_events": [],
            "selections": [],
            "skipped": [],
        }

    resolved_events: list[tuple[dict[str, Any], UpstoxOptionContract]] = []
    for event in events:
        try:
            selected = _select_upstox_contract(
                upstox,
                event=event,
                strike_reference=strike_reference,
                expiry=expiry,
                strike_mode=strike_mode,
                strike_offset=strike_offset,
            )
            resolved_events.append((event, selected))
        except (ValueError, FileNotFoundError, OSError, TypeError) as exc:
            skipped.append(
                f"SIGNAL_SKIP:{event['timestamp'].isoformat()}:{type(exc).__name__}:{exc}"
            )

    grouped: dict[str, list[tuple[dict[str, Any], UpstoxOptionContract]]] = {}
    for event, selected in resolved_events:
        grouped.setdefault(selected.instrument_key, []).append((event, selected))

    def _load_group(item):
        instrument_key, group = item
        selected = group[0][1]
        earliest_signal = min(
            normalize_datetime(event["timestamp"]) for event, _ in group
        )
        try:
            loaded = upstox.load_contract(
                selected,
                signal_time=earliest_signal,
                end_time=signal_end,
                interval="5minute",
            )
            return instrument_key, group, loaded, None
        except (ValueError, FileNotFoundError, OSError, TypeError) as exc:
            return instrument_key, group, [], exc

    # Historical option downloads are independent by contract. Fetch them in
    # parallel so a multi-month backtest does not wait sequentially on every
    # Upstox HTTP request. Keep the worker count conservative for provider limits.
    max_workers = max(1, min(int(os.getenv("BACKTEST_OPTION_DOWNLOAD_WORKERS", "6")), 8))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_load_group, item) for item in grouped.items()]
        results = [future.result() for future in as_completed(futures)]

    # Restore deterministic ordering after concurrent downloads.
    results.sort(key=lambda item: item[0])

    for instrument_key, group, loaded, error in results:
        selected = group[0][1]
        if error is not None:
            for event, _ in group:
                skipped.append(
                    f"CONTRACT_LOAD_SKIP:{event['timestamp'].isoformat()}:{type(error).__name__}:{error}"
                )
            continue

        earliest_signal = min(
            normalize_datetime(event["timestamp"]) for event, _ in group
        )
        if not loaded:
            skipped.append(
                f"NO_OPTION_BARS:{selected.instrument_key}:{earliest_signal.isoformat()}"
            )
            continue

        option_rows.extend(loaded)
        for event, contract in group:
            signal_time = normalize_datetime(event["timestamp"])
            first_bar = next(
                (r for r in loaded if r.timestamp >= signal_time), None
            )
            if first_bar is None:
                skipped.append(
                    f"NO_EXECUTION_SETUP_BAR:{contract.instrument_key}:{signal_time.isoformat()}"
                )
                continue

            prepared_events.append(
                {
                    "decision_timestamp": first_bar.timestamp.isoformat(),
                    "contract_key": contract.instrument_key,
                    "strategy_signal_time": signal_time.isoformat(),
                    "direction": event["direction"],
                    "underlying_close": event.get("underlying_close"),
                }
            )

            selections.append(
                {
                    "instrument_key": contract.instrument_key,
                    "trading_symbol": contract.trading_symbol,
                    "underlying_symbol": contract.underlying_symbol,
                    "expiry": contract.expiry,
                    "strike": contract.strike,
                    "option_type": contract.option_type,
                    "lot_size": int(contract.lot_size),
                    "strategy_signal_time": signal_time.isoformat(),
                }
            )

    if not option_rows:
        reason = skipped[0] if skipped else "NO_OPTION_BARS_AVAILABLE"
        raise ValueError(f"NO_HISTORICAL_OPTION_DATA_FOR_SIGNALS:{reason}")

    dedup = {(r.contract_key, r.timestamp): r for r in option_rows}
    option_rows = sorted(
        dedup.values(),
        key=lambda r: (r.timestamp, r.contract_key),
    )

    return {
        "events": events,
        "signal_diag": signal_diag,
        "option_rows": option_rows,
        "prepared_events": prepared_events,
        "selections": selections,
        "skipped": skipped,
    }


@lru_cache(maxsize=8)
def _prepare_option_market_cached(
    rows_json: str,
    preferred_strategy: str,
    strike_reference: float,
    expiry: str | None,
    strike_mode: str,
    strike_offset: int,
    signal_start_iso: str | None,
    signal_end_iso: str | None,
    access_token: str,
    underlying_key: str,
) -> dict[str, Any]:
    rows_payload = json.loads(rows_json)
    underlying = normalize_rows(rows_payload)
    loader = UpstoxHistoricalOptionLoader(
        underlying_key=underlying_key,
    )
    return _prepare_option_market(
        underlying,
        preferred_strategy=preferred_strategy,
        strike_reference=strike_reference,
        expiry=expiry,
        strike_mode=strike_mode,
        strike_offset=strike_offset,
        signal_start=normalize_datetime(signal_start_iso),
        signal_end=normalize_datetime(signal_end_iso),
        upstox=loader,
    )


def clear_strategy_option_cache() -> None:
    _prepare_option_market_cached.cache_clear()


def strategy_option_cache_info() -> dict[str, Any]:
    return {"prepared_market": _prepare_option_market_cached.cache_info()}


def _normalize_builder_leg(leg: dict[str, Any]) -> dict[str, Any]:
    action = str(leg.get("action") or "BUY").upper()
    option_type = str(leg.get("option_type") or "CE").upper()
    mode = str(leg.get("strike_mode") or "ATM").upper()

    if action not in {"BUY", "SELL"}:
        raise ValueError("OPTION_LEG_ACTION_MUST_BE_BUY_OR_SELL")
    if option_type not in {"CE", "PE"}:
        raise ValueError("OPTION_LEG_TYPE_MUST_BE_CE_OR_PE")
    if mode not in {"ATM", "ATM_PLUS", "ATM_MINUS", "SPECIFIC"}:
        raise ValueError(f"UNSUPPORTED_OPTION_LEG_STRIKE_MODE:{mode}")

    return {
        "action": action,
        "option_type": option_type,
        "expiry_mode": str(leg.get("expiry_mode") or "NEAREST").upper(),
        "expiry": leg.get("expiry"),
        "strike_mode": mode,
        "strike_offset": abs(int(float(leg.get("strike_offset") or 0))),
        "strike": float(leg["strike"]) if leg.get("strike") not in (None, "") else None,
        "lots": max(1, int(float(leg.get("lots") or 1))),
    }


def _run_single_leg_schedule(
    *,
    rows: list[HistoricalOptionBar],
    scheduled: dict[datetime, list[dict[str, Any]]],
    strategy_name: str,
    config: OptionsBacktestConfig,
) -> dict[str, Any]:
    """
    Small action-aware single-leg executor used only for Strategy Builder legs.
    The existing HistoricalOptionsBacktestEngine remains untouched for legacy
    single-leg mode.
    """
    series: dict[str, list[HistoricalOptionBar]] = defaultdict(list)
    for row in rows:
        series[row.contract_key].append(row)
    for values in series.values():
        values.sort(key=lambda r: r.timestamp)

    def buy_fill(row: HistoricalOptionBar) -> float:
        return HistoricalOptionsBacktestEngine._buy_fill(row, config.slippage_bps)

    def sell_fill(row: HistoricalOptionBar, reference: float | None = None) -> float:
        return HistoricalOptionsBacktestEngine._sell_fill(
            row,
            config.slippage_bps,
            reference,
        )

    def costs(entry: float, exit: float, qty: int) -> float:
        return HistoricalOptionsBacktestEngine._costs(entry, exit, qty, config)

    open_trade: dict[str, Any] | None = None
    cursors = {key: 0 for key in series}
    output: list[dict[str, Any]] = []
    warnings: list[str] = []
    trade_id = 0

    times = sorted(scheduled)

    def close_position(trade: dict[str, Any], row: HistoricalOptionBar, exit_price: float, reason: str) -> None:
        action = trade["action"]
        gross = (
            (exit_price - trade["entry_price"]) * trade["quantity"]
            if action == "BUY"
            else (trade["entry_price"] - exit_price) * trade["quantity"]
        )
        fee = costs(trade["entry_price"], exit_price, trade["quantity"])
        output.append(
            {
                "trade_id": trade["trade_id"],
                "contract_key": trade["contract_key"],
                "option_type": trade["option_type"],
                "strike": trade["strike"],
                "expiry": trade["expiry"],
                "entry_time": trade["entry_time"].isoformat(),
                "exit_time": row.timestamp.isoformat(),
                "entry_price": round(trade["entry_price"], 6),
                "exit_price": round(exit_price, 6),
                "quantity": trade["quantity"],
                "gross_pnl": round(gross, 6),
                "costs": round(fee, 6),
                "net_pnl": round(gross - fee, 6),
                "exit_reason": reason,
                "action": action,
                "strategy_trade_id": trade["strategy_trade_id"],
            }
        )

    for decision_time in times:
        # Advance current position through its own contract bars up to this decision.
        if open_trade is not None:
            key = open_trade["contract_key"]
            bars = series.get(key, [])
            pos = cursors.get(key, 0)

            while pos < len(bars):
                bar = bars[pos]
                if bar.timestamp <= open_trade["entry_time"]:
                    pos += 1
                    continue
                if bar.timestamp > decision_time:
                    break

                stop = open_trade["stop_price"]
                target = open_trade["target_price"]
                action = open_trade["action"]

                stop_hit = (
                    stop is not None
                    and (
                        bar.low <= stop
                        if action == "BUY"
                        else bar.high >= stop
                    )
                )
                if stop_hit:
                    close_price = (
                        sell_fill(bar, stop)
                        if action == "BUY"
                        else buy_fill(bar)
                    )
                    close_position(open_trade, bar, close_price, "STOP_LOSS")
                    open_trade = None
                    pos += 1
                    break

                target_hit = (
                    target is not None
                    and (
                        bar.high >= target
                        if action == "BUY"
                        else bar.low <= target
                    )
                )
                if target_hit:
                    close_price = (
                        sell_fill(bar, target)
                        if action == "BUY"
                        else buy_fill(bar)
                    )
                    close_position(open_trade, bar, close_price, "TARGET")
                    open_trade = None
                    pos += 1
                    break

                if bar.timestamp.date().isoformat() >= open_trade["expiry"]:
                    close_price = (
                        sell_fill(bar, bar.close)
                        if action == "BUY"
                        else buy_fill(bar)
                    )
                    close_position(open_trade, bar, close_price, "EXPIRY")
                    open_trade = None
                    pos += 1
                    break

                pos += 1

            cursors[key] = pos

            if open_trade is not None and pos >= len(bars):
                if bars:
                    last = bars[-1]
                    close_price = (
                        sell_fill(last, last.close)
                        if open_trade["action"] == "BUY"
                        else buy_fill(last)
                    )
                    reason = (
                        "EXPIRY"
                        if last.timestamp.date().isoformat() >= open_trade["expiry"]
                        else "END_OF_CONTRACT_DATA"
                    )
                    close_position(open_trade, last, close_price, reason)
                    open_trade = None

        scheduled_items = scheduled.get(decision_time) or []
        if not scheduled_items:
            continue

        if open_trade is not None:
            continue

        signal = scheduled_items[0]
        key = str(signal["contract_key"])
        bars = series.get(key, [])
        if not bars:
            warnings.append(f"NO_EXECUTION_BAR:{key}:{decision_time.isoformat()}")
            continue

        timestamps = [bar.timestamp for bar in bars]
        idx = bisect_right(timestamps, decision_time)
        if idx >= len(bars):
            warnings.append(f"NO_EXECUTION_BAR:{key}:{decision_time.isoformat()}")
            continue
        if idx >= len(bars) - 1:
            warnings.append(f"NO_FUTURE_EXIT_BAR:{key}:{decision_time.isoformat()}")
            continue

        entry_bar = bars[idx]
        action = str(signal["action"]).upper()
        entry_price = buy_fill(entry_bar) if action == "BUY" else sell_fill(entry_bar)

        risk = max(entry_price * float(signal.get("stop_pct", 0.15)), 0.000001)
        if action == "SELL":
            stop_price = entry_price + risk
            target_price = max(
                0.000001,
                entry_price - risk * float(signal.get("target_rr", 1.5)),
            )
        else:
            stop_price = max(0.000001, entry_price - risk)
            target_price = entry_price + risk * float(signal.get("target_rr", 1.5))

        trade_id += 1
        open_trade = {
            "trade_id": trade_id,
            "contract_key": key,
            "option_type": entry_bar.option_type,
            "strike": entry_bar.strike,
            "expiry": entry_bar.expiry,
            "entry_time": entry_bar.timestamp,
            "entry_price": entry_price,
            "action": action,
            "quantity": int(signal["quantity"]),
            "stop_price": stop_price,
            "target_price": target_price,
            "strategy_trade_id": signal["strategy_trade_id"],
        }
        cursors[key] = idx + 1

    # Close final open position.
    if open_trade is not None:
        bars = series.get(open_trade["contract_key"], [])
        if bars:
            last = bars[-1]
            close_price = (
                sell_fill(last, last.close)
                if open_trade["action"] == "BUY"
                else buy_fill(last)
            )
            reason = (
                "EXPIRY"
                if last.timestamp.date().isoformat() >= open_trade["expiry"]
                else "END_OF_DATA"
            )
            close_position(open_trade, last, close_price, reason)
        else:
            warnings.append("OPEN_POSITION_WITHOUT_FINAL_BAR")

    net = sum(float(t["net_pnl"]) for t in output)
    wins = [t["net_pnl"] for t in output if t["net_pnl"] > 0]
    losses = [t["net_pnl"] for t in output if t["net_pnl"] < 0]
    return {
        "strategy": strategy_name,
        "trades": output,
        "warnings": warnings,
        "net_profit": net,
        "wins": len(wins),
        "losses": len(losses),
    }


def _run_multi_leg_backtest(
    *,
    underlying: list[dict],
    events: list[dict[str, Any]],
    legs: list[dict[str, Any]],
    loader: UpstoxHistoricalOptionLoader,
    config: OptionsBacktestConfig,
    strategy_name: str,
    strike_reference: float,
    stop_pct: float,
    target_rr: float,
    signal_end: datetime | None,
) -> dict[str, Any]:
    normalized_legs = [_normalize_builder_leg(leg) for leg in legs]

    selections: list[dict[str, Any]] = []
    prepared_by_leg: dict[int, list[dict[str, Any]]] = defaultdict(list)
    contracts: dict[str, UpstoxOptionContract] = {}
    earliest: dict[str, datetime] = {}
    skipped: list[str] = []

    for event in events:
        event_ts = normalize_datetime(event["timestamp"])
        reference = float(event.get("underlying_close") or strike_reference)

        for leg_index, leg in enumerate(normalized_legs, start=1):
            try:
                requested_expiry = (
                    str(leg["expiry"])
                    if leg["expiry_mode"] == "SPECIFIC" and leg.get("expiry")
                    else None
                )
                contract = loader.select_contract_for_leg(
                    signal_time=event_ts,
                    option_type=leg["option_type"],
                    strike_reference=reference,
                    expiry=requested_expiry,
                    strike_mode=leg["strike_mode"],
                    strike_offset=leg["strike_offset"],
                    specific_strike=leg["strike"],
                )
                contracts[contract.instrument_key] = contract
                earliest[contract.instrument_key] = min(
                    earliest.get(contract.instrument_key, event_ts),
                    event_ts,
                )
                prepared_by_leg[leg_index].append(
                    {"event": event, "leg": leg, "contract": contract}
                )
                selections.append(
                    {
                        "leg_index": leg_index,
                        "action": leg["action"],
                        "option_type": contract.option_type,
                        "instrument_key": contract.instrument_key,
                        "trading_symbol": contract.trading_symbol,
                        "underlying_symbol": contract.underlying_symbol,
                        "expiry": contract.expiry,
                        "strike": contract.strike,
                        "lot_size": int(contract.lot_size),
                        "strategy_signal_time": event_ts.isoformat(),
                    }
                )
            except (ValueError, FileNotFoundError, OSError, TypeError) as exc:
                skipped.append(
                    f"LEG_SKIP:{event_ts.isoformat()}:LEG{leg_index}:{type(exc).__name__}:{exc}"
                )

    if not contracts:
        reason = skipped[0] if skipped else "NO_OPTION_CONTRACTS_SELECTED"
        raise ValueError(f"NO_HISTORICAL_OPTION_DATA_FOR_LEGS:{reason}")

    option_rows_by_contract: dict[str, list[HistoricalOptionBar]] = {}
    for key, contract in contracts.items():
        try:
            loaded = loader.load_contract(
                contract,
                signal_time=earliest[key],
                end_time=signal_end,
                interval="5minute",
            )
            if loaded:
                option_rows_by_contract[key] = loaded
            else:
                skipped.append(f"NO_OPTION_BARS:{key}")
        except (ValueError, FileNotFoundError, OSError, TypeError) as exc:
            skipped.append(f"CONTRACT_LOAD_SKIP:{key}:{type(exc).__name__}:{exc}")

    if not option_rows_by_contract:
        reason = skipped[0] if skipped else "NO_OPTION_BARS_AVAILABLE"
        raise ValueError(f"NO_HISTORICAL_OPTION_DATA_FOR_LEGS:{reason}")

    flat_trades: list[dict[str, Any]] = []
    leg_results: list[dict[str, Any]] = []

    for leg_index, items in prepared_by_leg.items():
        scheduled: dict[datetime, list[dict[str, Any]]] = {}
        leg_rows: list[HistoricalOptionBar] = []

        for item in items:
            key = item["contract"].instrument_key
            bars = option_rows_by_contract.get(key, [])
            leg_rows.extend(bars)

            event_ts = normalize_datetime(item["event"]["timestamp"])
            first_bar = next((bar for bar in bars if bar.timestamp >= event_ts), None)
            if first_bar is None:
                skipped.append(
                    f"NO_EXECUTION_SETUP_BAR:LEG{leg_index}:{key}:{event_ts.isoformat()}"
                )
                continue

            scheduled.setdefault(first_bar.timestamp, []).append(
                {
                    "action": item["leg"]["action"],
                    "contract_key": key,
                    "stop_pct": stop_pct,
                    "target_rr": target_rr,
                    "quantity": int(item["leg"]["lots"]) * int(item["contract"].lot_size),
                    "strategy_trade_id": event_ts.isoformat(),
                }
            )

        if not scheduled:
            continue

        leg_rows = list({(row.contract_key, row.timestamp): row for row in leg_rows}.values())
        leg_rows.sort(key=lambda row: (row.timestamp, row.contract_key))

        result = _run_single_leg_schedule(
            rows=leg_rows,
            scheduled=scheduled,
            strategy_name=f"{strategy_name} · LEG {leg_index}",
            config=config,
        )
        leg_results.append({"leg_index": leg_index, **result})

        for trade in result["trades"]:
            flat_trades.append({**trade, "leg_index": leg_index})

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in flat_trades:
        groups[str(trade["strategy_trade_id"])].append(trade)

    strategy_groups: list[dict[str, Any]] = []
    for group_id, group in groups.items():
        entries = [x["entry_time"] for x in group if x.get("entry_time")]
        exits = [x["exit_time"] for x in group if x.get("exit_time")]
        strategy_groups.append(
            {
                "strategy_trade_id": group_id,
                "entry_time": min(entries) if entries else None,
                "net_pnl": sum(float(x["net_pnl"]) for x in group),
                "exit_time": max(exits) if exits else None,
                "leg_transactions": len(group),
            }
        )
    strategy_groups.sort(key=lambda x: str(x.get("exit_time") or ""))

    net = sum(x["net_pnl"] for x in strategy_groups)
    wins = [x["net_pnl"] for x in strategy_groups if x["net_pnl"] > 0]
    losses = [x["net_pnl"] for x in strategy_groups if x["net_pnl"] < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    equity = float(config.initial_capital)
    peak = equity
    max_drawdown = 0.0
    for group in strategy_groups:
        equity += group["net_pnl"]
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    return {
        "strategy": strategy_name,
        "mode": "HISTORICAL_MULTI_LEG_OPTIONS",
        "metrics": {
            "initial_capital": config.initial_capital,
            "final_equity": equity,
            "net_profit": net,
            "return_pct": net / config.initial_capital * 100,
            "total_trades": len(strategy_groups),
            "leg_transactions": len(flat_trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate_pct": len(wins) / len(strategy_groups) * 100 if strategy_groups else 0.0,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else None,
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown / config.initial_capital * 100,
            "strategy_legs": len(normalized_legs),
            "contracts_used": len(option_rows_by_contract),
            "trade_limit": config.max_trades,
            "trade_limit_hit": False,
        },
        "trades": flat_trades,
        "strategy_trade_groups": strategy_groups,
        "leg_results": leg_results,
        "selection": {
            "contracts": selections,
            "count": len(selections),
            "unique_contracts": len(contracts),
            "legs": normalized_legs,
            "last_contract": selections[-1] if selections else None,
            "window_end": signal_end.isoformat() if signal_end else None,
        },
        "diagnostics": {
            "signals_generated": len(events),
            "signals_prepared": len(flat_trades),
            "signals_executable": len(flat_trades),
            "option_bars_loaded": sum(len(x) for x in option_rows_by_contract.values()),
            "unique_contracts_loaded": len(option_rows_by_contract),
            "contracts_selected": len(selections),
            "leg_count": len(normalized_legs),
            "leg_transactions": len(flat_trades),
            "strategy_trade_groups": len(strategy_groups),
            "signals_skipped": len(skipped),
            "skipped_by_reason": dict(Counter(item.split(":", 1)[0] for item in skipped)),
            "multi_leg": True,
        },
        "warnings": skipped,
        "no_lookahead": True,
        "used_actual_option_prices": True,
        "data_source": "Upstox",
        "synthetic_prices": False,
    }


def run_strategy_option_backtest(
    underlying_rows: list[dict],
    *,
    strategy_name: str,
    preferred_strategy: str,
    strike_reference: float,
    expiry: str | None = None,
    strike_mode: str = "ATM",
    strike_offset: int = 0,
    stop_pct: float = 0.15,
    target_rr: float = 1.5,
    config: OptionsBacktestConfig | None = None,
    loader: UpstoxHistoricalOptionLoader | None = None,
    signal_start: datetime | str | None = None,
    signal_end: datetime | str | None = None,
    legs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    underlying = normalize_rows(underlying_rows)
    if len(underlying) < 15:
        raise ValueError("UNDERLYING_HISTORY_TOO_SHORT")

    start_dt = normalize_datetime(signal_start)
    end_dt = normalize_datetime(signal_end)

    cfg = config or OptionsBacktestConfig()
    upstox = loader or UpstoxHistoricalOptionLoader()

    if legs:
        events, signal_diag = _strategy_signals(
            underlying,
            preferred_strategy=preferred_strategy,
            signal_start=start_dt,
            signal_end=end_dt,
        )
        if not events:
            return {
                "strategy": strategy_name,
                "mode": "HISTORICAL_MULTI_LEG_OPTIONS",
                "metrics": {
                    "initial_capital": cfg.initial_capital,
                    "final_equity": cfg.initial_capital,
                    "net_profit": 0.0,
                    "return_pct": 0.0,
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "win_rate_pct": 0.0,
                    "profit_factor": None,
                    "max_drawdown": 0.0,
                    "max_drawdown_pct": 0.0,
                    "strategy_legs": len(legs),
                },
                "trades": [],
                "selection": None,
                "diagnostics": signal_diag | {"multi_leg": True},
                "warnings": ["NO_STRATEGY_SIGNALS_IN_WINDOW"],
                "data_source": "Upstox",
                "used_actual_option_prices": True,
                "synthetic_prices": False,
            }
        return _run_multi_leg_backtest(
            underlying=underlying,
            events=events,
            legs=legs,
            loader=upstox,
            config=cfg,
            strategy_name=strategy_name,
            strike_reference=float(strike_reference),
            stop_pct=stop_pct,
            target_rr=target_rr,
            signal_end=end_dt,
        )

    # IMPORTANT: Do not generate strategy signals before entering the cache path.
    # Previously every robustness scenario regenerated signals across all 4,500+
    # candles even when the historical market preparation was already cached.
    # That made multi-month runs appear hung. The cached preparation now owns the
    # expensive signal/contract/bar work and subsequent scenarios reuse it.
    upstox = loader or UpstoxHistoricalOptionLoader()
    if isinstance(upstox, UpstoxHistoricalOptionLoader):
        rows_json = _cache_rows_payload(underlying)
        prepared = _prepare_option_market_cached(
            rows_json,
            preferred_strategy,
            float(strike_reference),
            expiry,
            strike_mode,
            int(strike_offset),
            start_dt.isoformat() if start_dt else None,
            end_dt.isoformat() if end_dt else None,
            upstox.access_token,
            upstox.underlying_key,
        )
    else:
        prepared = _prepare_option_market(
            underlying,
            preferred_strategy=preferred_strategy,
            strike_reference=float(strike_reference),
            expiry=expiry,
            strike_mode=strike_mode,
            strike_offset=int(strike_offset),
            signal_start=start_dt,
            signal_end=end_dt,
            upstox=upstox,
        )

    signal_diag = dict(prepared["signal_diag"])
    if not prepared.get("events"):
        return {
            "strategy": strategy_name,
            "mode": "HISTORICAL_OPTIONS",
            "metrics": {
                "initial_capital": cfg.initial_capital,
                "final_equity": cfg.initial_capital,
                "net_profit": 0.0,
                "return_pct": 0.0,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate_pct": 0.0,
                "profit_factor": None,
                "max_drawdown": 0.0,
                "max_drawdown_pct": 0.0,
                "signals_evaluated": signal_diag["signals_evaluated"],
                "signals_generated": 0,
                "contracts_used": 0,
            },
            "trades": [],
            "warnings": ["NO_STRATEGY_SIGNALS_IN_WINDOW"],
            "selection": None,
            "diagnostics": signal_diag,
            "data_source": "Upstox",
            "used_actual_option_prices": True,
            "synthetic_prices": False,
        }

    selections = list(prepared["selections"])
    skipped = list(prepared["skipped"])
    option_rows = list(prepared["option_rows"])
    prepared_events = list(prepared["prepared_events"])

    if not prepared.get("events"):
        cfg = config or OptionsBacktestConfig()
        return {
            "strategy": strategy_name,
            "mode": "HISTORICAL_OPTIONS",
            "metrics": {
                "initial_capital": cfg.initial_capital,
                "final_equity": cfg.initial_capital,
                "net_profit": 0.0,
                "return_pct": 0.0,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate_pct": 0.0,
                "profit_factor": None,
                "max_drawdown": 0.0,
                "max_drawdown_pct": 0.0,
                "signals_evaluated": signal_diag["signals_evaluated"],
                "signals_generated": 0,
                "contracts_used": 0,
            },
            "trades": [],
            "warnings": ["NO_STRATEGY_SIGNALS_IN_WINDOW"],
            "selection": None,
            "diagnostics": signal_diag,
            "data_source": "Upstox",
            "used_actual_option_prices": True,
            "synthetic_prices": False,
        }

    cfg = config or OptionsBacktestConfig()

    # Build the execution events locally from cached market preparation.
    contracts_by_key = {
        item["instrument_key"]: item
        for item in selections
    }
    scheduled_signals: dict[datetime, list[dict[str, Any]]] = {}

    for prepared_event in prepared_events:
        decision_timestamp = normalize_datetime(prepared_event["decision_timestamp"])
        if decision_timestamp is None:
            continue

        contract_key = prepared_event["contract_key"]
        contract_meta = contracts_by_key.get(contract_key)
        if contract_meta is None:
            continue

        quantity_lots = max(1, int(cfg.quantity))
        lot_size = int(contract_meta["lot_size"])
        quantity_units = quantity_lots * lot_size

        scheduled_signals.setdefault(decision_timestamp, []).append(
            {
                "action": "BUY",
                "contract_key": contract_key,
                "stop_pct": float(stop_pct),
                "target_rr": float(target_rr),
                "quantity": quantity_units,
                "quantity_lots": quantity_lots,
                "lot_size": lot_size,
                "strategy": strategy_name,
                "direction": prepared_event["direction"],
                "strategy_signal_time": prepared_event.get("strategy_signal_time"),
            }
        )

    collision_count = sum(
        max(0, len(items) - 1)
        for items in scheduled_signals.values()
    )
    collision_timestamps = sum(
        1 for items in scheduled_signals.values() if len(items) > 1
    )

    result = HistoricalOptionsBacktestEngine().run(
        option_rows,
        lambda _context: None,
        strategy_name=strategy_name,
        config=cfg,
        scheduled_signals=scheduled_signals,
    )

    payload = _as_result_payload(result)
    payload["selection"] = {
        "contracts": selections,
        "count": len(selections),
        "last_contract": selections[-1] if selections else None,
        "window_end": end_dt.isoformat() if end_dt else None,
    }
    payload["diagnostics"] = {
        **signal_diag,
        "contracts_resolved": len(selections) + sum(
            1 for item in skipped if item.startswith("SIGNAL_SKIP:")
        ),
        "contracts_selected": len(selections),
        "signals_prepared": len(prepared_events),
        "signals_scheduled": sum(len(items) for items in scheduled_signals.values()),
        "signals_executable": sum(len(items) for items in scheduled_signals.values()),
        "unique_decision_timestamps": len(scheduled_signals),
        "decision_timestamp_collisions": collision_count,
        "timestamps_with_collisions": collision_timestamps,
        "signals_skipped": len(skipped),
        "option_bars_loaded": len(option_rows),
        "unique_contracts_loaded": len(
            {row.contract_key for row in option_rows}
        ),
        "skipped_by_reason": dict(
            Counter(item.split(":", 1)[0] for item in skipped)
        ),
        "preparation_cache": strategy_option_cache_info(),
        "engine_metrics": payload.get("metrics", {}),
    }
    payload["warnings"] = list(payload.get("warnings") or []) + skipped
    payload["data_source"] = "Upstox"
    payload["used_actual_option_prices"] = True
    payload["synthetic_prices"] = False
    return payload