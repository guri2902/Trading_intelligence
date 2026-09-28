# Phase 18 — Portfolio Risk & Position Sizing

Phase 18 sits after signal fusion and before any future execution adapter.

## Guarantees
- No order is submitted by the risk engine.
- Risk is computed from equity and premium entry-to-stop distance.
- Quantity is rounded down to complete option lots.
- Daily loss and daily profit lock can hard-block new trades.
- Concurrent open risk, maximum trades and maximum open positions can block new trades.
- Peak-equity drawdown can hard-block new trades.
- Optional square-off time can block new entries once reached.
- Missing entry, stop or lot size is fail-closed.

## Formula
`risk_budget = equity × risk_per_trade_pct`

When configured, risk budget is capped by remaining daily-loss capacity and remaining concurrent-risk capacity.

`unit_risk = abs(entry - stop_loss)`

`lots = floor(risk_budget / unit_risk / lot_size)`

`quantity = lots × lot_size`

`estimated_trade_risk = quantity × unit_risk`

## API
`GET /phase18/health`

`POST /phase18/risk-check`

The endpoint runs the existing deterministic/LLM-advisory pipeline, obtains the Phase 17 signal, then applies Phase 18 portfolio risk. Live execution remains disabled.
