from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from .models import OptionContract, OptionQuoteState


def parse_option_chain_payload(
    payload: dict[str, Any],
    *,
    underlying_key: str,
) -> list[OptionQuoteState]:
    rows = payload.get("data") or []
    result = []

    for row in rows:
        expiry_raw = row.get("expiry")
        strike_raw = row.get("strike_price")
        spot = row.get("underlying_spot_price")

        if not expiry_raw or strike_raw is None:
            continue

        expiry = date.fromisoformat(str(expiry_raw))
        strike = float(strike_raw)

        for option_type, field in (
            ("CE", "call_options"),
            ("PE", "put_options"),
        ):
            side = row.get(field) or {}
            instrument_key = side.get("instrument_key")
            if not instrument_key:
                continue

            market = side.get("market_data") or {}
            greeks = side.get("option_greeks") or {}

            contract = OptionContract(
                instrument_key=instrument_key,
                underlying_key=underlying_key,
                underlying_symbol=str(
                    row.get("underlying_symbol")
                    or row.get("name")
                    or ""
                ),
                expiry=expiry,
                strike=strike,
                option_type=option_type,
                lot_size=None,
                tick_size=None,
            )

            result.append(
                OptionQuoteState(
                    contract=contract,
                    timestamp=datetime.now(timezone.utc),
                    underlying_spot=float(spot) if spot is not None else None,
                    ltp=float(market["ltp"]) if market.get("ltp") is not None else None,
                    close_price=float(market["close_price"])
                    if market.get("close_price") is not None
                    else None,
                    bid=float(market["bid_price"])
                    if market.get("bid_price") is not None
                    else None,
                    ask=float(market["ask_price"])
                    if market.get("ask_price") is not None
                    else None,
                    bid_qty=int(market["bid_qty"])
                    if market.get("bid_qty") is not None
                    else None,
                    ask_qty=int(market["ask_qty"])
                    if market.get("ask_qty") is not None
                    else None,
                    volume=float(market["volume"])
                    if market.get("volume") is not None
                    else None,
                    open_interest=float(market["oi"])
                    if market.get("oi") is not None
                    else None,
                    previous_oi=float(market["prev_oi"])
                    if market.get("prev_oi") is not None
                    else None,
                    iv=float(greeks["iv"])
                    if greeks.get("iv") is not None
                    else None,
                    delta=float(greeks["delta"])
                    if greeks.get("delta") is not None
                    else None,
                    gamma=float(greeks["gamma"])
                    if greeks.get("gamma") is not None
                    else None,
                    theta=float(greeks["theta"])
                    if greeks.get("theta") is not None
                    else None,
                    vega=float(greeks["vega"])
                    if greeks.get("vega") is not None
                    else None,
                    rho=float(greeks["rho"])
                    if greeks.get("rho") is not None
                    else None,
                    pop=float(greeks["pop"])
                    if greeks.get("pop") is not None
                    else None,
                )
            )

    return result
