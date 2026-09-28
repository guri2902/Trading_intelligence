from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from functools import lru_cache
from typing import Any

from .models import HistoricalOptionBar
from ..providers.upstox import UpstoxProvider


@dataclass(frozen=True)
class UpstoxOptionContract:
    instrument_key: str
    underlying_symbol: str
    expiry: str
    strike: float
    option_type: str
    trading_symbol: str
    lot_size: int


def normalize_datetime(value: datetime) -> datetime:
    # Persisted NIFTY candles are stored as naive IST timestamps.
    # Upstox API candles are timezone-aware. Normalize both to UTC.
    if value.tzinfo is None:
        from zoneinfo import ZoneInfo
        value = value.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    return value.astimezone(timezone.utc)


@lru_cache(maxsize=16)
def _cached_expiries(access_token: str, underlying_key: str) -> tuple[date, ...]:
    return tuple(UpstoxProvider(access_token=access_token).expired_expiries(underlying_key))


@lru_cache(maxsize=64)
def _cached_contracts(access_token: str, underlying_key: str, expiry: str) -> tuple[dict[str, Any], ...]:
    return tuple(
        UpstoxProvider(access_token=access_token).expired_option_contracts(
            underlying_key,
            date.fromisoformat(expiry),
        )
    )


@lru_cache(maxsize=512)
def _cached_bars(
    access_token: str,
    instrument_key: str,
    from_date: date,
    to_date: date,
    interval: str,
) -> tuple[Any, ...]:
    return tuple(
        UpstoxProvider(access_token=access_token).expired_historical_candles(
            instrument_key,
            interval,
            from_date,
            to_date,
        )
    )


