from __future__ import annotations

from dataclasses import dataclass

from .costs import apply_slippage


@dataclass
class Fill:
    price: float
    quantity: float


def simulate_fill(
    *,
    requested_price: float,
    direction: str,
    quantity: float,
    slippage_bps: float,
    partial_fill_ratio: float,
) -> Fill:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if not 0 < partial_fill_ratio <= 1:
        raise ValueError("partial_fill_ratio must be in (0,1]")

    filled_qty = quantity * partial_fill_ratio

    return Fill(
        price=apply_slippage(
            requested_price,
            direction,
            slippage_bps,
        ),
        quantity=filled_qty,
    )
