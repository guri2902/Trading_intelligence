from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from .identity import canonical_identity
from .models import InstrumentRecord


def map_upstox_instrument(row: dict[str, Any]) -> InstrumentRecord:
    """
    Maps an Upstox instrument-master row to the canonical internal model.

    The raw Upstox key is preserved as `source` identity by the ingestion
    service; the resulting canonical identity becomes the platform key.
    """
    exchange = str(row.get("exchange") or row.get("exchange_segment") or "")
    segment = str(row.get("segment") or row.get("segment_name") or "")
    symbol = str(
        row.get("trading_symbol")
        or row.get("tradingsymbol")
        or row.get("symbol")
        or ""
    )

    instrument_type = str(
        row.get("instrument_type")
        or row.get("instrument_type_name")
        or ""
    ).upper()

    option_type = row.get("option_type") or row.get("instrument_type_code")
    if option_type in {"CE", "PE"}:
        option_type = str(option_type)
    else:
        option_type = None

    expiry_raw = row.get("expiry")
    expiry: date | None = None
    if expiry_raw:
        if isinstance(expiry_raw, date):
            expiry = expiry_raw
        else:
            text = str(expiry_raw)[:10]
            expiry = date.fromisoformat(text)

    strike_raw = row.get("strike_price", row.get("strike"))
    strike = Decimal(str(strike_raw)) if strike_raw not in (None, "") else None

    lot_raw = row.get("lot_size", row.get("freeze_quantity"))
    lot_size = int(lot_raw) if lot_raw not in (None, "") else None

    tick_raw = row.get("tick_size")
    tick_size = Decimal(str(tick_raw)) if tick_raw not in (None, "") else None

    underlying_key = row.get("underlying_key")
    underlying_symbol = row.get("underlying_symbol")

    source_key = str(row.get("instrument_key") or row.get("instrument_key_id") or "")
    canonical_key = canonical_identity(
        exchange=exchange,
        segment=segment,
        trading_symbol=(
            str(underlying_symbol).upper()
            if underlying_symbol
            else symbol
        ),
        instrument_type=instrument_type,
        expiry_date=expiry,
        strike=strike,
        option_type=option_type,
    )

    updated_raw = row.get("last_updated") or row.get("updated_at")
    updated_at = None
    if updated_raw:
        try:
            updated_at = datetime.fromisoformat(
                str(updated_raw).replace("Z", "+00:00")
            )
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
        except ValueError:
            updated_at = None

    return InstrumentRecord(
        instrument_key=canonical_key,
        exchange=exchange,
        segment=segment,
        instrument_type=instrument_type or "UNKNOWN",
        trading_symbol=symbol,
        underlying_key=underlying_key,
        underlying_symbol=underlying_symbol,
        expiry_date=expiry,
        strike=strike,
        option_type=option_type,
        lot_size=lot_size,
        tick_size=tick_size,
        source="upstox",
        source_updated_at=updated_at,
    )
