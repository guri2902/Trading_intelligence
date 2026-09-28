from __future__ import annotations

import gzip
import json
import os
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

import requests

from .models import InstrumentRecord
from .repository import sync_records
from ..db.session import SessionLocal


UPSTOX_COMPLETE_BOD_URL = (
    "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
)


class UpstoxInstrumentMaster:
    """
    Downloads and normalizes Upstox's official BOD instrument master.

    The source file is gzipped JSON. It is intentionally downloaded to a
    temporary file so large instrument masters are not loaded into memory twice.
    """

    def __init__(
        self,
        url: str = UPSTOX_COMPLETE_BOD_URL,
        cache_dir: str | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.url = url
        self.cache_dir = Path(cache_dir or "data/instrument_master")
        self.timeout_seconds = timeout_seconds

    def download(self) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = self.cache_dir / f"upstox_complete_{stamp}.json.gz"

        with requests.get(
            self.url,
            stream=True,
            timeout=self.timeout_seconds,
            headers={"Accept": "application/gzip,application/octet-stream,*/*"},
        ) as response:
            response.raise_for_status()
            with target.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)

        if target.stat().st_size < 1024:
            target.unlink(missing_ok=True)
            raise RuntimeError("Downloaded Upstox instrument master is unexpectedly small")

        return target

    def iter_rows(self, path: Path) -> Iterator[dict[str, Any]]:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            data = json.load(fh)

        if not isinstance(data, list):
            raise ValueError("Expected Upstox instrument master JSON array")

        for row in data:
            if isinstance(row, dict):
                yield row

    @staticmethod
    def _parse_epoch_ms(value: Any) -> date | None:
        if value in (None, "", 0):
            return None
        try:
            return datetime.fromtimestamp(
                float(value) / 1000,
                tz=timezone.utc,
            ).date()
        except (TypeError, ValueError, OSError):
            return None

    @classmethod
    def to_record(cls, row: dict[str, Any]) -> InstrumentRecord | None:
        segment = str(row.get("segment") or "")
        exchange = str(row.get("exchange") or "")
        instrument_type = str(row.get("instrument_type") or "").upper()
        source_key = str(row.get("instrument_key") or "")

        if not source_key or not segment or not exchange or not instrument_type:
            return None

        symbol = str(row.get("trading_symbol") or row.get("name") or "")
        underlying_symbol = row.get("underlying_symbol")
        underlying_key = row.get("underlying_key")

        expiry = cls._parse_epoch_ms(row.get("expiry"))
        strike_raw = row.get("strike_price")
        strike = None
        if strike_raw not in (None, ""):
            strike = Decimal(str(strike_raw))

        option_type = (
            instrument_type if instrument_type in {"CE", "PE"} else None
        )

        # For options/futures, the canonical trading symbol is the underlying;
        # the source key remains the authoritative vendor alias.
        canonical_symbol = str(underlying_symbol or symbol)

        canonical_key = "|".join(
            [
                exchange.upper(),
                segment.upper(),
                canonical_symbol.upper().strip(),
                instrument_type,
                expiry.isoformat() if expiry else "-",
                str(strike.normalize()) if strike is not None else "-",
                option_type or "-",
            ]
        )

        lot_raw = row.get("lot_size") or row.get("minimum_lot")
        lot_size = int(lot_raw) if lot_raw not in (None, "") else None

        tick_raw = row.get("tick_size")
        tick_size = (
            Decimal(str(tick_raw))
            if tick_raw not in (None, "")
            else None
        )

        return InstrumentRecord(
            instrument_key=canonical_key,
            exchange=exchange,
            segment=segment,
            instrument_type=instrument_type,
            trading_symbol=symbol,
            underlying_key=str(underlying_key) if underlying_key else None,
            underlying_symbol=(
                str(underlying_symbol)
                if underlying_symbol
                else None
            ),
            expiry_date=expiry,
            strike=strike,
            option_type=option_type,
            lot_size=lot_size,
            tick_size=tick_size,
            source="upstox",
            source_updated_at=datetime.now(timezone.utc),
        )

    def sync(
        self,
        *,
        source_path: Path | None = None,
        segments: set[str] | None = None,
        instrument_types: set[str] | None = None,
        underlying_symbols: set[str] | None = None,
        only_future_expiry: bool = True,
        persist: bool = True,
    ) -> dict[str, Any]:
        path = source_path or self.download()

        normalized: list[InstrumentRecord] = []
        skipped = 0
        source_rows = 0

        today = datetime.now(timezone.utc).date()

        for row in self.iter_rows(path):
            source_rows += 1

            segment = str(row.get("segment") or "").upper()
            itype = str(row.get("instrument_type") or "").upper()
            underlying = str(
                row.get("underlying_symbol")
                or row.get("trading_symbol")
                or ""
            ).upper()

            if segments and segment not in {x.upper() for x in segments}:
                continue
            if instrument_types and itype not in {x.upper() for x in instrument_types}:
                continue
            if underlying_symbols and underlying not in {
                x.upper() for x in underlying_symbols
            }:
                continue

            record = self.to_record(row)
            if record is None:
                skipped += 1
                continue

            if only_future_expiry and record.expiry_date and record.expiry_date < today:
                continue

            normalized.append(record)

        synced = 0
        if persist and normalized:
            with SessionLocal() as db:
                synced = sync_records(db, normalized)

        return {
            "source": "upstox",
            "source_file": str(path),
            "source_rows": source_rows,
            "normalized": len(normalized),
            "skipped": skipped,
            "synced": synced,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "segments": sorted(segments) if segments else None,
            "instrument_types": sorted(instrument_types) if instrument_types else None,
            "underlyings": sorted(underlying_symbols) if underlying_symbols else None,
        }


def default_nse_index_and_fo_filters() -> dict[str, set[str]]:
    return {
        "segments": {"NSE_INDEX", "NSE_FO"},
        "instrument_types": {"INDEX", "FUT", "CE", "PE"},
        "underlying_symbols": {"NIFTY", "BANKNIFTY", "NIFTY BANK", "NIFTY 50"},
    }
