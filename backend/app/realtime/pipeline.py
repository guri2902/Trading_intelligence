from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from ..agents.models import AgentInput
from ..agents.orchestrator import AgentOrchestrator
from ..api.phase17 import SignalRequest, signal as phase17_signal
from ..db.models import Instrument
from ..db.session import SessionLocal
from ..features.service import FeatureService
from ..options.engine import OptionsEngine
from ..options.models import OptionContract, OptionQuoteState
from ..providers.registry import build_registry
from ..risk.engine import RiskEngine
from ..risk.models import AccountRiskContext
from ..risk_config.service import RiskConfigService
from ..signals.models import SignalDecision
from ..storage.ingestion import (
    ingest_option_chain,
    ingest_provider_candles,
)
from ..structure.service import StructureService
from ..strategies.engine import StrategyEngine
from ..strategies.models import StrategyContext

logger = logging.getLogger(__name__)

IST = __import__("zoneinfo").ZoneInfo("Asia/Kolkata")

NIFTY_KEY = "NSE_INDEX|Nifty 50"
NIFTY_SYMBOL = "NIFTY"

DB_URL = os.getenv("DATABASE_URL", "sqlite:///./trading_intelligence.db")

engine = create_engine(DB_URL)

feature_service = FeatureService()
structure_service = StructureService()
options_engine = OptionsEngine()
strategy_engine = StrategyEngine()
risk_engine = RiskEngine()

providers = build_registry()

_pipeline_task: asyncio.Task | None = None
_pipeline_running = False
_last_result: dict[str, Any] | None = None
_last_error: str | None = None
_cycle_count = 0
_pipeline_interval_seconds = 30
_history: list[dict[str, Any]] = []


def _now_ist() -> datetime:
    return datetime.now(IST)

def _as_ist_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        raw = value.strip()

        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"

        dt = datetime.fromisoformat(raw)
    else:
        raise TypeError(f"Unsupported timestamp type: {type(value).__name__}")

    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)

    return dt.astimezone(IST)


def _market_open() -> bool:
    now = _now_ist().time()
    return time(9, 15) <= now < time(15, 30)


def _as_json(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _get_nifty_instrument(db: Session) -> Instrument:
    instrument = db.query(Instrument).filter(
        Instrument.segment == "NSE_INDEX",
        Instrument.trading_symbol == NIFTY_SYMBOL,
    ).first()

    if instrument is None:
        raise RuntimeError("NIFTY instrument not found in instrument master")

    return instrument


def _load_latest_candles(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT
                c.timestamp,
                c.open,
                c.high,
                c.low,
                c.close,
                c.volume
            FROM candles c
            JOIN instruments i
              ON i.id = c.instrument_id
            WHERE i.segment = 'NSE_INDEX'
              AND i.trading_symbol = 'NIFTY'
              AND c.timeframe = 'minutes:5'
              AND c.source = 'upstox'
            ORDER BY c.timestamp DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).fetchall()

    rows = list(reversed(rows))

    return [
        {
            "timestamp": _as_ist_datetime(row.timestamp),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume) if row.volume is not None else None,
        }
        for row in rows
    ]


