from __future__ import annotations

import os
from datetime import datetime, timezone

from .base import ProviderStatus


class TradingViewMCPProvider:
    """
    Optional chart-context connector.

    Phase 2 does not depend on TradingView for authoritative quotes.
    Configure a local MCP/REST bridge separately and use this provider only
    for chart context, screenshots, or supplemental analysis.
    """

    name = "tradingview_mcp"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or os.getenv("TRADINGVIEW_MCP_BASE_URL")

    def health(self) -> ProviderStatus:
        return ProviderStatus(
            provider=self.name,
            available=bool(self.base_url),
            checked_at=datetime.now(timezone.utc),
            message=(
                "Configured as optional chart-context provider."
                if self.base_url
                else "TRADINGVIEW_MCP_BASE_URL is not configured."
            ),
        )
