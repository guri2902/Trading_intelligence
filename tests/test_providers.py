from datetime import date

from backend.app.providers.nse import NSEOptionChainProvider
from backend.app.providers.tradingview import TradingViewMCPProvider


def test_nse_fails_closed_without_fake_data():
    result = NSEOptionChainProvider().option_chain(
        "NSE_INDEX|Nifty 50",
        date(2026, 9, 10),
    )
    assert result.status == "UNAVAILABLE"
    assert result.quotes == []


def test_tradingview_is_optional():
    result = TradingViewMCPProvider(base_url=None).health()
    assert result.available is False
