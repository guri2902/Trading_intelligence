from __future__ import annotations

import os
import time
from datetime import date, datetime, timezone
from typing import Any

from .base import (
    OptionChainProvider,
    OptionChainSnapshot,
    ProviderStatus,
)
from .http import HttpClient


class NSEOptionChainProvider(OptionChainProvider):
    """
    Best-effort adapter for NSE's public option-chain surface.

    This provider deliberately fails closed:
    - it does not bypass CAPTCHA/security controls;
    - it does not fabricate rows when NSE is unavailable;
    - callers must treat UNAVAILABLE as a hard data-quality condition.
    """

    name = "nse"

    def __init__(self, timeout_seconds: float = 12.0) -> None:
        self.http = HttpClient(timeout_seconds=timeout_seconds)
        self.base_url = "https://www.nseindia.com"

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json,text/plain,*/*",
            "User-Agent": os.getenv(
                "NSE_USER_AGENT",
                "TradingIntelligencePlatform/phase2",
            ),
            "Referer": "https://www.nseindia.com/option-chain",
        }

    def health(self) -> ProviderStatus:
        checked_at = datetime.now(timezone.utc)
        try:
            started = time.perf_counter()
            response = self.http.request(
                "GET",
                self.base_url,
                headers=self._headers(),
            )
            latency = (time.perf_counter() - started) * 1000
            return ProviderStatus(
                provider=self.name,
                available=True,
                authenticated=False,
                latency_ms=latency,
                checked_at=checked_at,
                message=f"HTTP {response.status_code}",
            )
        except Exception as exc:
            return ProviderStatus(
                provider=self.name,
                available=False,
                checked_at=checked_at,
                message=str(exc),
            )

    def option_chain(
        self,
        underlying_key: str,
        expiry_date: date | None = None,
    ) -> OptionChainSnapshot:
        # NSE's live page is dynamic. Keep this adapter conservative until a
        # compliant JSON/CSV acquisition path is explicitly configured.
        return OptionChainSnapshot(
            underlying_key=underlying_key,
            timestamp=datetime.now(timezone.utc),
            source=self.name,
            status="UNAVAILABLE",
            reason=(
                "NSE option-chain acquisition is not configured in Phase 2. "
                "No fallback/fabricated data is returned."
            ),
        )
