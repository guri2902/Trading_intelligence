from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import select

from ..db.models import PaperTrade
from ..db.session import SessionLocal

from ..features.service import FeatureService
from ..structure.service import StructureService
from ..options.engine import OptionsEngine
from ..agents.models import AgentInput
from ..agents.orchestrator import AgentOrchestrator
from ..realtime import realtime_pipeline
from ..risk_config.service import RiskConfigService
from ..risk_config.models import RiskConfig

router = APIRouter(prefix="/ui", tags=["ui-research"])

risk_config_service = RiskConfigService()
agent_orchestrator = AgentOrchestrator()
feature_service = FeatureService()
structure_service = StructureService()
options_engine = OptionsEngine()

def _json(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _signal_payload(last: dict[str, Any]) -> dict[str, Any]:
    return last.get("signal") or {}


def _agent_input(last: dict[str, Any]) -> AgentInput:
    return AgentInput(
        timestamp=last.get("timestamp") or "",
        market=last.get("market") or {},
        features=last.get("features") or {},
        structure=last.get("structure") or {},
        options=last.get("options") or {},
        strategies=last.get("strategies") or {},
        ml={},
        fundamentals={},
        sentiment={},
        news={},
        risk=last.get("risk") or {},
    )


def _empty(reason: str) -> dict[str, Any]:
    return {
        "status": "WAIT",
        "available": False,
        "reason": reason,
        "timestamp": None,
    }


@router.get("/analysis")
def analysis():
    pipeline = realtime_pipeline.status()
    last = pipeline.get("last_result")

    # Normal live-market path: use the completed realtime cycle.
    if last:
        features = last.get("features") or {}
        structure = last.get("structure") or {}
        options = last.get("options") or {}
        strategies = last.get("strategies") or {}
        signal = _signal_payload(last)
        risk = last.get("risk") or {}

        return {
            "status": "LIVE",
            "available": True,
            "live": True,
            "market_open": True,
            "timestamp": last.get("timestamp"),
            "candle_timestamp": last.get("candle_timestamp"),
            "market": last.get("market") or {},
            "technical": {
                "rsi14": features.get("rsi14", features.get("rsi")),
                "ema9": features.get("ema9"),
                "ema20": features.get("ema20"),
                "ema50": features.get("ema50"),
                "atr14": features.get("atr14", features.get("atr")),
                "vwap": features.get("vwap"),
                "relative_volume": features.get("relative_volume"),
                "momentum": features.get("momentum"),
                "volatility": features.get("volatility"),
            },
            "structure": {
                "trend": structure.get("trend"),
                "regime": structure.get("regime"),
                "bos": structure.get("bos"),
                "choch": structure.get("choch"),
                "support": structure.get("support"),
                "resistance": structure.get("resistance"),
                "pullback": structure.get("pullback"),
                "retest": structure.get("retest"),
                "rejection": structure.get("rejection"),
            },
            "options": {
                "status": options.get("status"),
                "underlying_spot": options.get("underlying_spot"),
                "atm_strike": options.get("atm_strike"),
                "expiry": options.get("expiry"),
                "best_ce": options.get("best_ce"),
                "best_pe": options.get("best_pe"),
            },
            "strategy": {
                "regime": strategies.get("regime"),
                "triggered_count": strategies.get("triggered_count"),
                "best_setup": strategies.get("best_setup"),
                "setups": strategies.get("setups") or [],
            },
            "signal": signal,
            "risk": risk,
            "external": {
                "sentiment": None,
                "news": None,
                "fundamentals": None,
                "status": "NOT_CONNECTED",
            },
            "pipeline_running": bool(pipeline.get("running")),
            "last_error": pipeline.get("last_error"),
        }

    # Closed-market fallback:
    # show the latest persisted research inputs, but do NOT create a new
    # live signal/strategy/risk decision.
    try:
        from ..realtime.pipeline import _load_latest_candles, _load_latest_option_quotes
        from ..db.session import SessionLocal

        with SessionLocal() as db:
            candles = _load_latest_candles(db, 100)
            option_timestamp, option_quotes = _load_latest_option_quotes(db)

        if not candles:
            return {
                **_empty("No persisted NIFTY candles are available yet."),
                "market_open": False,
                "live": False,
                "pipeline_running": bool(pipeline.get("running")),
                "last_error": pipeline.get("last_error"),
            }

        features = feature_service.calculate(candles, session_ids=None)
        structure = structure_service.analyze(candles)

        options = {}
        if option_quotes and option_timestamp is not None:
            options = options_engine.analyze(
                option_quotes,
                now=option_timestamp,
            )

        return {
            "status": "LATEST",
            "available": True,
            "live": False,
            "market_open": False,
            "timestamp": (
                option_timestamp.isoformat()
                if option_timestamp
                else candles[-1]["timestamp"].isoformat()
            ),
            "candle_timestamp": candles[-1]["timestamp"].isoformat(),
            "market": {
                "symbol": "NIFTY",
                "spot": candles[-1]["close"],
                "timestamp": candles[-1]["timestamp"].isoformat(),
            },
            "technical": {
                "rsi14": features.get("rsi14", features.get("rsi")),
                "ema9": features.get("ema9"),
                "ema20": features.get("ema20"),
                "ema50": features.get("ema50"),
                "atr14": features.get("atr14", features.get("atr")),
                "vwap": features.get("vwap"),
                "relative_volume": features.get("relative_volume"),
                "momentum": features.get("momentum"),
                "volatility": features.get("volatility"),
            },
            "structure": {
                "trend": structure.get("trend"),
                "regime": structure.get("regime"),
                "bos": structure.get("bos"),
                "choch": structure.get("choch"),
                "support": structure.get("support"),
                "resistance": structure.get("resistance"),
                "pullback": structure.get("pullback"),
                "retest": structure.get("retest"),
                "rejection": structure.get("rejection"),
            },
            "options": {
                "status": options.get("status") if options else "LATEST",
                "underlying_spot": options.get("underlying_spot") if options else None,
                "atm_strike": options.get("atm_strike") if options else None,
                "expiry": options.get("expiry") if options else None,
                "best_ce": options.get("best_ce") if options else None,
                "best_pe": options.get("best_pe") if options else None,
            },
            "strategy": {
                "regime": None,
                "triggered_count": 0,
                "best_setup": None,
                "setups": [],
            },
            "signal": {},
            "risk": {
                "final_action": "NO_TRADE",
                "approved": False,
            },
            "external": {
                "sentiment": None,
                "news": None,
                "fundamentals": None,
                "status": "NOT_CONNECTED",
            },
            "pipeline_running": bool(pipeline.get("running")),
            "last_error": pipeline.get("last_error"),
            "message": (
                "Showing the latest persisted market research. "
                "No new live signal is generated while the market is closed."
            ),
        }

    except Exception as exc:
        return {
            **_empty(f"Latest research fallback unavailable: {exc}"),
            "market_open": False,
            "live": False,
            "pipeline_running": bool(pipeline.get("running")),
            "last_error": pipeline.get("last_error"),
        }


@router.get("/ai-analysis")
def ai_analysis():
    pipeline = realtime_pipeline.status()
    last = pipeline.get("last_result")

    # Live-market path: use the completed realtime cycle.
    if last:
        try:
            result = agent_orchestrator.run(_agent_input(last))
            deterministic_agents = [_json(agent) for agent in result.agents]
            debate = _json(result.debate)
            final_decision = _json(result.final_decision)
        except Exception as exc:
            return {
                "status": "ERROR",
                "available": False,
                "reason": str(exc),
                "timestamp": last.get("timestamp"),
                "pipeline_running": bool(pipeline.get("running")),
            }

        signal = _signal_payload(last)
        risk = last.get("risk") or {}

        return {
            "status": "LIVE",
            "available": True,
            "live": True,
            "timestamp": last.get("timestamp"),
            "market": last.get("market") or {},
            "signal": signal,
            "risk": risk,
            "agents": deterministic_agents,
            "debate": debate,
            "final_decision": final_decision,
            "policy": (
                "Deterministic data gates and risk gates remain authoritative. "
                "The agent layer is advisory."
            ),
            "pipeline_running": bool(pipeline.get("running")),
            "last_error": pipeline.get("last_error"),
        }

    # Closed-market fallback: rebuild advisory AI analysis from the latest
    # persisted research inputs. This must never become a new live trade signal.
    try:
        from ..realtime.pipeline import (
            _load_latest_candles,
            _load_latest_option_quotes,
        )
        from ..db.session import SessionLocal
        from ..features.service import FeatureService
        from ..structure.service import StructureService
        from ..options.engine import OptionsEngine

        feature_service = FeatureService()
        structure_service = StructureService()
        options_engine = OptionsEngine()

        with SessionLocal() as db:
            candles = _load_latest_candles(db, 100)
            option_timestamp, option_quotes = _load_latest_option_quotes(db)

        if not candles:
            return {
                **_empty("No persisted market research is available yet."),
                "live": False,
                "pipeline_running": bool(pipeline.get("running")),
                "last_error": pipeline.get("last_error"),
            }

        features = feature_service.calculate(
            candles,
            session_ids=None,
        )

        structure = structure_service.analyze(candles)

        options = {}
        if option_quotes and option_timestamp is not None:
            options = options_engine.analyze(
                option_quotes,
                now=option_timestamp,
            )

        latest = {
            "timestamp": (
                option_timestamp.isoformat()
                if option_timestamp
                else candles[-1]["timestamp"].isoformat()
            ),
            "market": {
                "symbol": "NIFTY",
                "spot": candles[-1]["close"],
                "timestamp": candles[-1]["timestamp"].isoformat(),
                "data_quality_status": "PASS",
                "stale": True,
            },
            "features": features,
            "structure": structure,
            "options": options,
            "strategies": {},
            "risk": {
                "final_action": "NO_TRADE",
                "approved": False,
            },
        }

        deterministic_agents = []
        debate = {}
        final_decision = {}

        return {
            "status": "LATEST",
            "available": True,
            "live": False,
            "timestamp": latest["timestamp"],
            "market": latest["market"],
            "signal": {},
            "risk": {
                "final_action": "NO_TRADE",
                "approved": False,
            },
            "agents": deterministic_agents,
            "debate": debate,
            "final_decision": final_decision,
            "policy": (
                "Latest persisted research is available, but no new AI trading decision "
                "is generated while the market is closed. The AI layer becomes active "
                "only when a completed live market cycle supplies current strategy and "
                "signal context. Risk gates remain authoritative."
            ),
            "pipeline_running": bool(pipeline.get("running")),
            "last_error": pipeline.get("last_error"),
            "message": (
                "Showing the latest persisted AI research because the "
                "market session is closed."
            ),
        }

    except Exception as exc:
        return {
            "status": "ERROR",
            "available": False,
            "live": False,
            "reason": f"Latest AI research fallback unavailable: {exc}",
            "pipeline_running": bool(pipeline.get("running")),
            "last_error": pipeline.get("last_error"),
        }


@router.get("/risk")
def risk():
    pipeline = realtime_pipeline.status()
    last = pipeline.get("last_result")
    config = risk_config_service.get().model_dump(mode="json")

    if not last:
        return {
            **_empty("No completed realtime pipeline cycle is available."),
            "config": config,
            "trading_allowed": False,
            "pipeline_running": bool(pipeline.get("running")),
            "last_error": pipeline.get("last_error"),
        }

    current = last.get("risk") or {}
    signal = _signal_payload(last)

    return {
        "status": "LIVE",
        "available": True,
        "timestamp": last.get("timestamp"),
        "decision": current.get("final_action"),
        "approved": bool(current.get("approved")),
        "trading_allowed": bool(current.get("approved")),
        "signal_action": current.get("signal_action", signal.get("action")),
        "reason_codes": (current.get("assessment") or {}).get("reason_codes", []),
        "risk_budget": (current.get("assessment") or {}).get("risk_budget"),
        "unit_risk": (current.get("assessment") or {}).get("unit_risk"),
        "estimated_trade_risk": (current.get("assessment") or {}).get("estimated_trade_risk"),
        "resulting_open_risk": (current.get("assessment") or {}).get("resulting_open_risk"),
        "remaining_daily_loss_capacity": (current.get("assessment") or {}).get("remaining_daily_loss_capacity"),
        "remaining_profit_lock_capacity": (current.get("assessment") or {}).get("remaining_profit_lock_capacity"),
        "quantity": (current.get("assessment") or {}).get("quantity"),
        "lot_size": (current.get("assessment") or {}).get("lot_size"),
        "trade_plan": current.get("trade_plan"),
        "config": config,
        "pipeline_running": bool(pipeline.get("running")),
        "last_error": pipeline.get("last_error"),
    }
@router.get("/risk/config")
def risk_config():
    config = risk_config_service.get()

    return {
        "status": "OK",
        "config": config.model_dump(mode="json"),
    }


@router.put("/risk/config")
def update_risk_config(config: RiskConfig):
    saved = risk_config_service.save(config)

    return {
        "status": "OK",
        "config": saved.model_dump(mode="json"),
    }

@router.get("/history")
def history(
    account_id: str = Query("default"),
    status: str = Query("ALL"),
    source: str = Query("ALL"),
    search: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    limit: int = Query(500, ge=1, le=500),
):
    with SessionLocal() as db:
        rows = db.scalars(
            select(PaperTrade)
            .where(
                PaperTrade.account_id == account_id,
                PaperTrade.position_id != "__ACCOUNT__",
            )
            .order_by(PaperTrade.opened_at.desc())
        ).all()

    status_filter = status.strip().upper()
    source_filter = source.strip()

    def event_timestamp(row: PaperTrade) -> datetime | None:
        return row.closed_at or row.opened_at

    filtered = []

    for row in rows:
        if status_filter != "ALL" and row.status.upper() != status_filter:
            continue

        if source_filter != "ALL" and str(row.source or "") != source_filter:
            continue

        text = " ".join(
            [
                str(row.symbol or ""),
                str(row.option_type or ""),
                str(row.strike or ""),
                str(row.expiry or ""),
                str(row.position_id or ""),
                str(row.source or ""),
                str(row.close_reason or ""),
            ]
        ).lower()

        if search and search.strip().lower() not in text:
            continue

        ts = event_timestamp(row)

        if date_from:
            try:
                from_date = datetime.fromisoformat(date_from).date()
                if ts is None or ts.date() < from_date:
                    continue
            except ValueError:
                pass

        if date_to:
            try:
                to_date = datetime.fromisoformat(date_to).date()
                if ts is None or ts.date() > to_date:
                    continue
            except ValueError:
                pass

        if row.status.upper() == "CLOSED":
            pnl = float(row.realized_pnl or 0) - float(row.total_costs or 0)
        else:
            pnl = float(row.unrealized_pnl or 0) - float(row.total_costs or 0)

        filtered.append(
            {
                "position_id": row.position_id,
                "account_id": row.account_id,
                "timestamp": ts,
                "opened_at": row.opened_at,
                "closed_at": row.closed_at,
                "symbol": row.symbol,
                "option_type": row.option_type,
                "strike": float(row.strike),
                "expiry": row.expiry,
                "quantity": row.quantity,
                "entry_price": float(row.entry_price),
                "mark_price": float(row.mark_price),
                "exit_price": (
                    float(row.exit_price)
                    if row.exit_price is not None
                    else None
                ),
                "pnl": round(pnl, 2),
                "realized_pnl": round(float(row.realized_pnl or 0), 2),
                "unrealized_pnl": round(float(row.unrealized_pnl or 0), 2),
                "total_costs": round(float(row.total_costs or 0), 2),
                "status": row.status,
                "source": row.source,
                "close_reason": row.close_reason,
                "signal_id": row.signal_id,
                "strategy": None,
            }
        )

        if len(filtered) >= limit:
            break

    closed = [row for row in filtered if row["status"].upper() == "CLOSED"]
    pnl_total = round(sum(float(row["pnl"]) for row in filtered), 2)
    wins = sum(1 for row in closed if float(row["pnl"]) > 0)
    losses = sum(1 for row in closed if float(row["pnl"]) < 0)

    return {
        "status": "OK",
        "account_id": account_id,
        "records": filtered,
        "summary": {
            "records": len(filtered),
            "wins": wins,
            "losses": losses,
            "pnl": pnl_total,
        },
    }