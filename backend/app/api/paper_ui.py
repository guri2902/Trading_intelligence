from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Instrument, MarketSnapshot, PaperTrade
from ..db.session import get_db
from ..paper.engine import PaperTradingEngine
from ..paper.models import PaperCloseRequest, PaperMarkRequest, PaperOrderRequest

router = APIRouter(prefix="/paper", tags=["paper-ui"])
engine = PaperTradingEngine()

DEFAULT_ACCOUNT_ID = "default"
DEFAULT_STARTING_EQUITY = 100_000.0


class AccountCreateRequest(BaseModel):
    account_id: str = DEFAULT_ACCOUNT_ID
    starting_equity: float = Field(default=DEFAULT_STARTING_EQUITY, gt=0)


class PaperOrderUIRequest(BaseModel):
    account_id: str = DEFAULT_ACCOUNT_ID
    symbol: str
    action: str
    option_type: str
    strike: float = Field(gt=0)
    expiry: str
    quantity: int = Field(gt=0)
    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    target_1: float | None = Field(default=None, gt=0)
    target_2: float | None = Field(default=None, gt=0)
    timestamp: datetime | None = None
    bid: float | None = Field(default=None, gt=0)
    ask: float | None = Field(default=None, gt=0)
    available_quantity: int | None = Field(default=None, ge=0)
    signal_id: str | None = None
    source: str = "paper_ui"


class MarkRequest(BaseModel):
    account_id: str = DEFAULT_ACCOUNT_ID
    position_id: str
    price: float = Field(gt=0)
    timestamp: datetime | None = None
    bid: float | None = Field(default=None, gt=0)
    ask: float | None = Field(default=None, gt=0)
    available_quantity: int | None = Field(default=None, ge=0)
    underlying_ltp: float | None = Field(default=None, gt=0)


class AutoMarkRequest(BaseModel):
    account_id: str = DEFAULT_ACCOUNT_ID


def _ts(value: datetime | None) -> datetime:
    return value or datetime.now(timezone.utc)


def _ensure_account(db: Session, account_id: str):
    try:
        return engine.account(db, account_id)
    except ValueError:
        return engine.ensure_account(db, account_id, DEFAULT_STARTING_EQUITY)


def _serialize_trade(row: PaperTrade) -> dict[str, Any]:
    return {
        "id": row.id,
        "position_id": row.position_id,
        "account_id": row.account_id,
        "symbol": row.symbol,
        "option_type": row.option_type,
        "strike": float(row.strike),
        "expiry": row.expiry,
        "quantity": row.quantity,
        "requested_quantity": row.requested_quantity,
        "filled_quantity": row.filled_quantity,
        "entry_price": float(row.entry_price),
        "mark_price": float(row.mark_price),
        "exit_price": float(row.exit_price) if row.exit_price is not None else None,
        "stop_loss": float(row.stop_loss) if row.stop_loss is not None else None,
        "target_1": float(row.target_1) if row.target_1 is not None else None,
        "target_2": float(row.target_2) if row.target_2 is not None else None,
        "realized_pnl": float(row.realized_pnl or 0),
        "unrealized_pnl": float(row.unrealized_pnl or 0),
        "status": row.status,
        "opened_at": row.opened_at,
        "closed_at": row.closed_at,
        "close_reason": row.close_reason,
        "signal_id": row.signal_id,
        "source": row.source,
        "entry_slippage": float(row.entry_slippage or 0),
        "exit_slippage": float(row.exit_slippage or 0),
        "entry_costs": float(row.entry_costs or 0),
        "exit_costs": float(row.exit_costs or 0),
        "total_costs": float(row.total_costs or 0),
        "partial_fill": bool(row.partial_fill or False),
        "latency_ms": int(row.latency_ms or 0),
    }


def _account_payload(db: Session, account_id: str) -> dict[str, Any]:
    account = _ensure_account(db, account_id)
    equity = account.starting_equity + account.realized_pnl + account.unrealized_pnl
    return {
        **account.model_dump(mode="json"),
        "equity": round(equity, 2),
        "starting_equity": round(account.starting_equity, 2),
        "live_execution": False,
        "mode": "SIMULATION",
    }


@router.get("/health")
def health():
    return {
        "status": "ok",
        "mode": "SIMULATION",
        "live_execution": False,
        "engine": "phase19+20",
    }


@router.post("/account")
def create_account(req: AccountCreateRequest, db: Session = Depends(get_db)):
    return engine.ensure_account(db, req.account_id, req.starting_equity).model_dump(mode="json") | {
        "equity": req.starting_equity,
        "live_execution": False,
        "mode": "SIMULATION",
    }


@router.get("/account")
def get_account(
    account_id: str = Query(DEFAULT_ACCOUNT_ID),
    db: Session = Depends(get_db),
):
    return _account_payload(db, account_id)


