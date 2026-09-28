from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from ..providers.openbb_runtime import OpenBBRuntimeError, run_openbb
from .models import (
    FundamentalSnapshot,
    NewsItem,
    NewsMacroSnapshot,
    SourceAttribution,
)


class OpenBBResearchAdapter:
    """Actual OpenBB research integration.

    Queries are executed through the OpenBB Python interface in a subprocess,
    keeping main-interpreter signal handling isolated from FastAPI worker threads.
    """

    name = "openbb"

    def __init__(self, provider: str | None = None):
        self.provider = provider or os.getenv("OPENBB_PROVIDER") or None

    @staticmethod
    def _require_openbb() -> None:
        from ..providers.openbb_runtime import check_openbb
        status = check_openbb()
        if not status["available"]:
            raise RuntimeError(status["message"])

    def _query(self, target: str, **kwargs: Any) -> Any:
        if self.provider:
            kwargs["provider"] = self.provider
        try:
            return run_openbb(target, kwargs)
        except OpenBBRuntimeError as exc:
            raise RuntimeError(f"OpenBB query {target} failed: {exc}") from exc

    def fundamentals(self, symbol: str) -> FundamentalSnapshot:
        self._require_openbb()
        now = datetime.now(timezone.utc)
        rows = self._query(
            "equity.fundamental.metrics",
            symbol=symbol,
            period="annual",
            ttm="only",
        )
        if isinstance(rows, dict):
            rows = [rows]
        row = rows[0] if rows else None

        wanted = (
            "market_cap", "enterprise_value", "pe_ratio", "forward_pe", "eps",
            "price_to_book", "price_to_sales", "ev_to_ebitda", "debt_to_equity",
            "current_ratio", "gross_margin", "operating_margin", "profit_margin",
            "return_on_equity", "return_on_assets", "revenue_growth", "eps_growth",
            "net_income_growth", "free_cash_flow_yield", "beta", "last_price",
            "year_high", "year_low", "volume_avg",
        )
        metrics: dict[str, float | str | None] = {}
        if row:
            for key in wanted:
                if key in row:
                    metrics[key] = row[key]

        source = SourceAttribution(
            source="OpenBB",
            source_type="research_connector",
            retrieved_at=now,
            provider=self.provider,
            confidence=1.0 if row else 0.0,
        )
        return FundamentalSnapshot(
            symbol=symbol,
            timestamp=now,
            score=0.0,
            confidence=1.0 if row else 0.0,
            summary="OpenBB fundamental metrics retrieved; directional scoring remains downstream and evidence-based.",
            metrics=metrics,
            risks=[],
            sources=[source],
        )

    def company_news(self, symbol: str, *, limit: int = 20) -> NewsMacroSnapshot:
        self._require_openbb()
        now = datetime.now(timezone.utc)
        rows = self._query("news.company", symbol=symbol, limit=limit)
        if isinstance(rows, dict):
            rows = [rows]
        items: list[NewsItem] = []
        for row in rows or []:
            ts_value = row.get("date") or row.get("datetime") or row.get("published")
            if ts_value:
                try:
                    ts = datetime.fromisoformat(str(ts_value).replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except ValueError:
                    ts = now
            else:
                ts = now
            items.append(
                NewsItem(
                    headline=str(row.get("title") or row.get("headline") or ""),
                    timestamp=ts,
                    symbol=symbol,
                    source=str(row.get("source") or "OpenBB provider"),
                    url=row.get("url"),
                    sentiment=None,
                    impact="UNKNOWN",
                )
            )

        source = SourceAttribution(
            source="OpenBB",
            source_type="news_connector",
            retrieved_at=now,
            provider=self.provider,
            confidence=1.0 if items else 0.0,
        )
        return NewsMacroSnapshot(
            symbol=symbol,
            timestamp=now,
            score=0.0,
            confidence=1.0 if items else 0.0,
            summary="OpenBB news retrieved; sentiment remains an explicit downstream evidence transform.",
            items=items,
            sources=[source],
        )

    def macro_indicator(self, symbol: str, country: str | None = None, limit: int = 10) -> dict[str, Any]:
        self._require_openbb()
        rows = self._query(
            "economy.indicators",
            symbol=symbol,
            country=country,
            limit=limit,
        )
        return {
            "indicator": symbol,
            "country": country,
            "rows": rows if isinstance(rows, list) else [rows],
            "source": "OpenBB",
            "provider": self.provider,
        }

    def health(self) -> dict[str, Any]:
        from ..providers.openbb_runtime import check_openbb
        result = check_openbb()
        return {
            "provider": self.name,
            "available": result["available"],
            "message": result["message"],
            "execution": "subprocess_main_interpreter",
        }
