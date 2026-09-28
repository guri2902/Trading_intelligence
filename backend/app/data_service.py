from __future__ import annotations

from datetime import date
from typing import Any

from .normalization import normalize_candles, candle_quality_report, option_chain_quality_report
from .providers.registry import build_registry


class DataService:
    def __init__(self) -> None:
        self.providers = build_registry()

    def provider_health(self, provider_name: str) -> dict[str, Any]:
        if provider_name not in self.providers:
            raise KeyError(f"Unknown provider: {provider_name}")
        provider = self.providers[provider_name]
        health = getattr(provider, "health", None)
        return health().model_dump(mode="json") if health else {
            "provider": provider_name,
            "available": False,
            "message": "No health method",
        }

    def health(self) -> dict[str, Any]:
        output = {}
        for name, provider in self.providers.items():
            health = getattr(provider, "health", None)
            output[name] = health().model_dump(mode="json") if health else {
                "provider": name,
                "available": False,
                "message": "No health method",
            }
        return output

    def historical_candles(
        self,
        provider_name: str,
        instrument_key: str,
        unit: str,
        interval: int,
        from_date: date,
        to_date: date,
    ) -> dict[str, Any]:
        provider = self.providers.get(provider_name)
        if provider is None:
            raise KeyError(f"Unknown provider: {provider_name}")
        candles = provider.candles(
            instrument_key,
            unit,
            interval,
            from_date,
            to_date,
        )
        normalized = normalize_candles(candles)
        quality = candle_quality_report(
            normalized,
            expected_interval_minutes=interval if unit == "minutes" else None,
        )
        return {
            "provider": provider_name,
            "instrument_key": instrument_key,
            "candles": [c.model_dump(mode="json") for c in normalized],
            "quality": quality,
        }

    def option_chain(
        self,
        provider_name: str,
        underlying_key: str,
        expiry_date: date | None = None,
    ) -> dict[str, Any]:
        provider = self.providers[provider_name]
        snapshot = provider.option_chain(underlying_key, expiry_date)
        quality = option_chain_quality_report(snapshot)
        return {
            "provider": provider_name,
            "snapshot": snapshot.model_dump(mode="json"),
            "quality": quality,
        }