@router.get("/status")
def status(
    account_id: str = Query(DEFAULT_ACCOUNT_ID),
    db: Session = Depends(get_db),
):
    account = _account_payload(db, account_id)
    rows = db.scalars(
        select(PaperTrade)
        .where(PaperTrade.account_id == account_id, PaperTrade.position_id != "__ACCOUNT__")
        .order_by(PaperTrade.opened_at.desc())
    ).all()

    open_rows = [r for r in rows if r.status == "OPEN"]

    latest_mark = max(
        (
            r.closed_at or r.opened_at
            for r in rows
            if r.closed_at is not None or r.opened_at is not None
        ),
        default=None,
    )

    today = datetime.now(timezone.utc).date()
    today_realized = round(
        sum(
            float(r.realized_pnl or 0) - float(r.total_costs or 0)
            for r in rows
            if r.status == "CLOSED"
            and r.closed_at is not None
            and r.closed_at.astimezone(timezone.utc).date() == today
        ),
        2,
    )

    return {
        "status": "ok",
        "mode": "SIMULATION",
        "live_execution": False,
        "account": account,
        "open_positions": len(open_rows),
        "today_virtual_pnl": today_realized + account["unrealized_pnl"],
        "latest_event_at": latest_mark,
    }


@router.get("/positions")
def positions(
    account_id: str = Query(DEFAULT_ACCOUNT_ID),
    status_filter: str = Query("OPEN", alias="status"),
    db: Session = Depends(get_db),
):
    query = (
        select(PaperTrade)
        .where(PaperTrade.account_id == account_id, PaperTrade.position_id != "__ACCOUNT__")
        .order_by(PaperTrade.opened_at.desc())
    )
    if status_filter.upper() != "ALL":
        query = query.where(PaperTrade.status == status_filter.upper())

    rows = db.scalars(query).all()
    return {"positions": [_serialize_trade(row) for row in rows]}


@router.get("/fills")
def fills(
    account_id: str = Query(DEFAULT_ACCOUNT_ID),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(PaperTrade)
        .where(PaperTrade.account_id == account_id, PaperTrade.position_id != "__ACCOUNT__")
        .order_by(PaperTrade.opened_at.desc())
        .limit(limit)
    ).all()

    events: list[dict[str, Any]] = []
    for row in rows:
        events.append(
            {
                "timestamp": row.opened_at,
                "position_id": row.position_id,
                "symbol": row.symbol,
                "side": "BUY",
                "action": "BUY",
                "quantity": row.filled_quantity or row.quantity,
                "price": float(row.entry_price),
                "status": "FILLED",
                "pnl": None,
                "costs": float(row.entry_costs or 0),
                "source": row.source,
            }
        )
        if row.closed_at is not None and row.exit_price is not None:
            events.append(
                {
                    "timestamp": row.closed_at,
                    "position_id": row.position_id,
                    "symbol": row.symbol,
                    "side": "SELL",
                    "action": "SELL",
                    "quantity": row.quantity,
                    "price": float(row.exit_price),
                    "status": "CLOSED",
                    "pnl": float(row.realized_pnl or 0) - float(row.total_costs or 0),
                    "costs": float(row.exit_costs or 0),
                    "source": row.source,
                    "close_reason": row.close_reason,
                }
            )

    events.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"fills": events[:limit]}


@router.get("/equity-curve")
def equity_curve(
    account_id: str = Query(DEFAULT_ACCOUNT_ID),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(PaperTrade)
        .where(PaperTrade.account_id == account_id, PaperTrade.position_id != "__ACCOUNT__")
        .order_by(PaperTrade.opened_at.asc())
    ).all()

    account_row = db.scalar(
        select(PaperTrade).where(
            PaperTrade.account_id == account_id,
            PaperTrade.position_id == "__ACCOUNT__",
        )
    )
    if account_row is None:
        account_row = engine.ensure_account(db, account_id, DEFAULT_STARTING_EQUITY)

    equity = float(account_row.entry_price)
    points: list[dict[str, Any]] = [
        {"timestamp": account_row.opened_at, "equity": round(equity, 2), "event": "ACCOUNT"}
    ]

    for row in rows:
        if row.status == "CLOSED":
            equity += float(row.realized_pnl or 0) - float(row.total_costs or 0)
            points.append(
                {
                    "timestamp": row.closed_at or row.opened_at,
                    "equity": round(equity, 2),
                    "event": "CLOSED_TRADE",
                    "position_id": row.position_id,
                }
            )

    live_account = _account_payload(db, account_id)
    if live_account["unrealized_pnl"] != 0:
        points.append(
            {
                "timestamp": datetime.now(timezone.utc),
                "equity": round(live_account["equity"], 2),
                "event": "LIVE_MARK",
            }
        )

    return {"points": points}


