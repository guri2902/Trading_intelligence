from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from .data_service import DataService


DEFAULT_INSTRUMENTS = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
    "SENSEX": "BSE_INDEX|SENSEX",
}


class MarketDataPipeline:
    """
    Single backend market-data access layer for current market state.

    The pipeline deliberately uses the existing provider registry so there is
    one source of truth for Upstox authentication and market-data behavior.
    It does not invent/fallback to synthetic prices.
    """

    def __init__(self, data_service: DataService | None = None) -> None:
        self.data_service = data_service or DataService()

    def resolve_instrument_key(
        self,
        symbol: str,
        instrument_key: str | None = None,
    ) -> str:
        if instrument_key and instrument_key.strip():
            return instrument_key.strip()

        normalized = symbol.strip().upper()
        if normalized not in DEFAULT_INSTRUMENTS:
            raise ValueError(f"Unsupported symbol: {normalized}")

        return DEFAULT_INSTRUMENTS[normalized]

    def snapshot(
        self,
        symbol: str = "NIFTY",
        instrument_key: str | None = None,
        include_candles: bool = True,
        candle_interval: int = 5,
        candle_limit: int = 100,
    ) -> dict[str, Any]:
        resolved_key = self.resolve_instrument_key(symbol, instrument_key)

        provider = self.data_service.providers.get("upstox")
        if provider is None:
            return {
                "status": "UNAVAILABLE",
                "provider": "upstox",
                "symbol": symbol.upper(),
                "instrument_key": resolved_key,
                "error": "Upstox provider is not registered.",
                "quote": None,
                "candles": [],
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

        checked_at = datetime.now(timezone.utc)

        try:
            ltp, quote_timestamp = provider.market_quote(resolved_key)
        except Exception as exc:
            return {
                "status": "ERROR",
                "provider": "upstox",
                "symbol": symbol.upper(),
                "instrument_key": resolved_key,
                "error": f"Market quote request failed: {exc}",
                "quote": None,
                "candles": [],
                "checked_at": checked_at.isoformat(),
            }

        candles: list[dict[str, Any]] = []
        candle_error: str | None = None

        if include_candles:
            try:
                today = datetime.now().astimezone().date()
                rows = provider.candles(
                    resolved_key,
                    "minutes",
                    candle_interval,
                    today,
                    today,
                )
                rows = rows[-candle_limit:]
                candles = [
                    {
                        "timestamp": row.timestamp.isoformat(),
                        "open": row.open,
                        "high": row.high,
                        "low": row.low,
                        "close": row.close,
                        "volume": row.volume,
                        "open_interest": row.open_interest,
                        "source": row.source,
                    }
                    for row in rows
                ]
            except Exception as exc:
                candle_error = str(exc)

        if ltp is None:
            status = "NO_QUOTE"
        else:
            status = "CONNECTED"

        return {
            "status": status,
            "provider": "upstox",
            "symbol": symbol.upper(),
            "instrument_key": resolved_key,
            "checked_at": checked_at.isoformat(),
            "market_timestamp": (
                quote_timestamp.isoformat() if quote_timestamp else None
            ),
            "quote": {
                "ltp": ltp,
            } if ltp is not None else None,
            "candles": candles,
            "candle_status": (
                "OK"
                if candles
                else ("UNAVAILABLE" if candle_error else "NO_DATA")
            ),
            "candle_error": candle_error,
        }