def _load_latest_option_quotes(
    db: Session,
) -> tuple[datetime | None, list[OptionQuoteState]]:
    latest = db.execute(
        text(
            """
            SELECT MAX(m.timestamp)
            FROM market_snapshots m
            JOIN instruments i
              ON i.id = m.instrument_id
            WHERE i.underlying_symbol = 'NIFTY'
              AND i.option_type IN ('CE', 'PE')
              AND m.source = 'upstox'
              AND time(m.timestamp) >= '09:15:00'
              AND time(m.timestamp) < '15:30:00'
            """
        )
    ).scalar_one()

    if latest is None:
        return None, []

    rows = db.execute(
        text(
            """
            SELECT
                m.timestamp,
                m.underlying_ltp,
                m.ltp,
                m.bid,
                m.ask,
                m.bid_qty,
                m.ask_qty,
                m.volume,
                m.open_interest,
                m.change_in_oi,
                m.iv,
                m.delta,
                m.gamma,
                m.theta,
                m.vega,
                m.rho,
                i.instrument_key,
                i.underlying_key,
                i.underlying_symbol,
                i.expiry_date,
                i.strike,
                i.option_type,
                i.lot_size,
                i.tick_size
            FROM market_snapshots m
            JOIN instruments i
              ON i.id = m.instrument_id
            WHERE i.underlying_symbol = 'NIFTY'
              AND i.option_type IN ('CE', 'PE')
              AND m.source = 'upstox'
              AND m.timestamp = :timestamp
            ORDER BY i.strike, i.option_type
            """
        )
    , {"timestamp": latest}).fetchall()

    quotes: list[OptionQuoteState] = []

    for row in rows:
        previous_oi = None

        if row.open_interest is not None and row.change_in_oi is not None:
            previous_oi = (
                float(row.open_interest)
                - float(row.change_in_oi)
            )

        contract = OptionContract(
            instrument_key=row.instrument_key,
            underlying_key=row.underlying_key or NIFTY_KEY,
            underlying_symbol=row.underlying_symbol or NIFTY_SYMBOL,
            expiry=row.expiry_date,
            strike=float(row.strike),
            option_type=row.option_type,
            lot_size=row.lot_size,
            tick_size=(
                float(row.tick_size)
                if row.tick_size is not None
                else None
            ),
        )

        quotes.append(
            OptionQuoteState(
                contract=contract,
                timestamp=row.timestamp,
                underlying_spot=(
                    float(row.underlying_ltp)
                    if row.underlying_ltp is not None
                    else None
                ),
                ltp=float(row.ltp) if row.ltp is not None else None,
                bid=float(row.bid) if row.bid is not None else None,
                ask=float(row.ask) if row.ask is not None else None,
                bid_qty=row.bid_qty,
                ask_qty=row.ask_qty,
                volume=float(row.volume) if row.volume is not None else None,
                open_interest=(
                    float(row.open_interest)
                    if row.open_interest is not None
                    else None
                ),
                previous_oi=previous_oi,
                iv=float(row.iv) if row.iv is not None else None,
                delta=float(row.delta) if row.delta is not None else None,
                gamma=float(row.gamma) if row.gamma is not None else None,
                theta=float(row.theta) if row.theta is not None else None,
                vega=float(row.vega) if row.vega is not None else None,
                rho=float(row.rho) if row.rho is not None else None,
            )
        )

    latest = _as_ist_datetime(latest)

    return latest, quotes


risk_config_service = RiskConfigService()


def _account_context(option_timestamp: datetime) -> AccountRiskContext:
    cfg = risk_config_service.get()

    # User-facing controls remain cash/lot based. The existing RiskEngine
    # still consumes risk_per_trade_pct, so convert the cash budget internally.
    risk_per_trade_pct = (
        (cfg.per_trade_risk / cfg.capital) * 100.0
        if cfg.capital > 0
        else 0.0
    )

    return AccountRiskContext(
        equity=cfg.capital,
        realized_pnl_today=float(
            os.getenv("RISK_REALIZED_PNL", "0")
        ),
        open_risk=float(os.getenv("RISK_OPEN_RISK", "0")),
        open_positions=int(os.getenv("RISK_OPEN_POSITIONS", "0")),
        trades_today=int(os.getenv("RISK_TRADES_TODAY", "0")),
        peak_equity=float(
            os.getenv("RISK_PEAK_EQUITY", str(cfg.capital))
        ),
        risk_per_trade_pct=risk_per_trade_pct,
        max_daily_loss=cfg.daily_risk_budget,
        daily_profit_lock=float(
            os.getenv("RISK_DAILY_PROFIT_LOCK", "0")
        ),
        max_concurrent_risk=cfg.max_concurrent_risk,
        max_trades_per_day=cfg.max_trades_per_day,
        max_open_positions=cfg.max_open_positions,
        max_drawdown_pct=cfg.max_drawdown_pct,
        square_off_time=cfg.square_off_time,
        market_timestamp=option_timestamp,
        enabled=True,
    )


