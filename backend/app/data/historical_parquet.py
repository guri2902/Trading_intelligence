from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
import os

import duckdb

from ..options_backtest.models import HistoricalOptionBar


@dataclass(frozen=True)
class HistoricalQuery:
    symbol: str
    from_date: date | None = None
    to_date: date | None = None
    expiry: date | None = None
    strike: float | None = None
    side: str | None = None


class HistoricalParquetDataService:
    """Reads the user's authorized historical Parquet data.

    The storage root is configurable so the same code works with:
      - a local development directory; or
      - a Google Drive for Desktop streamed directory such as
        G:\\My Drive\\TradingData\\Historical.

    The service never fabricates market data and only reads files that exist
    beneath the configured root.
    """

    def __init__(self, root_dir: str | None = None) -> None:
        configured = (
            root_dir
            or os.getenv("HISTORICAL_DATA_ROOT")
            or os.getenv("OPTIONVAULT_ROOT")
            or "data/optionvault"
        )
        self.root_dir = Path(configured).expanduser()

    def health(self) -> dict[str, Any]:
        files = self._option_files()
        return {
            "root": str(self.root_dir),
            "root_exists": self.root_dir.exists() and self.root_dir.is_dir(),
            "option_parquet_files": len(files),
        }

    def _option_files(self, symbol: str | None = None) -> list[Path]:
        if not self.root_dir.exists():
            return []

        symbol_token = symbol.upper().replace(" ", "") if symbol else None
        files: list[Path] = []
        for path in self.root_dir.rglob("*.parquet"):
            rel = path.as_posix().upper()
            if "/OPTIONS/" not in rel:
                continue
            if symbol_token and f"/{symbol_token}/" not in rel and not path.name.upper().startswith(f"{symbol_token}_"):
                continue
            files.append(path)
        return sorted(files)

    @staticmethod
    def _sql_literal(value: str) -> str:
        return value.replace("'", "''")

    def query_options(self, query: HistoricalQuery) -> list[dict[str, Any]]:
        files = self._option_files(query.symbol)
        if not files:
            return []

        con = duckdb.connect(database=":memory:")
        try:
            file_list = ",".join(
                "'" + self._sql_literal(str(p)) + "'" for p in files
            )
            filters: list[str] = []
            if query.from_date:
                filters.append(f"CAST(datetime AS DATE) >= DATE '{query.from_date.isoformat()}'")
            if query.to_date:
                filters.append(f"CAST(datetime AS DATE) <= DATE '{query.to_date.isoformat()}'")
            if query.expiry:
                filters.append(f"CAST(expiry AS DATE) = DATE '{query.expiry.isoformat()}'")
            if query.strike is not None:
                filters.append(f"CAST(strike AS DOUBLE) = {float(query.strike)}")
            if query.side:
                side = self._sql_literal(query.side.upper())
                filters.append(f"UPPER(CAST(side AS VARCHAR)) = '{side}'")

            where_sql = " AND ".join(filters) if filters else "TRUE"
            sql = f"""
                SELECT *
                FROM read_parquet([{file_list}], union_by_name=true)
                WHERE {where_sql}
                QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY symbol, datetime, expiry, strike, side
                    ORDER BY datetime
                ) = 1
                ORDER BY datetime, symbol, strike, side
            """
            rows = con.execute(sql).fetchdf().to_dict(orient="records")
            return [self._normalize_row(r) for r in rows]
        finally:
            con.close()

    @staticmethod
    def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        ts = out.get("datetime")
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        if isinstance(ts, datetime) and ts.tzinfo is None:
            out["datetime"] = ts.replace(tzinfo=None)
        elif isinstance(ts, datetime):
            out["datetime"] = ts
        else:
            out["datetime"] = datetime.fromisoformat(str(ts))

        if hasattr(out.get("expiry"), "date"):
            out["expiry"] = out["expiry"].date()
        else:
            out["expiry"] = date.fromisoformat(str(out["expiry"])[:10])
        return out

    def option_bars(self, query: HistoricalQuery) -> list[HistoricalOptionBar]:
        rows = self.query_options(query)
        return [
            HistoricalOptionBar(
                timestamp=row["datetime"],
                contract_key=str(row["symbol"]),
                underlying_symbol=str(row.get("name") or query.symbol),
                expiry=row["expiry"].isoformat(),
                strike=float(row["strike"]),
                option_type=str(row["side"]).upper(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]) if row.get("volume") is not None else None,
                open_interest=int(row["oi"]) if row.get("oi") is not None else None,
                bid=None,
                ask=None,
            )
            for row in rows
        ]
