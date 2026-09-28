from __future__ import annotations

import os
import time
from datetime import date, datetime, timezone, timedelta
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from .base import (
    Candle,
    MarketDataProvider,
    OptionChainProvider,
    OptionChainSnapshot,
    OptionQuote,
    ProviderStatus,
)
from .http import HttpClient


IST = ZoneInfo("Asia/Kolkata")
UPSTOX_BASE_URL = "https://api.upstox.com"


class UpstoxProvider(MarketDataProvider, OptionChainProvider):
    name = "upstox"

    def __init__(
        self,
        access_token: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.access_token = access_token or os.getenv("UPSTOX_ACCESS_TOKEN")
        self.http = HttpClient(timeout_seconds=timeout_seconds)

    def _headers(self) -> dict[str, str]:
        if not self.access_token:
            raise RuntimeError("UPSTOX_ACCESS_TOKEN is not configured")

        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

    def health(self) -> ProviderStatus:
        checked_at = datetime.now(timezone.utc)

        if not self.access_token:
            return ProviderStatus(
                provider=self.name,
                available=False,
                authenticated=False,
                checked_at=checked_at,
                message="UPSTOX_ACCESS_TOKEN is not configured",
            )

        return ProviderStatus(
            provider=self.name,
            available=True,
            authenticated=True,
            checked_at=checked_at,
            message="Credentials configured; live request is validated on use.",
        )

    def market_quote(self, instrument_key: str) -> tuple[float | None, datetime | None]:
        """
        Fetch a fresh exchange-derived last traded price for an instrument.

        Upstox's Full Market Quotes V3 endpoint returns a snapshot obtained
        directly from the exchange at request time. This is used as the
        canonical current underlying spot instead of relying on the
        underlying_spot_price embedded in a possibly stale option-chain row.
        """
        encoded_key = quote(instrument_key, safe="")
        url = (
            f"{UPSTOX_BASE_URL}/v3/market-quote/quotes"
            f"?instrument_key={encoded_key}"
        )

        response = self.http.request(
            "GET",
            url,
            headers=self._headers(),
        )
        payload = response.json()

        data = payload.get("data") or {}
        if not data:
            return None, None

        row = next(iter(data.values()))
        if not isinstance(row, dict):
            return None, None

        ltp = row.get("last_price")
        timestamp_raw = row.get("timestamp")

        last_price = float(ltp) if ltp is not None else None
        snapshot_ts = None
        if timestamp_raw:
            try:
                snapshot_ts = datetime.fromisoformat(
                    str(timestamp_raw).replace("Z", "+00:00")
                )
                if snapshot_ts.tzinfo is None:
                    snapshot_ts = snapshot_ts.replace(tzinfo=timezone.utc)
            except ValueError:
                snapshot_ts = None

        return last_price, snapshot_ts


    @staticmethod
    def _parse_candles(payload: dict[str, Any], instrument_key: str) -> list[Candle]:
        rows = payload.get("data", {}).get("candles", []) or []
        result: list[Candle] = []

        for row in rows:
            if len(row) < 6:
                continue

            raw_ts = str(row[0]).replace("Z", "+00:00")
            ts = datetime.fromisoformat(raw_ts)

            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            result.append(
                Candle(
                    instrument_key=instrument_key,
                    timestamp=ts,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]) if row[5] is not None else None,
                    open_interest=(
                        float(row[6])
                        if len(row) > 6 and row[6] is not None
                        else None
                    ),
                    source="upstox",
                )
            )

        return result

    def _historical_candles(
        self,
        instrument_key: str,
        unit: str,
        interval: int,
        from_date: date,
        to_date: date,
    ) -> list[Candle]:
        """Fetch historical candles using safe <=30-day windows."""

        from datetime import timedelta

        if unit == "minutes" and int(interval) <= 15:
            from calendar import monthrange

            result: list[Candle] = []
            cursor = from_date

            while cursor <= to_date:
                month_end = cursor.replace(
                    day=monthrange(cursor.year, cursor.month)[1]
                )

                chunk_to = min(to_date, month_end)

                url = (
                    f"{UPSTOX_BASE_URL}/v3/historical-candle/"
                    f"{instrument_key}/{unit}/{int(interval)}/"
                    f"{chunk_to.isoformat()}/{cursor.isoformat()}"
                )

                response = self.http.request(
                    "GET",
                    url,
                    headers=self._headers(),
                )

                chunk = self._parse_candles(
                    response.json(),
                    instrument_key,
                )

                result.extend(chunk)

                cursor = chunk_to + timedelta(days=1)

            dedup: dict[datetime, Candle] = {
                candle.timestamp: candle
                for candle in result
            }

            return sorted(
                dedup.values(),
                key=lambda candle: candle.timestamp,
            )

        url = (
            f"{UPSTOX_BASE_URL}/v3/historical-candle/"
            f"{instrument_key}/{unit}/{int(interval)}/"
            f"{to_date.isoformat()}/{from_date.isoformat()}"
        )

        response = self.http.request(
            "GET",
            url,
            headers=self._headers(),
        )

        return self._parse_candles(
            response.json(),
            instrument_key,
        )

    def _intraday_candles(
        self,
        instrument_key: str,
        unit: str,
        interval: int,
    ) -> list[Candle]:
        encoded_key = quote(instrument_key, safe="")
        url = (
            f"{UPSTOX_BASE_URL}/v3/historical-candle/intraday/"
            f"{encoded_key}/{unit}/{interval}"
        )

        response = self.http.request(
            "GET",
            url,
            headers=self._headers(),
        )

        return self._parse_candles(response.json(), instrument_key)

    def candles(
        self,
        instrument_key: str,
        unit: str,
        interval: int,
        from_date: date,
        to_date: date,
    ) -> list[Candle]:
        """
        Fetch historical or current-day candles using Upstox V3.

        - Past-only range: historical V3 endpoint.
        - Today-only range: intraday V3 endpoint.
        - Range spanning yesterday -> today: fetch both and merge.
        """
        today_ist = datetime.now(IST).date()

        if to_date < from_date:
            raise ValueError(
                f"Invalid candle range: from_date={from_date} > to_date={to_date}"
            )

        started = time.perf_counter()

        candles: list[Candle] = []

        # Historical-only range.
        if to_date < today_ist:
            candles.extend(
                self._historical_candles(
                    instrument_key,
                    unit,
                    interval,
                    from_date,
                    to_date,
                )
            )

        # Current-day-only range.
        elif from_date >= today_ist:
            candles.extend(
                self._intraday_candles(
                    instrument_key,
                    unit,
                    interval,
                )
            )

        # Mixed range: historical portion + current-day intraday portion.
        else:
            yesterday = today_ist - timedelta(days=1)

            if from_date <= yesterday:
                candles.extend(
                    self._historical_candles(
                        instrument_key,
                        unit,
                        interval,
                        from_date,
                        min(to_date, yesterday),
                    )
                )

            candles.extend(
                self._intraday_candles(
                    instrument_key,
                    unit,
                    interval,
                )
            )

        # Keep only the requested date window.
        filtered: list[Candle] = []
        for candle in candles:
            local_ts = candle.timestamp.astimezone(IST)
            if from_date <= local_ts.date() <= to_date:
                filtered.append(candle)

        # Stable ordering + duplicate removal by timestamp.
        unique = {c.timestamp: c for c in filtered}

        _ = (time.perf_counter() - started) * 1000

        return [unique[k] for k in sorted(unique)]

    def option_chain(
        self,
        underlying_key: str,
        expiry_date: date | None = None,
    ) -> OptionChainSnapshot:
        """
        Fetch an option-chain snapshot from Upstox.

        Upstox requires an expiry date for the option-chain endpoint. When the
        caller does not provide one, resolve the nearest available future
        expiry through the option-contracts endpoint first, then request the
        chain for that expiry.

        This keeps callers simple while preserving explicit expiry selection.
        """
        resolved_expiry = expiry_date

        if resolved_expiry is None:
            contracts = self.option_contracts(
                underlying_key=underlying_key,
                expiry_date=None,
            )

            today = datetime.now(IST).date()
            expiries: set[date] = set()

            for contract in contracts:
                raw_expiry = (
                    contract.get("expiry")
                    if isinstance(contract, dict)
                    else None
                )
                if not raw_expiry:
                    continue

                try:
                    parsed_expiry = date.fromisoformat(str(raw_expiry))
                except (TypeError, ValueError):
                    continue

                if parsed_expiry >= today:
                    expiries.add(parsed_expiry)

            if expiries:
                resolved_expiry = min(expiries)

        if resolved_expiry is None:
            # Keep the response contract honest. No HTTP 400 is generated by
            # our own provider when Upstox does not expose a usable expiry.
            now = datetime.now(timezone.utc)
            return OptionChainSnapshot(
                underlying_key=underlying_key,
                timestamp=now,
                underlying_ltp=None,
                expiry_dates=[],
                quotes=[],
                source=self.name,
                status="UNAVAILABLE",
                reason="Upstox did not expose a valid option expiry.",
            )

        url = f"{UPSTOX_BASE_URL}/v2/option/chain"

        params: dict[str, Any] = {
            "instrument_key": underlying_key,
            "expiry_date": resolved_expiry.isoformat(),
        }

        started = time.perf_counter()

        response = self.http.request(
            "GET",
            url,
            headers=self._headers(),
            params=params,
        )

        latency_ms = (time.perf_counter() - started) * 1000
        payload = response.json()
        rows = payload.get("data") or []

        # Obtain a fresh canonical spot from the exchange-derived market quote.
        # Do not trust the option-chain embedded underlying_spot_price when it
        # differs from a contemporaneous quote.
        fresh_spot, fresh_spot_timestamp = self.market_quote(underlying_key)

        quotes: list[OptionQuote] = []
        expiry_dates: set[date] = set()
        underlying_ltp: float | None = fresh_spot

        for row in rows:
            expiry_raw = row.get("expiry")
            strike_raw = row.get("strike_price")

            if not expiry_raw or strike_raw is None:
                continue

            try:
                expiry = date.fromisoformat(str(expiry_raw))
                strike = float(strike_raw)
            except (TypeError, ValueError):
                continue

            expiry_dates.add(expiry)

            for option_type, side_key in (
                ("CE", "call_options"),
                ("PE", "put_options"),
            ):
                side = row.get(side_key) or {}
                market = side.get("market_data") or {}
                greeks = side.get("option_greeks") or {}

                instrument = side.get("instrument_key")
                if not instrument:
                    continue

                try:
                    bid = (
                        float(market["bid_price"])
                        if market.get("bid_price") is not None
                        else None
                    )
                    ask = (
                        float(market["ask_price"])
                        if market.get("ask_price") is not None
                        else None
                    )
                    ltp = (
                        float(market["ltp"])
                        if market.get("ltp") is not None
                        else None
                    )
                except (TypeError, ValueError):
                    continue

                # Reject malformed quotes before they enter the canonical snapshot.
                if bid is not None and bid < 0:
                    continue

                if ask is not None and ask < 0:
                    continue

                if bid is not None and ask is not None and ask < bid:
                    continue

                current_oi = (
                    float(market["oi"])
                    if market.get("oi") is not None
                    else None
                )

                previous_oi = (
                    float(market["prev_oi"])
                    if market.get("prev_oi") is not None
                    else None
                )

                # Normalize Upstox fields so downstream consumers receive
                # actual change-in-OI rather than prev_oi under that name.
                change_in_oi = None
                if current_oi is not None and previous_oi is not None:
                    change_in_oi = current_oi - previous_oi

                def _float_or_none(value: Any) -> float | None:
                    if value is None:
                        return None
                    try:
                        return float(value)
                    except (TypeError, ValueError):
                        return None

                quotes.append(
                    OptionQuote(
                        instrument_key=str(instrument),
                        underlying_key=underlying_key,
                        expiry=expiry,
                        strike=strike,
                        option_type=option_type,
                        ltp=ltp,
                        bid=bid,
                        ask=ask,
                        bid_qty=(
                            int(market["bid_qty"])
                            if market.get("bid_qty") is not None
                            else None
                        ),
                        ask_qty=(
                            int(market["ask_qty"])
                            if market.get("ask_qty") is not None
                            else None
                        ),
                        volume=_float_or_none(market.get("volume")),
                        open_interest=current_oi,
                        change_in_oi=change_in_oi,
                        iv=_float_or_none(greeks.get("iv")),
                        delta=_float_or_none(greeks.get("delta")),
                        gamma=_float_or_none(greeks.get("gamma")),
                        theta=_float_or_none(greeks.get("theta")),
                        vega=_float_or_none(greeks.get("vega")),
                        rho=_float_or_none(greeks.get("rho")),
                        source=self.name,
                    )
                )

        # Upstox option-chain response does not provide a per-row snapshot
        # timestamp that we can use as the market event timestamp here.
        # Use the UTC time immediately after the response was received.
        snapshot_timestamp = fresh_spot_timestamp or datetime.now(timezone.utc)

        status = "OK" if quotes else "UNAVAILABLE"
        reason = "" if quotes else "Upstox returned no option-chain rows."

        snapshot = OptionChainSnapshot(
            underlying_key=underlying_key,
            timestamp=snapshot_timestamp,
            underlying_ltp=underlying_ltp,
            expiry_dates=sorted(expiry_dates),
            quotes=quotes,
            source=self.name,
            status=status,
            reason=reason,
        )

        snapshot.model_dump(mode="json")

        _ = latency_ms

        return snapshot

    def expired_expiries(self, underlying_key: str) -> list[date]:
        """Return historical option expiries exposed by Upstox."""
        encoded_key = quote(underlying_key, safe="")
        url = (
            f"{UPSTOX_BASE_URL}/v2/expired-instruments/expiries"
            f"?instrument_key={encoded_key}"
        )
        response = self.http.request(
            "GET",
            url,
            headers=self._headers(),
        )
        values = response.json().get("data") or []
        out: list[date] = []
        for value in values:
            try:
                out.append(date.fromisoformat(str(value)))
            except (TypeError, ValueError):
                continue
        return sorted(set(out))

    def expired_option_contracts(
        self,
        underlying_key: str,
        expiry_date: date,
    ) -> list[dict[str, Any]]:
        """Return real expired option contracts for one expiry."""
        encoded_key = quote(underlying_key, safe="")
        url = (
            f"{UPSTOX_BASE_URL}/v2/expired-instruments/option/contract"
            f"?instrument_key={encoded_key}"
            f"&expiry_date={expiry_date.isoformat()}"
        )
        response = self.http.request(
            "GET",
            url,
            headers=self._headers(),
        )
        return response.json().get("data") or []

    def expired_historical_candles(
        self,
        expired_instrument_key: str,
        interval: str,
        from_date: date,
        to_date: date,
    ) -> list[Candle]:
        """Fetch actual historical candles for an expired derivative contract."""
        if to_date < from_date:
            raise ValueError(
                f"Invalid expired candle range: from_date={from_date} > to_date={to_date}"
            )
        allowed = {"1minute", "3minute", "5minute", "15minute", "30minute", "day"}
        if interval not in allowed:
            raise ValueError(f"UPSTOX_EXPIRED_INTERVAL_UNSUPPORTED:{interval}")

        encoded_key = quote(expired_instrument_key, safe="")
        url = (
            f"{UPSTOX_BASE_URL}/v2/expired-instruments/historical-candle/"
            f"{encoded_key}/{interval}/{to_date.isoformat()}/{from_date.isoformat()}"
        )
        response = self.http.request(
            "GET",
            url,
            headers=self._headers(),
        )
        return self._parse_candles(response.json(), expired_instrument_key)

    def option_contracts(
        self,
        underlying_key: str,
        expiry_date: date | None = None,
    ) -> list[dict[str, Any]]:
        url = f"{UPSTOX_BASE_URL}/v2/option/contract"

        params: dict[str, Any] = {
            "instrument_key": underlying_key,
        }

        if expiry_date is not None:
            params["expiry_date"] = expiry_date.isoformat()

        response = self.http.request(
            "GET",
            url,
            headers=self._headers(),
            params=params,
        )

        return response.json().get("data") or []