def run_cycle() -> dict[str, Any]:
    global _last_result

    if not _market_open():
        return {
            "status": "WAITING",
            "reason": "MARKET_SESSION_CLOSED",
            "timestamp": _now_ist().isoformat(),
        }

    provider = providers.get("upstox")

    if provider is None:
        raise RuntimeError("Upstox provider is not available")

    today = _now_ist().date()

    with SessionLocal() as db:
        # 1. Refresh latest 5-minute NIFTY candles.
        candles = provider.candles(
            NIFTY_KEY,
            "minutes",
            5,
            today,
            today,
        )

        candle_result = ingest_provider_candles(
            db,
            instrument=_get_nifty_instrument(db),
            timeframe="minutes:5",
            candles=candles,
            expected_interval_minutes=5,
            source="upstox",
        )

        # 2. Refresh current option chain.
        option_snapshot = provider.option_chain(
            NIFTY_KEY,
            None,
        )

        instruments = db.query(Instrument).filter(
            Instrument.underlying_symbol == NIFTY_SYMBOL,
            Instrument.option_type.in_(["CE", "PE"]),
        ).all()

        lookup = {
            (
                instrument.expiry_date,
                float(instrument.strike),
                instrument.option_type,
            ): instrument
            for instrument in instruments
            if instrument.expiry_date is not None
            and instrument.strike is not None
            and instrument.option_type is not None
        }

        option_result = ingest_option_chain(
            db,
            snapshot=option_snapshot,
            instrument_lookup=lookup,
            source="upstox",
        )

        db.commit()

        # 3. Read synchronized persisted data.
        latest_candles = _load_latest_candles(db, 100)

        option_timestamp, option_quotes = _load_latest_option_quotes(db)

        if len(latest_candles) < 7:
            raise RuntimeError(
                f"Insufficient NIFTY candles: {len(latest_candles)}"
            )

        if not option_quotes or option_timestamp is None:
            raise RuntimeError("No usable option snapshot available")

        # Never perform the historical-test spot normalization here.
        latest_candle = latest_candles[-1]

        # 4. Phase 6.
        features = feature_service.calculate(
            latest_candles,
            session_ids=None,
        )

        # 5. Phase 7.
        structure = structure_service.analyze(latest_candles)

        # 6. Phase 8.
        options = options_engine.analyze(
            option_quotes,
            now=option_timestamp,
        )

        # 7. Phase 9.
        context = StrategyContext(
            timestamp=option_timestamp,
            candles=latest_candles,
            features=features,
            structure=structure,
            options=options,
            regime=structure.get("regime"),
        )

        strategies = strategy_engine.evaluate(context)

        options_payload = _as_json(options)

        option_spots = sorted(
            {
                float(q.underlying_spot)
                for q in option_quotes
                if q.underlying_spot is not None
            }
        )

        options_payload["snapshot_timestamp"] = option_timestamp.isoformat()
        options_payload["underlying_spot"] = (
            option_spots[0] if option_spots else None
        )

        # 8. Existing AgentInput contract.
        agent_input = AgentInput(
            timestamp=option_timestamp,
            market={
                "symbol": NIFTY_SYMBOL,
                "spot": latest_candle["close"],
                "timestamp": latest_candle["timestamp"].isoformat(),
                "data_quality_status": "PASS",
                "stale": False,
            },
            features=_as_json(features),
            structure=_as_json(structure),
            options=options_payload,
            strategies=_as_json(strategies),
            ml={},
            fundamentals={},
            sentiment={},
            news={},
            risk={},
        )

        # 9. Existing Phase 17.
        try:
            phase17_result = phase17_signal(
                SignalRequest(
                    data=agent_input,
                    use_llm=os.getenv("REALTIME_USE_LLM", "true").lower() == "true",
                    provider=os.getenv("LLM_PROVIDER"),
                    model=os.getenv("LLM_MODEL"),
                )
            )
        except Exception as exc:
            logger.warning(
                "Realtime LLM unavailable; falling back to deterministic Phase 17: %s",
                exc,
            )

            phase17_result = phase17_signal(
                SignalRequest(
                    data=agent_input,
                    use_llm=False,
                )
            )


        # 10. Existing deterministic risk gate.
        signal = SignalDecision.model_validate(phase17_result)

        account = _account_context(option_timestamp)

        risk = risk_engine.evaluate(
            signal,
            account,
        )

        live_options = {
            "status": options.get("status"),
            "expiry": options.get("expiry"),
            "atm_strike": options.get("atm_strike"),
            "underlying_spot": options_payload.get("underlying_spot"),
            "best_ce": options.get("best_ce"),
            "best_pe": options.get("best_pe"),
            "debate": options.get("debate"),
        }

        live_strategies = {
            "regime": getattr(strategies, "regime", None),
            "triggered_count": getattr(strategies, "triggered_count", 0),
            "best_setup": (
                _as_json(strategies.best_setup)
                if getattr(strategies, "best_setup", None)
                else None
            ),
            "setups": _as_json(getattr(strategies, "setups", [])),
        }

        result = {
            "status": "UPDATED",
            "timestamp": option_timestamp.isoformat(),
            "candle_timestamp": latest_candle["timestamp"].isoformat(),

            "market": {
                "symbol": NIFTY_SYMBOL,
                "spot": latest_candle["close"],
                "timestamp": latest_candle["timestamp"].isoformat(),
            },

            "features": _as_json(features),
            "structure": _as_json(structure),
            "options": live_options,
            "strategies": live_strategies,

            "signal": phase17_result,
            "risk": risk.model_dump(mode="json"),

            "ingestion": {
                "candles": candle_result,
                "options": option_result,
            },
        }

        _last_result = result

        _history.insert(
            0,
            {
                "timestamp": option_timestamp.isoformat(),
                "action": phase17_result.get("action"),
                "direction": phase17_result.get("direction"),
                "confidence": phase17_result.get("confidence"),
                "score": phase17_result.get("score"),
                "final_action": risk.final_action,
                "approved": risk.approved,
            },
        )

        del _history[30:]

        return result


