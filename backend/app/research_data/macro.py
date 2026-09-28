from __future__ import annotations

from datetime import datetime, timezone

from .models import NewsMacroSnapshot, SourceAttribution


class MacroResearchAdapter:
    """
    Optional OpenBB macro adapter.

    It returns sourced raw macro context without inventing a directional score.
    """

    def __init__(self, provider: str | None = None):
        self.provider = provider

    def health(self):
        try:
            from openbb import obb
            return {
                "available": True,
                "provider": self.provider,
                "coverage": getattr(obb.coverage, "providers", None) is not None,
            }
        except Exception as exc:
            return {"available": False, "error": str(exc)}

    def indicator(self, symbol: str, country: str | None = None):
        from openbb import obb

        now = datetime.now(timezone.utc)
        result = obb.economy.indicators(
            symbol=symbol,
            country=country,
            provider=self.provider,
        )
        rows = getattr(result, "results", result)

        source = SourceAttribution(
            source="OpenBB",
            source_type="macro_connector",
            retrieved_at=now,
            provider=self.provider,
            confidence=1.0 if rows else 0.0,
        )

        return {
            "indicator": symbol,
            "country": country,
            "retrieved_at": now.isoformat(),
            "rows": [
                x.model_dump() if hasattr(x, "model_dump") else x
                for x in (rows or [])
            ],
            "source": source.model_dump(mode="json"),
        }
