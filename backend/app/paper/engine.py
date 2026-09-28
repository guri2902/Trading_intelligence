from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import PaperAccount, PaperCloseRequest, PaperMarkRequest, PaperOrderRequest, PaperPosition
from .execution import MarketQuote, RealisticExecutionSimulator
from ..db.models import PaperTrade

class PaperTradingEngine:
    """Simulation-only execution engine with configurable market microstructure costs."""
    def __init__(self, simulator: RealisticExecutionSimulator | None = None):
        self.simulator = simulator or RealisticExecutionSimulator()

    def ensure_account(self, db: Session, account_id: str, starting_equity: float) -> PaperAccount:
        row = db.scalar(select(PaperTrade).where(PaperTrade.account_id == account_id, PaperTrade.position_id == "__ACCOUNT__"))
        if row is None:
            row = PaperTrade(account_id=account_id, position_id="__ACCOUNT__", symbol="__ACCOUNT__", option_type="NONE", strike=0, expiry="", quantity=0, entry_price=starting_equity, mark_price=starting_equity, status="ACCOUNT", opened_at=datetime.now(timezone.utc), realized_pnl=0, unrealized_pnl=0)
            db.add(row); db.commit()
        return self.account(db, account_id)

    def account(self, db: Session, account_id: str) -> PaperAccount:
        rows = db.scalars(select(PaperTrade).where(PaperTrade.account_id == account_id, PaperTrade.position_id != "__ACCOUNT__")).all()
        account = db.scalar(select(PaperTrade).where(PaperTrade.account_id == account_id, PaperTrade.position_id == "__ACCOUNT__"))
        if account is None: raise ValueError("PAPER_ACCOUNT_NOT_FOUND")
        realized = sum(float(r.realized_pnl or 0) - float(r.total_costs or 0) for r in rows)
        unrealized = sum(float(r.unrealized_pnl or 0) for r in rows if r.status == "OPEN")
        closed = [r for r in rows if r.status == "CLOSED"]
        return PaperAccount(account_id=account_id, starting_equity=float(account.entry_price), realized_pnl=round(realized,2), unrealized_pnl=round(unrealized,2), open_positions=sum(r.status=="OPEN" for r in rows), total_trades=len(closed), win_trades=sum(float(r.realized_pnl or 0)-float(r.total_costs or 0)>0 for r in closed), loss_trades=sum(float(r.realized_pnl or 0)-float(r.total_costs or 0)<0 for r in closed))

    def open(self, db: Session, req: PaperOrderRequest) -> PaperPosition:
        if req.action not in {"BUY_CE", "BUY_PE"}:
            raise ValueError("PAPER_ONLY_BUY_OPTIONS")
        sim = self.simulator.fill("BUY", req.quantity, MarketQuote(req.entry_price, req.bid, req.ask, req.available_quantity, timestamp=req.timestamp))
        if sim.filled_qty <= 0:
            raise ValueError("NO_LIQUIDITY_FOR_ENTRY")
        position_id = f"P-{uuid4().hex[:12]}"
        turnover = sim.fill_price * sim.filled_qty
        costs = self.simulator.costs(turnover, 0.0, orders=1)
        row = PaperTrade(account_id=req.account_id, position_id=position_id, symbol=req.symbol, option_type=req.option_type, strike=req.strike, expiry=req.expiry, quantity=sim.filled_qty, requested_quantity=req.quantity, filled_quantity=sim.filled_qty, entry_price=sim.fill_price, mark_price=sim.fill_price, stop_loss=req.stop_loss, target_1=req.target_1, target_2=req.target_2, status="OPEN", opened_at=req.timestamp, realized_pnl=0, unrealized_pnl=0, signal_id=req.signal_id, source=req.source, entry_slippage=sim.slippage_cost, entry_costs=costs.total, total_costs=costs.total, partial_fill=sim.partial, latency_ms=sim.latency_ms)
        db.add(row); db.commit(); db.refresh(row)
        return self._position(row)

    def mark(self, db: Session, req: PaperMarkRequest) -> list[PaperPosition]:
        rows = db.scalars(select(PaperTrade).where(PaperTrade.account_id == req.account_id, PaperTrade.symbol == req.instrument_key, PaperTrade.status == "OPEN")).all()
        out=[]
        for r in rows: self._apply_mark(r, req, out)
        db.commit(); return out

    def close(self, db: Session, req: PaperCloseRequest) -> PaperPosition:
        r = db.scalar(select(PaperTrade).where(PaperTrade.account_id == req.account_id, PaperTrade.position_id == req.position_id, PaperTrade.status == "OPEN"))
        if r is None: raise ValueError("PAPER_POSITION_NOT_FOUND")
        self._close_row(r, req.exit_price, req.timestamp, req.reason, req.__dict__)
        db.commit(); db.refresh(r); return self._position(r)

    def _apply_mark(self, r: PaperTrade, req: PaperMarkRequest, out: list[PaperPosition]):
        if req.market_closed and self.simulator.is_expired(r.expiry, req.timestamp):
            if req.underlying_ltp is None: raise ValueError("UNDERLYING_REQUIRED_FOR_EXPIRY_SETTLEMENT")
            price = self.simulator.expiry_value(r.option_type, float(r.strike), req.underlying_ltp)
            self._close_row(r, price, req.timestamp, "EXPIRY", req.__dict__)
        else:
            quote = MarketQuote(req.price, req.bid, req.ask, req.available_quantity, req.underlying_ltp, req.timestamp)
            self._mark_open(r, quote)
            reason = None
            if req.price <= float(r.stop_loss): reason = "STOP_LOSS"
            elif r.target_2 is not None and req.price >= float(r.target_2): reason = "TARGET_2"
            elif r.target_1 is not None and req.price >= float(r.target_1): reason = "TARGET_1"
            if reason: self._close_row(r, req.price, req.timestamp, reason, req.__dict__)
        out.append(self._position(r))

    @staticmethod
    def _mark_open(r: PaperTrade, quote: MarketQuote):
        r.mark_price = quote.ltp
        r.unrealized_pnl = (quote.ltp - float(r.entry_price)) * int(r.quantity)

    def _close_row(self, r: PaperTrade, price: float, ts: datetime, reason: str, context: dict):
        quote = MarketQuote(price, context.get("bid"), context.get("ask"), context.get("available_quantity"), context.get("underlying_ltp"), ts)
        fill = self.simulator.fill("SELL", int(r.quantity), quote)
        if fill.filled_qty <= 0:
            raise ValueError("NO_LIQUIDITY_FOR_EXIT")
        proceeds = fill.fill_price * fill.filled_qty
        buy_turnover = float(r.entry_price) * int(r.quantity)
        costs = self.simulator.costs(buy_turnover, proceeds, orders=1)
        r.mark_price=fill.fill_price; r.exit_price=fill.fill_price
        r.realized_pnl=(fill.fill_price-float(r.entry_price))*fill.filled_qty
        r.unrealized_pnl=0; r.status="CLOSED"; r.closed_at=ts; r.close_reason=reason
        r.exit_slippage=fill.slippage_cost; r.exit_costs=costs.total; r.total_costs=float(r.total_costs or 0) + costs.total; r.partial_fill = bool(r.partial_fill or fill.partial); r.latency_ms=max(int(r.latency_ms or 0), fill.latency_ms)

    @staticmethod
    def _position(r: PaperTrade) -> PaperPosition:
        return PaperPosition(position_id=r.position_id, account_id=r.account_id, symbol=r.symbol, option_type=r.option_type, strike=float(r.strike), expiry=r.expiry, quantity=r.quantity, entry_price=float(r.entry_price), mark_price=float(r.mark_price), stop_loss=float(r.stop_loss), target_1=float(r.target_1) if r.target_1 is not None else None, target_2=float(r.target_2) if r.target_2 is not None else None, realized_pnl=float(r.realized_pnl or 0), unrealized_pnl=float(r.unrealized_pnl or 0), status=r.status, opened_at=r.opened_at, closed_at=r.closed_at, exit_price=float(r.exit_price) if r.exit_price is not None else None, close_reason=r.close_reason, signal_id=r.signal_id, requested_quantity=r.requested_quantity, filled_quantity=r.filled_quantity, total_costs=float(r.total_costs or 0), partial_fill=bool(r.partial_fill or False))
