from __future__ import annotations

import os

from .nse import NSEOptionChainProvider
from .openbb import OpenBBProvider
from .optionvault import OptionVaultProvider
from .tradingview import TradingViewMCPProvider
from .upstox import UpstoxProvider


def build_registry() -> dict[str, object]:
    return {
        "upstox": UpstoxProvider(),
        "nse": NSEOptionChainProvider(),
        "optionvault": OptionVaultProvider(
            root_dir=os.getenv("OPTIONVAULT_ROOT", "data/optionvault")
        ),
        "openbb": OpenBBProvider(
            provider_name=os.getenv("OPENBB_PROVIDER") or None
        ),
        "tradingview_mcp": TradingViewMCPProvider(),
    }