class UpstoxHistoricalOptionLoader:
    """Load real historical NIFTY option contracts/candles from Upstox."""

    def __init__(
        self,
        provider: UpstoxProvider | None = None,
        underlying_key: str = "NSE_INDEX|Nifty 50",
    ) -> None:
        self.provider = provider or UpstoxProvider()
        self.underlying_key = underlying_key
        if not self.provider.access_token:
            raise RuntimeError("UPSTOX_ACCESS_TOKEN is not configured")
        self.access_token = self.provider.access_token

    @staticmethod
    def _day_end(d: date) -> datetime:
        return datetime.combine(d, time.max, tzinfo=timezone.utc)

    def _expiries(self, underlying_key: str) -> tuple[date, ...]:
        return _cached_expiries(self.access_token, underlying_key)

    def _contracts_for_expiry(self, underlying_key: str, expiry: str) -> tuple[dict[str, Any], ...]:
        return _cached_contracts(self.access_token, underlying_key, expiry)

    def _bars_cached(self, instrument_key: str, from_date: date, to_date: date, interval: str) -> tuple[Any, ...]:
        return _cached_bars(self.access_token, instrument_key, from_date, to_date, interval)

    def _candidate_expiry(self, signal_time: datetime, requested_expiry: str | None) -> str:
        signal_time = normalize_datetime(signal_time)
        if requested_expiry:
            return date.fromisoformat(requested_expiry).isoformat()

        expiries = self._expiries(self.underlying_key)
        if not expiries:
            raise ValueError("UPSTOX_NO_HISTORICAL_EXPIRIES")

        eligible = [x for x in expiries if x >= signal_time.date()]
        if not eligible:
            earliest, latest = min(expiries), max(expiries)
            raise ValueError(
                "UPSTOX_NO_EXPIRY_COVERAGE_FOR_SIGNAL:"
                f"available={earliest.isoformat()}..{latest.isoformat()}"
            )
        return min(eligible).isoformat()

    def select_contract(
        self,
        *,
        signal_time: datetime,
        direction: str,
        strike_reference: float,
        expiry: str | None = None,
        strike_mode: str = "ATM",
        strike_offset: int = 0,
    ) -> UpstoxOptionContract:
        option_type = "CE" if direction.upper() == "LONG" else "PE"
        expiry_value = self._candidate_expiry(signal_time, expiry)
        raw = [
            x for x in self._contracts_for_expiry(self.underlying_key, expiry_value)
            if str(x.get("instrument_type") or "").upper() == option_type
        ]
        if not raw:
            raise ValueError(f"UPSTOX_NO_OPTION_CONTRACTS:{expiry_value}:{option_type}")

        strikes = sorted({float(x["strike_price"]) for x in raw if x.get("strike_price") is not None})
        if not strikes:
            raise ValueError("UPSTOX_NO_STRIKES")
        nearest = min(strikes, key=lambda x: abs(x - float(strike_reference)))
        step = min((b - a for a, b in zip(strikes, strikes[1:]) if b > a), default=0.0)
        target = nearest
        mode = strike_mode.upper()
        if step > 0 and mode in {"OFFSET", "ATM_OFFSET"}:
            target = nearest + float(strike_offset) * step

        eligible = [x for x in raw if float(x.get("strike_price")) == float(target)]
        if not eligible:
            raise ValueError("UPSTOX_NO_STRIKE_MATCH")
        row = eligible[0]
        raw_lot_size = row.get("lot_size")
        try:
            lot_size = int(raw_lot_size) if raw_lot_size is not None else 0
        except (TypeError, ValueError):
            lot_size = 0
        if lot_size <= 0:
            raise ValueError(
                f"UPSTOX_CONTRACT_LOT_SIZE_MISSING:{row.get('instrument_key')}"
            )

        return UpstoxOptionContract(
            instrument_key=str(row["instrument_key"]),
            underlying_symbol=str(row.get("underlying_symbol") or row.get("name") or "NIFTY"),
            expiry=str(row.get("expiry") or expiry_value)[:10],
            strike=float(row["strike_price"]),
            option_type=option_type,
            trading_symbol=str(row.get("trading_symbol") or row.get("name") or ""),
            lot_size=lot_size,
        )

    def select_contract_for_leg(
        self,
        *,
        signal_time: datetime,
        option_type: str,
        strike_reference: float,
        expiry: str | None = None,
        strike_mode: str = "ATM",
        strike_offset: int = 0,
        specific_strike: float | None = None,
    ) -> UpstoxOptionContract:
        """Select one Strategy Builder leg from actual Upstox historical contracts."""
        signal_time = normalize_datetime(signal_time)
        option_type = str(option_type or "").upper()
        if option_type not in {"CE", "PE"}:
            raise ValueError("UPSTOX_INVALID_LEG_OPTION_TYPE")

        expiry_value = self._candidate_expiry(signal_time, expiry)
        raw = [
            x
            for x in self._contracts_for_expiry(self.underlying_key, expiry_value)
            if str(x.get("instrument_type") or "").upper() == option_type
        ]
        if not raw:
            raise ValueError(f"UPSTOX_NO_OPTION_CONTRACTS:{expiry_value}:{option_type}")

        strikes = sorted(
            float(x["strike_price"])
            for x in raw
            if x.get("strike_price") is not None
        )
        if not strikes:
            raise ValueError("UPSTOX_NO_STRIKES")

        nearest = min(strikes, key=lambda x: abs(x - float(strike_reference)))
        mode = str(strike_mode or "ATM").upper()
        step = min(
            (b - a for a, b in zip(strikes, strikes[1:]) if b > a),
            default=0.0,
        )

        if mode == "SPECIFIC":
            if specific_strike is None:
                raise ValueError("UPSTOX_SPECIFIC_STRIKE_REQUIRED")
            target = float(specific_strike)
        elif mode == "ATM":
            target = nearest
        elif mode == "ATM_PLUS":
            if step <= 0:
                raise ValueError("UPSTOX_STRIKE_STEP_UNAVAILABLE")
            target = nearest + abs(int(strike_offset)) * step
        elif mode == "ATM_MINUS":
            if step <= 0:
                raise ValueError("UPSTOX_STRIKE_STEP_UNAVAILABLE")
            target = nearest - abs(int(strike_offset)) * step
        else:
            raise ValueError(f"UPSTOX_UNSUPPORTED_LEG_STRIKE_MODE:{mode}")

        matched = min(strikes, key=lambda x: abs(x - target))
        tolerance = max(0.5, step * 0.01 if step > 0 else 0.5)
        if abs(matched - target) > tolerance:
            raise ValueError(f"UPSTOX_NO_STRIKE_MATCH:{target}")

        eligible = [x for x in raw if abs(float(x["strike_price"]) - matched) < 1e-9]
        if not eligible:
            raise ValueError("UPSTOX_NO_STRIKE_MATCH")

        row = eligible[0]
        try:
            lot_size = int(row.get("lot_size") or 0)
        except (TypeError, ValueError):
            lot_size = 0
        if lot_size <= 0:
            raise ValueError(
                f"UPSTOX_CONTRACT_LOT_SIZE_MISSING:{row.get('instrument_key')}"
            )

        return UpstoxOptionContract(
            instrument_key=str(row["instrument_key"]),
            underlying_symbol=str(row.get("underlying_symbol") or row.get("name") or "NIFTY"),
            expiry=str(row.get("expiry") or expiry_value)[:10],
            strike=float(row["strike_price"]),
            option_type=option_type,
            trading_symbol=str(row.get("trading_symbol") or row.get("name") or ""),
            lot_size=lot_size,
        )

    def load_contract(
        self,
        contract: UpstoxOptionContract,
        *,
        signal_time: datetime,
        end_time: datetime | None = None,
        interval: str = "5minute",
    ) -> list[HistoricalOptionBar]:
        signal_time = normalize_datetime(signal_time)
        if end_time is not None:
            end_time = normalize_datetime(end_time)

        expiry_date = date.fromisoformat(contract.expiry)
        end_date = min(expiry_date, end_time.date() if end_time else expiry_date)
        start_date = signal_time.date()
        if end_date < start_date:
            return []

        rows: list[HistoricalOptionBar] = []
        for candle in self._bars_cached(contract.instrument_key, start_date, end_date, interval):
            candle_time = normalize_datetime(candle.timestamp)
            if candle_time < signal_time:
                continue
            if end_time is not None and candle_time > end_time:
                continue
            rows.append(
                HistoricalOptionBar(
                    timestamp=candle_time,
                    contract_key=contract.instrument_key,
                    underlying_symbol=contract.underlying_symbol,
                    expiry=contract.expiry,
                    strike=contract.strike,
                    option_type=contract.option_type,
                    open=float(candle.open),
                    high=float(candle.high),
                    low=float(candle.low),
                    close=float(candle.close),
                    volume=int(candle.volume or 0),
                    open_interest=int(candle.open_interest or 0),
                    bid=None,
                    ask=None,
                    underlying_close=None,
                )
            )
        return sorted(rows, key=lambda x: (x.timestamp, x.contract_key))


def clear_upstox_cache() -> None:
    _cached_expiries.cache_clear()
    _cached_contracts.cache_clear()
    _cached_bars.cache_clear()


def upstox_cache_info() -> dict[str, Any]:
    return {
        "expiries": _cached_expiries.cache_info(),
        "contracts": _cached_contracts.cache_info(),
        "bars": _cached_bars.cache_info(),
    }