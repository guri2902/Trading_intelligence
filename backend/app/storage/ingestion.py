from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..instruments.identity import canonical_identity
from ..db.models import Instrument
from ..providers.base import Candle as ProviderCandle
from ..providers.base import OptionChainSnapshot
from .quality import evaluate_candles, evaluate_option_quotes
from .repository import (
    persist_candles,
    persist_option_snapshot,
    quality_to_payload,
    record_quality_event,
)


def ingest_provider_candles(
    db: Session,
    *,
    instrument: Instrument,
    timeframe: str,
    candles: list[ProviderCandle],
    expected_interval_minutes: int | None,
    source: str,
    max_age_seconds: int | None = None,
) -> dict:
    rows = [
        {
            "timestamp": item["timestamp"],
            "open": item["open"],
            "high": item["high"],
            "low": item["low"],
            "close": item["close"],
            "volume": item.get("volume", 0),
            "open_interest": item.get("open_interest", 0),
        }
        for item in candles
    ]

    result = evaluate_candles(
        [
            {
                **row,
                "timestamp": row["timestamp"].isoformat(),
            }
            for row in rows
        ],
        timeframe_minutes=expected_interval_minutes,
        max_age_seconds=max_age_seconds,
    )

    inserted = persist_candles(
        db,
        instrument=instrument,
        timeframe=timeframe,
        rows=rows,
        source=source,
        quality_status=result.status,
    )

    if result.status != "PASS":
        record_quality_event(
            db,
            source=source,
            instrument_key=instrument.instrument_key,
            event_type="CANDLE_QUALITY",
            severity="ERROR" if not result.signal_safe else "WARN",
            details=result.reason,
        )

    return {
        "stored": inserted,
        "quality": quality_to_payload(result),
        "instrument_id": instrument.id,
        "timeframe": timeframe,
        "source": source,
    }


def ingest_option_chain(
    db: Session,
    *,
    snapshot: OptionChainSnapshot,
    instrument_lookup: dict[tuple[date, float, str], Instrument],
    source: str,
    max_age_seconds: int = 60,
) -> dict:
    snapshot_dicts = [
        {
            "instrument_key": q.instrument_key,
            "expiry": q.expiry.isoformat(),
            "strike": q.strike,
            "option_type": q.option_type,
            "underlying_ltp": snapshot.underlying_ltp,
            "ltp": q.ltp,
            "bid": q.bid,
            "ask": q.ask,
            "bid_qty": q.bid_qty,
            "ask_qty": q.ask_qty,
            "volume": q.volume,
            "open_interest": q.open_interest,
            "change_in_oi": q.change_in_oi,
            "iv": q.iv,
            "delta": q.delta,
            "gamma": q.gamma,
            "theta": q.theta,
            "vega": q.vega,
            "rho": q.rho,
        }
        for q in snapshot.quotes
    ]

    quality = evaluate_option_quotes(
        snapshot_dicts,
        snapshot_timestamp=snapshot.timestamp,
        max_age_seconds=max_age_seconds,
    )

    pairs: list[tuple[Instrument, dict]] = []
    unmapped = 0

    for q in snapshot.quotes:
        key = (q.expiry, float(q.strike), q.option_type)
        instrument = instrument_lookup.get(key)
        if instrument is None:
            unmapped += 1
            continue

        pairs.append(
            (
                instrument,
                {
                    "underlying_ltp": snapshot.underlying_ltp,
                    "ltp": q.ltp,
                    "bid": q.bid,
                    "ask": q.ask,
                    "bid_qty": q.bid_qty,
                    "ask_qty": q.ask_qty,
                    "volume": q.volume,
                    "open_interest": q.open_interest,
                    "change_in_oi": q.change_in_oi,
                    "iv": q.iv,
                    "delta": q.delta,
                    "gamma": q.gamma,
                    "theta": q.theta,
                    "vega": q.vega,
                    "rho": q.rho,
                },
            )
        )

    stored = persist_option_snapshot(
        db,
        instrument_rows=pairs,
        timestamp=snapshot.timestamp,
        source=source,
        quality_status=quality.status,
    )

    if quality.status != "PASS" or unmapped:
        record_quality_event(
            db,
            source=source,
            instrument_key=snapshot.underlying_key,
            event_type="OPTION_CHAIN_QUALITY",
            severity="ERROR" if not quality.signal_safe else "WARN",
            details=f"{quality.reason}; unmapped_quotes={unmapped}",
        )

    return {
        "stored": stored,
        "unmapped": unmapped,
        "quotes_received": len(snapshot.quotes),
        "quality": quality_to_payload(quality),
        "timestamp": snapshot.timestamp.isoformat(),
        "source": source,
    }
