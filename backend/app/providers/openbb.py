from __future__ import annotations

from datetime import date, datetime, timezone
import os

from .base import Candle, MarketDataProvider, ProviderStatus
from .openbb_runtime import OpenBBRuntimeError, check_openbb, run_openbb


class OpenBBProvider(MarketDataProvider):
    """OpenBB historical-data adapter.

    OpenBB is a research/data abstraction layer, not the authoritative source
    for live Indian options. Calls execute in a subprocess so OpenBB components
    that rely on main-thread signal handling do not break FastAPI worker threads.
    """

    name = "openbb"

    def __init__(self, provider_name: str | None = None) -> None:
        self.provider_name = provider_name
        self.symbol_suffix = os.getenv("OPENBB_SYMBOL_SUFFIX", "").strip()

    def health(self) -> ProviderStatus:
        checked_at = datetime.now(timezone.utc)
        result = check_openbb()
        return ProviderStatus(
            provider=self.name,
            available=bool(result["available"]),
            authenticated=False,
            checked_at=checked_at,
            message=result["message"],
            metadata={
                "provider": self.provider_name,
                "symbol_suffix": self.symbol_suffix,
                "execution": "subprocess_main_interpreter",
            },
        )

    def _symbol(self, instrument_key: str) -> str:
        symbol = instrument_key
        if "|" in symbol:
            symbol = symbol.split("|")[-1]
        symbol = symbol.strip()
        if self.symbol_suffix and "." not in symbol:
            symbol = f"{symbol}{self.symbol_suffix}"
        return symbol

    def candles(
        self,
        instrument_key,
        unit,
        interval,
        from_date: date,
        to_date: date,
    ) -> list[Candle]:
        interval_map = {
            ("minutes", 1): "1m",
            ("minutes", 5): "5m",
            ("minutes", 15): "15m",
            ("minutes", 30): "30m",
            ("hours", 1): "1h",
            ("days", 1): "1d",
        }
        interval_value = interval_map.get((unit, interval))
        if not interval_value:
            raise ValueError(f"Unsupported OpenBB interval: {unit}/{interval}")

        kwargs = {
            "symbol": self._symbol(instrument_key),
            "start_date": from_date.isoformat(),
            "end_date": to_date.isoformat(),
            "interval": interval_value,
        }
        if self.provider_name:
            kwargs["provider"] = self.provider_name

        try:
            records = run_openbb("equity.price.historical", kwargs)
        except OpenBBRuntimeError as exc:
            raise RuntimeError(f"OpenBB historical query failed: {exc}") from exc

        if isinstance(records, dict):
            records = [records]

        output: list[Candle] = []
        for row in records or []:
            ts = row.get("date") or row.get("datetime") or row.get("timestamp")
            if ts is None:
                continue
            ts = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            output.append(
                Candle(
                    instrument_key=instrument_key,
                    timestamp=ts,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]) if row.get("volume") is not None else None,
                    open_interest=None,
                    source=self.name,
                )
            )

        return sorted(output, key=lambda x: x.timestamp)
