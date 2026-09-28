# Phase 21 — Historical Options Backtesting

Phase 21 adds a dedicated backtest path that uses **actual historical option bars**. It never synthesizes an option premium from the underlying index price.

## Supported inputs
- timestamp
- real contract key
- underlying symbol
- expiry
- strike
- CE/PE
- OHLC
- optional volume/OI/bid/ask

## Execution model
Signals are evaluated using bars strictly before the decision timestamp. The selected real contract is executed only on a later historical bar, with configurable latency and slippage.

## Costs
Brokerage, exchange transaction charges, SEBI turnover charge, GST, stamp duty, STT and slippage are configurable.

## Safety
Missing contract bars are skipped and recorded as warnings. Duplicate bars, crossed bid/ask, invalid OHLC and lookahead are rejected. Live order execution is not part of this phase.

## API
- `GET /phase21/health`
- `POST /phase21/backtest`
