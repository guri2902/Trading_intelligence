from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db.models import Instrument, MarketSnapshot
from ..db.session import get_db
from ..realtime import realtime_pipeline

router = APIRouter(prefix="/ui", tags=["ui-market-data"])



SUPPORTED_UNDERLYINGS = {
    "NIFTY": "NIFTY",
    "BANKNIFTY": "BANKNIFTY",
    "FINNIFTY": "FINNIFTY",
    "SENSEX": "SENSEX",
}


def _num(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _quote(row: MarketSnapshot | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {
        "ltp": _num(row.ltp),
        "bid": _num(row.bid),
        "ask": _num(row.ask),
        "bid_qty": _int(row.bid_qty),
        "ask_qty": _int(row.ask_qty),
        "volume": _num(row.volume),
        "open_interest": _int(row.open_interest),
        "change_in_oi": _int(row.change_in_oi),
        "iv": _num(row.iv),
        "delta": _num(row.delta),
        "gamma": _num(row.gamma),
        "theta": _num(row.theta),
        "vega": _num(row.vega),
        "rho": _num(row.rho),
        "underlying_ltp": _num(row.underlying_ltp),
        "timestamp": row.timestamp,
        "source": row.source,
        "quality_status": row.quality_status,
    }


def _option_instrument(
    instrument: Instrument,
    snapshot: MarketSnapshot | None,
) -> dict[str, Any]:
    quote = _quote(snapshot)
    return {
        **quote,
        "instrument_key": instrument.instrument_key,
        "trading_symbol": instrument.trading_symbol,
        "underlying_symbol": instrument.underlying_symbol,
        "expiry": instrument.expiry_date,
        "strike": _num(instrument.strike),
        "option_type": instrument.option_type,
        "lot_size": instrument.lot_size,
        "tick_size": _num(instrument.tick_size),
    }


@router.get("/option-chain")
def option_chain(
    underlying: str = Query("NIFTY"),
    underlying_key: str | None = Query(default=None),
    expiry: str | None = Query(default=None),
    expiry_date: str | None = Query(default=None),
    strike_window: int = Query(default=10, ge=1, le=30),
):
    """
    Return Upstox option-chain data.

    The expiry selector is populated from the full option-contract universe
    returned by Upstox, while the selected chain itself is fetched for exactly
    one expiry. This keeps every available expiry visible even though the
    Upstox option-chain endpoint is expiry-specific.
    """
    from datetime import date as date_type
    from ..data_service import DataService

    symbol = (underlying or "NIFTY").strip().upper()

    key_map = {
        "NIFTY": "NSE_INDEX|Nifty 50",
        "BANKNIFTY": "NSE_INDEX|Nifty Bank",
        "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
        "SENSEX": "BSE_INDEX|SENSEX",
    }

    resolved_key = (underlying_key or "").strip() or key_map.get(symbol)

    if not resolved_key:
        return {
            "status": "UNSUPPORTED",
            "underlying": symbol,
            "provider": "upstox",
            "source": "upstox",
            "quotes": [],
            "rows": [],
            "strikes": [],
            "available_expiries": [],
            "message": "Underlying is not supported by this market-data view.",
        }

    requested_expiry_raw = (expiry_date or expiry or "").strip() or None
    requested_expiry = None

    if requested_expiry_raw:
        try:
            requested_expiry = date_type.fromisoformat(requested_expiry_raw)
        except ValueError:
            return {
                "status": "ERROR",
                "underlying": symbol,
                "provider": "upstox",
                "source": "upstox",
                "quotes": [],
                "rows": [],
                "strikes": [],
                "available_expiries": [],
                "message": "Expiry must use YYYY-MM-DD.",
            }

    service = DataService()
    provider = service.providers.get("upstox")

    if provider is None or not hasattr(provider, "option_chain"):
        return {
            "status": "ERROR",
            "underlying": symbol,
            "provider": "upstox",
            "source": "upstox",
            "quotes": [],
            "rows": [],
            "strikes": [],
            "available_expiries": [],
            "message": "Upstox provider is not available.",
        }

    # Resolve the complete expiry universe independently from the selected
    # option-chain request. The chain endpoint itself is expiry-specific.
    available_expiry_values: set[date_type] = set()

    try:
        contracts = provider.option_contracts(
            resolved_key,
            expiry_date=None,
        )

        for contract in contracts or []:
            if not isinstance(contract, dict):
                continue

            raw_expiry = contract.get("expiry")
            if not raw_expiry:
                continue

            try:
                parsed = date_type.fromisoformat(str(raw_expiry))
            except (TypeError, ValueError):
                continue

            available_expiry_values.add(parsed)

    except Exception as exc:
        # Don't fail an otherwise usable chain solely because expiry discovery
        # failed. The explicitly requested expiry can still be attempted.
        expiry_discovery_error = str(exc)
    else:
        expiry_discovery_error = None

    available_expiries = sorted(
        value.isoformat() for value in available_expiry_values
    )

    # When no expiry was selected, use the nearest future expiry from the
    # contract universe. The provider also supports resolving this itself,
    # but resolving here lets the response expose the selected value clearly.
    selected_expiry = requested_expiry

    if selected_expiry is None and available_expiry_values:
        today = date_type.today()
        future = sorted(
            value for value in available_expiry_values if value >= today
        )
        if future:
            selected_expiry = future[0]
        else:
            selected_expiry = sorted(available_expiry_values)[0]

    try:
        snapshot = provider.option_chain(
            resolved_key,
            selected_expiry,
        )
    except Exception as exc:
        return {
            "status": "ERROR",
            "underlying": symbol,
            "underlying_key": resolved_key,
            "provider": "upstox",
            "source": "upstox",
            "quotes": [],
            "rows": [],
            "strikes": [],
            "available_expiries": available_expiries,
            "expiry": (
                selected_expiry.isoformat()
                if selected_expiry is not None
                else None
            ),
            "message": f"Upstox option-chain request failed: {exc}",
        }

    def dump_quote(quote: Any) -> dict[str, Any]:
        if hasattr(quote, "model_dump"):
            return quote.model_dump(mode="json")
        if isinstance(quote, dict):
            return dict(quote)
        return dict(quote)

    quotes = [dump_quote(quote) for quote in (snapshot.quotes or [])]

    # Use the explicitly selected expiry when available. When Upstox/provider
    # returns it in the snapshot, prefer that value for display.
    final_expiry = (
        selected_expiry.isoformat()
        if selected_expiry is not None
        else None
    )

    if final_expiry is None and snapshot.expiry_dates:
        final_expiry = str(snapshot.expiry_dates[0])

    if final_expiry:
        quotes = [
            quote
            for quote in quotes
            if str(quote.get("expiry")) == final_expiry
        ]

    strikes_all = sorted(
        {
            float(quote["strike"])
            for quote in quotes
            if quote.get("strike") is not None
        }
    )

    spot = snapshot.underlying_ltp

    if strikes_all and spot is not None:
        atm = min(
            strikes_all,
            key=lambda strike: abs(strike - float(spot)),
        )
        atm_index = strikes_all.index(atm)
        low = max(0, atm_index - strike_window)
        high = min(
            len(strikes_all),
            atm_index + strike_window + 1,
        )
        visible_strikes = strikes_all[low:high]
    else:
        atm = None
        visible_strikes = strikes_all[: (2 * strike_window) + 1]

    quote_by_strike: dict[float, dict[str, Any]] = {}

    for quote in quotes:
        strike = quote.get("strike")
        option_type = str(quote.get("option_type") or "").upper()

        if strike is None:
            continue

        strike_value = float(strike)

        if strike_value not in visible_strikes:
            continue

        bucket = quote_by_strike.setdefault(
            strike_value,
            {
                "strike": strike_value,
                "ce": None,
                "pe": None,
            },
        )

        if option_type == "CE":
            bucket["ce"] = quote
        elif option_type == "PE":
            bucket["pe"] = quote

    grouped_rows = [
        quote_by_strike[strike]
        for strike in visible_strikes
        if strike in quote_by_strike
    ]

    status = "LIVE" if quotes else "WAIT"

    message = None
    if not quotes:
        message = (
            snapshot.reason
            or "Upstox returned no usable option-chain contracts."
        )
    elif expiry_discovery_error:
        # Keep this informational rather than failing the page; the selected
        # chain still came successfully from Upstox.
        message = f"Expiry list refresh warning: {expiry_discovery_error}"

    return {
        "status": status,
        "underlying": symbol,
        "underlying_key": resolved_key,
        "expiry": final_expiry,
        "available_expiries": available_expiries,
        "snapshot_timestamp": (
            snapshot.timestamp.isoformat()
            if snapshot.timestamp
            else None
        ),
        "spot": spot,
        "underlying_ltp": spot,
        "atm_strike": atm,
        "strike_window": strike_window,
        "provider": "upstox",
        "source": "upstox",
        "market_open": bool(quotes),
        "contract_count": len(quotes),
        "quotes": quotes,
        "rows": grouped_rows,
        "strikes": visible_strikes,
        "message": message,
    }


@router.get("/scanner")
def scanner(
    state: str = Query("ALL"),
    limit: int = Query(30, ge=1, le=100),
):
    pipeline = realtime_pipeline.status()
    result = pipeline.get("last_result") or {}
    risk = result.get("risk") or {}
    strategies = result.get("strategies") or {}

    setups = strategies.get("setups") or []
    out: list[dict[str, Any]] = []

    for setup in setups:
        if not isinstance(setup, dict):
            continue

        row_state = str(setup.get("state") or "NO_SETUP").upper()
        if state.upper() != "ALL" and row_state != state.upper():
            continue

        confidence = _num(setup.get("confidence"))
        direction = str(setup.get("direction") or "NONE").upper()

        selected_option = None
        if direction == "LONG":
            best = (result.get("options") or {}).get("best_ce") or {}
            selected_option = best.get("quote") if isinstance(best, dict) else None
        elif direction == "SHORT":
            best = (result.get("options") or {}).get("best_pe") or {}
            selected_option = best.get("quote") if isinstance(best, dict) else None

        out.append({
            "symbol": result.get("market", {}).get("symbol", "NIFTY"),
            "strategy": setup.get("strategy"),
            "direction": direction,
            "state": row_state,
            "confidence": confidence,
            "entry": _num(setup.get("entry")),
            "invalidation": _num(setup.get("invalidation")),
            "target_1": _num(setup.get("target_1")),
            "target_2": _num(setup.get("target_2")),
            "risk_reward": _num(setup.get("risk_reward")),
            "evidence": setup.get("evidence") or [],
            "wait_for": setup.get("wait_for") or [],
            "invalidation_reasons": setup.get("invalidation_reasons") or [],
            "metadata": setup.get("metadata") or {},
            "option": selected_option,
            "risk_action": risk.get("final_action"),
            "risk_approved": bool(risk.get("approved")),
            "timestamp": result.get("timestamp"),
        })

    out.sort(
        key=lambda row: (
            row["state"] == "TRIGGERED",
            row["confidence"] if row["confidence"] is not None else -1,
        ),
        reverse=True,
    )
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    market_open = time(9, 15) <= now_ist.time() < time(15, 30)
    if not market_open:
        scanner_status = "MARKET_CLOSED"
        scanner_message = (
            "NSE market session is closed. The scanner will generate new setups "
            "only during the configured live market session (09:15–15:30 IST)."
        )
    elif not pipeline.get("running"):
        scanner_status = "WAIT"
        scanner_message = "Realtime market pipeline is stopped."
    elif result:
        scanner_status = "LIVE"
        scanner_message = None
    else:
        scanner_status = "WAIT"
        scanner_message = (
            pipeline.get("last_error")
            or "Waiting for the realtime pipeline to produce its first result."
        )
    return {
        "status": scanner_status,
        "pipeline_running": bool(pipeline.get("running")),
        "market_open": market_open,
        "cycle_count": pipeline.get("cycle_count", 0),
        "last_error": pipeline.get("last_error"),
        "message": scanner_message,
        "timestamp": result.get("timestamp"),
        "symbol": result.get("market", {}).get("symbol", "NIFTY") if result else None,
        "regime": strategies.get("regime"),
        "triggered_count": strategies.get("triggered_count", 0),
        "rows": out[:limit],
    }