@router.post("/orders")
def create_order(req: PaperOrderUIRequest, db: Session = Depends(get_db)):
    model = PaperOrderRequest(
        account_id=req.account_id,
        symbol=req.symbol,
        action=req.action,
        option_type=req.option_type,
        strike=req.strike,
        expiry=req.expiry,
        quantity=req.quantity,
        entry_price=req.entry_price,
        stop_loss=req.stop_loss,
        target_1=req.target_1,
        target_2=req.target_2,
        timestamp=_ts(req.timestamp),
        bid=req.bid,
        ask=req.ask,
        available_quantity=req.available_quantity,
        signal_id=req.signal_id,
        source=req.source,
    )
    try:
        _ensure_account(db, req.account_id)
        position = engine.open(db, model)
        return {
            "status": "FILLED" if not position.partial_fill else "PARTIAL",
            "position": position.model_dump(mode="json"),
            "live_execution": False,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/positions/{position_id}/mark")
def mark_position(position_id: str, req: MarkRequest, db: Session = Depends(get_db)):
    ts = _ts(req.timestamp)
    request = PaperMarkRequest(
        account_id=req.account_id,
        instrument_key=position_id,
        price=req.price,
        timestamp=ts,
        bid=req.bid,
        ask=req.ask,
        available_quantity=req.available_quantity,
        underlying_ltp=req.underlying_ltp,
    )
    try:
        position = db.scalar(
            select(PaperTrade).where(
                PaperTrade.account_id == req.account_id,
                PaperTrade.position_id == position_id,
            )
        )
        if position is None:
            raise HTTPException(status_code=404, detail="PAPER_POSITION_NOT_FOUND")

        # phase19 mark() filters by symbol, so we directly use the underlying
        # engine request contract by temporarily targeting the position symbol.
        request.instrument_key = position.symbol
        rows = engine.mark(db, request)
        matched = next((item for item in rows if item.position_id == position_id), None)
        if matched is None:
            raise HTTPException(status_code=404, detail="PAPER_POSITION_NOT_FOUND")
        return {"position": matched.model_dump(mode="json"), "live_execution": False}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/positions/{position_id}/mark-latest")
def mark_latest(position_id: str, req: AutoMarkRequest, db: Session = Depends(get_db)):
    position = db.scalar(
        select(PaperTrade).where(
            PaperTrade.account_id == req.account_id,
            PaperTrade.position_id == position_id,
            PaperTrade.status == "OPEN",
        )
    )
    if position is None:
        raise HTTPException(status_code=404, detail="PAPER_POSITION_NOT_FOUND")

    instrument = db.scalar(
        select(Instrument).where(Instrument.instrument_key == position.symbol)
    )

    snapshot = None
    if instrument is not None:
        snapshot = db.scalar(
            select(MarketSnapshot)
            .where(MarketSnapshot.instrument_id == instrument.id)
            .order_by(MarketSnapshot.timestamp.desc())
        )

    if snapshot is None:
        # Also permit PaperTrade.symbol to be a trading symbol in the instrument master.
        instrument = db.scalar(
            select(Instrument).where(Instrument.trading_symbol == position.symbol)
        )
        if instrument is not None:
            snapshot = db.scalar(
                select(MarketSnapshot)
                .where(MarketSnapshot.instrument_id == instrument.id)
                .order_by(MarketSnapshot.timestamp.desc())
            )

    if snapshot is None or snapshot.ltp is None:
        raise HTTPException(
            status_code=404,
            detail="NO_LATEST_MARKET_SNAPSHOT_FOR_POSITION",
        )

    request = PaperMarkRequest(
        account_id=req.account_id,
        instrument_key=position.symbol,
        price=float(snapshot.ltp),
        timestamp=snapshot.timestamp,
        bid=float(snapshot.bid) if snapshot.bid is not None else None,
        ask=float(snapshot.ask) if snapshot.ask is not None else None,
        available_quantity=None,
        underlying_ltp=float(snapshot.underlying_ltp) if snapshot.underlying_ltp is not None else None,
        market_closed=False,
    )

    try:
        rows = engine.mark(db, request)
        matched = next((item for item in rows if item.position_id == position_id), None)
        if matched is None:
            raise HTTPException(status_code=404, detail="PAPER_POSITION_NOT_FOUND")
        return {
            "position": matched.model_dump(mode="json"),
            "snapshot_time": snapshot.timestamp,
            "snapshot_source": snapshot.source,
            "live_execution": False,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/positions/{position_id}/close")
def close_position(
    position_id: str,
    req: PaperCloseRequest,
    db: Session = Depends(get_db),
):
    request = req.model_copy(update={"position_id": position_id, "account_id": req.account_id})
    try:
        position = engine.close(db, request)
        return {"position": position.model_dump(mode="json"), "live_execution": False}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
