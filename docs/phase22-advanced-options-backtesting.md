# Phase 22 — Advanced Options Backtesting

Phase 22 extends historical options backtesting with expiry-aware, multi-leg contract portfolios.

## Scope
- Multi-leg option strategies using actual historical contract bars.
- BUY/SELL leg direction and per-leg quantity.
- Maximum-leg safety limit.
- Expiry-aware validation; bars after expiry are rejected by default.
- Expiry settlement from the contract's intrinsic value when `underlying_close` is present.
- Explicit warning when expiry settlement cannot be computed because underlying data is missing.
- No-lookahead execution with configurable latency bars.
- Bid/ask-aware fills with configurable slippage.
- Cost model inherited from the realistic execution layer.
- Live execution remains disabled.

## API
- `GET /phase22/health`
- `POST /phase22/backtest`

## Safety
The engine never invents an option premium. If a requested contract has no real execution bar, that leg is rejected. Expiry settlement requires an underlying close; otherwise the engine records a warning instead of fabricating intrinsic value.
