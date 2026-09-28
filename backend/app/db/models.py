from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    exchange: Mapped[str] = mapped_column(String(30), index=True)
    segment: Mapped[str] = mapped_column(String(40), index=True)
    instrument_type: Mapped[str] = mapped_column(String(40), index=True)
    trading_symbol: Mapped[str] = mapped_column(String(120), index=True)
    underlying_key: Mapped[str | None] = mapped_column(String(120), index=True)
    underlying_symbol: Mapped[str | None] = mapped_column(String(80), index=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, index=True)
    strike: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    option_type: Mapped[str | None] = mapped_column(String(4))
    lot_size: Mapped[int | None] = mapped_column(Integer)
    tick_size: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "ix_instruments_option_identity",
            "underlying_symbol",
            "expiry_date",
            "strike",
            "option_type",
        ),
    )


class InstrumentAlias(Base):
    __tablename__ = "instrument_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(Integer, index=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(160), index=True)
    source_symbol: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_key",
            name="uq_instrument_alias_source_key",
        ),
    )


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(Integer, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ltp: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    bid: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    ask: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    bid_qty: Mapped[int | None] = mapped_column(Integer)
    ask_qty: Mapped[int | None] = mapped_column(Integer)
    volume: Mapped[int | None] = mapped_column(Integer)
    open_interest: Mapped[int | None] = mapped_column(Integer)
    change_in_oi: Mapped[int | None] = mapped_column(Integer)
    iv: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))

    underlying_ltp: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    delta: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    gamma: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    theta: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    vega: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    rho: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))

    source: Mapped[str] = mapped_column(String(40), index=True)
    quality_status: Mapped[str] = mapped_column(String(30), index=True)

    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "timestamp",
            "source",
            name="uq_market_snapshot_identity",
        ),
    )


class Candle(Base):
    __tablename__ = "candles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(Integer, index=True)
    timeframe: Mapped[str] = mapped_column(String(20), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    volume: Mapped[int | None] = mapped_column(Integer)
    open_interest: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(40), index=True)
    quality_status: Mapped[str] = mapped_column(String(30), index=True)

    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "timeframe",
            "timestamp",
            "source",
            name="uq_candle_identity",
        ),
        Index(
            "ix_candles_instrument_tf_time",
            "instrument_id",
            "timeframe",
            "timestamp",
        ),
    )


class DataQualityEvent(Base):
    __tablename__ = "data_quality_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    instrument_key: Mapped[str | None] = mapped_column(String(120), index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    details: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[str] = mapped_column(String(80), index=True)
    position_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(120), index=True)
    option_type: Mapped[str] = mapped_column(String(4))
    strike: Mapped[float] = mapped_column(Numeric(18, 4))
    expiry: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[int] = mapped_column(Integer)
    entry_price: Mapped[float] = mapped_column(Numeric(18, 6))
    mark_price: Mapped[float] = mapped_column(Numeric(18, 6))
    stop_loss: Mapped[float | None] = mapped_column(Numeric(18, 6))
    target_1: Mapped[float | None] = mapped_column(Numeric(18, 6))
    target_2: Mapped[float | None] = mapped_column(Numeric(18, 6))
    exit_price: Mapped[float | None] = mapped_column(Numeric(18, 6))
    realized_pnl: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    unrealized_pnl: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    status: Mapped[str] = mapped_column(String(20), index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    close_reason: Mapped[str | None] = mapped_column(String(60))
    signal_id: Mapped[str | None] = mapped_column(String(120), index=True)
    source: Mapped[str] = mapped_column(String(40), default="signal_engine")
    requested_quantity: Mapped[int | None] = mapped_column(Integer)
    filled_quantity: Mapped[int | None] = mapped_column(Integer)
    entry_slippage: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    exit_slippage: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    entry_costs: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    exit_costs: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    total_costs: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    partial_fill: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (Index("ix_paper_trades_account_status", "account_id", "status"),)
