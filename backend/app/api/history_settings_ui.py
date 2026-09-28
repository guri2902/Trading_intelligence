from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import DataQualityEvent, PaperTrade
from ..db.session import get_db
from ..realtime import realtime_pipeline
from ..risk_config.service import RiskConfigService

router = APIRouter(prefix="/ui", tags=["ui-history-settings"])
risk_config_service = RiskConfigService()


def _f(v: Any):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _trade(row: PaperTrade) -> dict[str, Any]:
    pnl = _f(row.realized_pnl) if row.status == "CLOSED" else _f(row.unrealized_pnl)
    if row.status == "CLOSED":
        pnl = (pnl or 0) - (_f(row.total_costs) or 0)

    return {
        "id": row.id,
        "position_id": row.position_id,
        "account_id": row.account_id,
        "timestamp": row.closed_at or row.opened_at,
        "opened_at": row.opened_at,
        "closed_at": row.closed_at,
        "symbol": row.symbol,
        "option_type": row.option_type,
        "strike": _f(row.strike),
        "expiry": row.expiry,
        "side": "BUY",
        "quantity": row.filled_quantity or row.quantity,
        "requested_quantity": row.requested_quantity,
        "price": _f(row.exit_price if row.status == "CLOSED" and row.exit_price is not None else row.entry_price),
        "entry_price": _f(row.entry_price),
        "exit_price": _f(row.exit_price),
        "pnl": pnl,
        "status": row.status,
        "source": row.source,
        "strategy": row.signal_id,
        "close_reason": row.close_reason,
        "costs": _f(row.total_costs),
        "partial_fill": bool(row.partial_fill),
    }


@router.get("/history")
def history(
    account_id: str = Query("default"),
    side: str = Query("ALL"),
    status: str = Query("ALL"),
    source: str = Query("ALL"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    stmt = (
        select(PaperTrade)
        .where(
            PaperTrade.account_id == account_id,
            PaperTrade.position_id != "__ACCOUNT__",
        )
        .order_by(PaperTrade.opened_at.desc())
        .limit(limit)
    )
    rows = list(db.scalars(stmt).all())

    if status.upper() != "ALL":
        rows = [r for r in rows if r.status.upper() == status.upper()]

    if side.upper() != "ALL" and side.upper() != "BUY":
        rows = []

    if source.upper() != "ALL":
        rows = [r for r in rows if str(r.source or "").upper() == source.upper()]

    if search:
        needle = search.lower().strip()
        rows = [
            r for r in rows
            if needle in str(r.symbol or "").lower()
            or needle in str(r.signal_id or "").lower()
            or needle in str(r.position_id or "").lower()
        ]

    def day(value: datetime | None):
        return value.date().isoformat() if value else None

    if date_from:
        rows = [r for r in rows if (day(r.closed_at or r.opened_at) or "") >= date_from]
    if date_to:
        rows = [r for r in rows if (day(r.closed_at or r.opened_at) or "") <= date_to]

    records = [_trade(r) for r in rows]
    pnl = sum((item["pnl"] or 0) for item in records)
    wins = sum(1 for item in records if (item["pnl"] or 0) > 0)
    losses = sum(1 for item in records if (item["pnl"] or 0) < 0)

    return {
        "status": "LIVE",
        "records": records,
        "count": len(records),
        "summary": {
            "pnl": round(pnl, 2),
            "wins": wins,
            "losses": losses,
        },
        "source": "paper_trades",
    }


@router.get("/system-status")
def system_status():
    pipeline = realtime_pipeline.status()
    risk = risk_config_service.get()
    return {
        "status": "OK",
        "backend": "CONNECTED",
        "realtime_pipeline": {
            "running": bool(pipeline.get("running")),
            "cycle_count": pipeline.get("cycle_count", 0),
            "last_error": pipeline.get("last_error"),
            "last_timestamp": (pipeline.get("last_result") or {}).get("timestamp"),
        },
        "risk_config": {
            "loaded": True,
            "version": getattr(risk, "version", None),
        },
        "paper": {
            "mode": "SIMULATION",
            "live_execution": False,
        },
        "market_data_boundary": {
            "browser_direct_upstox": False,
            "backend_data_layer": True,
        },
    }


@router.get("/data-quality")
def data_quality(
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(DataQualityEvent)
        .order_by(DataQualityEvent.event_time.desc())
        .limit(limit)
    ).all()

    return {
        "status": "LIVE",
        "events": [
            {
                "id": row.id,
                "source": row.source,
                "instrument_key": row.instrument_key,
                "event_type": row.event_type,
                "severity": row.severity,
                "event_time": row.event_time,
                "details": row.details,
                "resolved": row.resolved,
            }
            for row in rows
        ],
    }
