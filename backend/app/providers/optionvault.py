from __future__ import annotations

import csv
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .base import Candle, MarketDataProvider, ProviderStatus


SUPPORTED = {".csv", ".parquet", ".feather"}


class OptionVaultProvider(MarketDataProvider):
    """Adapter for the real OptionVault repository/data layout.

    It discovers actual local files recursively and supports the repository's
    documented fields such as datetime, OHLC, volume, oi, expiry, strike and side.
    Missing datasets are reported honestly; no synthetic coverage is generated.
    """

    name = "optionvault"

    def __init__(self, root_dir: str | None = None) -> None:
        self.root_dir = Path(
            root_dir
            or os.getenv("OPTIONVAULT_ROOT")
            or "data/optionvault"
        ).expanduser()
        self._files_cache: list[Path] | None = None

    @property
    def exists(self) -> bool:
        return self.root_dir.exists() and self.root_dir.is_dir()

    def _files(self) -> list[Path]:
        if self._files_cache is None:
            if not self.exists:
                self._files_cache = []
            else:
                self._files_cache = sorted(
                    p for p in self.root_dir.rglob("*")
                    if p.is_file() and p.suffix.lower() in SUPPORTED
                )
        return self._files_cache

    def health(self) -> ProviderStatus:
        files = self._files()
        exists = self.exists
        return ProviderStatus(
            provider=self.name,
            available=bool(files),
            authenticated=False,
            checked_at=datetime.now(timezone.utc),
            message=(
                "OptionVault dataset discovered."
                if files
                else f"OptionVault dataset not found or empty: {self.root_dir}"
            ),
            metadata={
                "root": str(self.root_dir),
                "root_exists": exists,
                "file_count": len(files),
                "samples_dir": str(self.root_dir / "samples"),
                "samples_present": (self.root_dir / "samples").exists(),
            },
        )

    def coverage(self) -> dict[str, Any]:
        files = self._files()
        categories: dict[str, int] = {}
        samples: list[str] = []
        for path in files:
            rel = path.relative_to(self.root_dir).as_posix()
            top = rel.split("/", 1)[0] if "/" in rel else "root"
            categories[top] = categories.get(top, 0) + 1
            if len(samples) < 25:
                samples.append(rel)
        return {
            "root": str(self.root_dir),
            "root_exists": self.exists,
            "file_count": len(files),
            "categories": categories,
            "sample_files": samples,
        }

    def _candidate_files(self, instrument_key: str, *, options: bool = False) -> Iterator[Path]:
        tokens = [
            t.strip().upper().replace(" ", "")
            for t in instrument_key.replace("|", "_").replace("/", "_").split("_")
            if t.strip()
        ]
        primary = tokens[-1] if tokens else instrument_key.upper()
        for path in self._files():
            rel = path.as_posix().upper()
            stem = path.stem.upper().replace(" ", "")
            if options and "/OPTIONS/" not in rel and "/DERIVATIVES/" not in rel:
                continue
            if primary in stem or any(t in stem for t in tokens if len(t) >= 3):
                yield path

    @staticmethod
    def _row_value(row: dict[str, Any], *names: str) -> Any:
        lowered = {str(k).strip().lower(): v for k, v in row.items()}
        for name in names:
            if name in lowered:
                return lowered[name]
        return None

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        if value is None:
            raise ValueError("Missing timestamp/datetime field")
        text = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    @staticmethod
    def _read_table(path: Path) -> list[dict[str, Any]]:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            with path.open("r", newline="", encoding="utf-8-sig") as fh:
                return list(csv.DictReader(fh))
        try:
            import pandas as pd  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "OptionVault parquet/feather support requires pandas. "
                "CSV samples work without the optional dependency."
            ) from exc
        if suffix == ".parquet":
            return pd.read_parquet(path).to_dict(orient="records")
        return pd.read_feather(path).to_dict(orient="records")

    def candles(
        self,
        instrument_key,
        unit,
        interval,
        from_date,
        to_date,
    ) -> list[Candle]:
        rows: dict[datetime, Candle] = {}
        candidates = list(self._candidate_files(instrument_key))

        for path in candidates:
            for row in self._read_table(path):
                ts = self._parse_timestamp(
                    self._row_value(row, "datetime", "timestamp", "date")
                )
                if not (from_date <= ts.date() <= to_date):
                    continue
                op = self._row_value(row, "open", "o")
                hi = self._row_value(row, "high", "h")
                lo = self._row_value(row, "low", "l")
                cl = self._row_value(row, "close", "c")
                if None in (op, hi, lo, cl):
                    continue
                vol = self._row_value(row, "volume", "v")
                oi = self._row_value(row, "oi", "open_interest")
                rows[ts] = Candle(
                    instrument_key=instrument_key,
                    timestamp=ts,
                    open=float(op),
                    high=float(hi),
                    low=float(lo),
                    close=float(cl),
                    volume=float(vol) if vol not in (None, "") else None,
                    open_interest=float(oi) if oi not in (None, "") else None,
                    source=self.name,
                )

        return sorted(rows.values(), key=lambda x: x.timestamp)

    def option_series(
        self,
        symbol: str,
        *,
        expiry: date | None = None,
        strike: float | None = None,
        side: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Load actual option market rows when the local OptionVault data exists."""
        out: list[dict[str, Any]] = []
        symbol_upper = symbol.upper().replace(" ", "")
        side_upper = side.upper() if side else None

        for path in self._candidate_files(symbol, options=True):
            if symbol_upper not in path.stem.upper().replace(" ", ""):
                continue
            for row in self._read_table(path):
                exp_value = self._row_value(row, "expiry", "exp")
                row_strike = self._row_value(row, "strike", "strike_price")
                row_side = self._row_value(row, "side", "option_type", "type")

                if expiry is not None and exp_value not in (None, ""):
                    try:
                        exp = date.fromisoformat(str(exp_value)[:10])
                    except ValueError:
                        exp = None
                    if exp is not None and exp != expiry:
                        continue
                if strike is not None and row_strike not in (None, ""):
                    if float(row_strike) != float(strike):
                        continue
                if side_upper and row_side not in (None, ""):
                    if str(row_side).upper() != side_upper:
                        continue

                ts = self._parse_timestamp(self._row_value(row, "datetime", "timestamp", "date"))
                if from_date and ts.date() < from_date:
                    continue
                if to_date and ts.date() > to_date:
                    continue

                normalized = {str(k).strip().lower(): v for k, v in row.items()}
                normalized["timestamp"] = ts.isoformat()
                normalized["source"] = self.name
                out.append(normalized)

        out.sort(key=lambda x: x["timestamp"])
        return out
