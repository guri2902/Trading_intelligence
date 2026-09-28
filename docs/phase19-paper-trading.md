# Phase 19 — Paper Trading

Simulation-only execution built on the platform's signal/risk layers. It never calls a broker and `live_execution` is permanently reported as false by this phase.

## Lifecycle
1. Create a named paper account with starting equity.
2. Open a position from an already-approved BUY_CE/BUY_PE plan.
3. Mark the option price from a live/historical feed.
4. Automatically close on stop loss or target 1/2.
5. Or explicitly close a position.
6. Account P&L and trade statistics are reconstructed from persistent `paper_trades` rows.

## Conservative semantics
- Long option P&L = `(exit/mark - entry) * quantity`.
- Stop is checked before targets when a mark crosses multiple thresholds.
- No partial fills, slippage, brokerage or spread modeling yet; those belong in the later execution-simulation phase.
- No short option positions.