async def _loop(interval_seconds: int) -> None:
    global _pipeline_running, _last_error, _cycle_count

    _pipeline_running = True

    try:
        while _pipeline_running:
            try:
                result = await asyncio.to_thread(run_cycle)

                _last_error = None
                _cycle_count += 1

                logger.info(
                    "Realtime cycle %s: %s action=%s final_action=%s",
                    _cycle_count,
                    result.get("status"),
                    result.get("signal", {}).get("action"),
                    result.get("risk", {}).get("final_action"),
                )

            except asyncio.CancelledError:
                raise

            except Exception as exc:
                _last_error = str(exc)
                logger.exception("Realtime pipeline cycle failed")

            await asyncio.sleep(interval_seconds)

    finally:
        _pipeline_running = False


def start(interval_seconds: int = 30) -> dict[str, Any]:
    global _pipeline_task, _pipeline_running, _pipeline_interval_seconds

    if _pipeline_running:
        return status()

    _pipeline_interval_seconds = max(5, interval_seconds)

    _pipeline_task = asyncio.create_task(
        _loop(_pipeline_interval_seconds),
        name=f"realtime-pipeline-{_pipeline_interval_seconds}s",
    )

    return status()


async def stop() -> dict[str, Any]:
    global _pipeline_task, _pipeline_running

    _pipeline_running = False

    if _pipeline_task is not None:
        _pipeline_task.cancel()

        try:
            await _pipeline_task
        except asyncio.CancelledError:
            pass

        _pipeline_task = None

    return status()


def status() -> dict[str, Any]:
    return {
        "running": _pipeline_running,
        "cycle_count": _cycle_count,
        "last_error": _last_error,
        "last_result": _last_result,
        "history": _history,
        "interval_seconds": _pipeline_interval_seconds,
    }