# Phase 20 — Realistic Paper Execution

Adds a broker-neutral microstructure simulator on top of Phase 19 paper trading.

## Scope
- Bid/ask-aware fills
- Configurable bps slippage
- Liquidity-driven partial fills
- Latency metadata
- Brokerage, exchange transaction charges, SEBI turnover charge, STT, stamp duty and GST as configurable rates
- Expiry intrinsic-value settlement for long CE/PE when underlying LTP is supplied
- Entry/exit cost persistence and net P&L attribution

## Safety
- No broker calls
- No live order placement
- All charge rates are configuration defaults and must be verified against the chosen broker/exchange schedule before production use
- Expiry settlement requires underlying LTP; otherwise the engine fails closed

## APIs
- `GET /phase20/health`
- `POST /phase20/fill`
- `POST /phase20/costs`
- `POST /phase20/expiry-value`
