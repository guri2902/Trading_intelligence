# Phase 29 — Frontend / End-to-End Integration

The cumulative backend is now paired with a Next.js/React frontend.

## Pages
/, /scanner, /option-chain, /analysis, /ai-analysis, /backtest,
/strategies, /paper, /history, /risk, /settings

## Design
Warm cream / paper / muted charcoal / soft brown editorial visual system.
No neon, crypto-style gradients, or execution-forward UI.

## Integration rules
- Backend remains the authoritative calculation source.
- Broker credentials never belong in `NEXT_PUBLIC_*` browser variables.
- The UI must not fabricate a signal when live data is missing.
- Execution remains disabled.
- Backend CORS is restricted by FRONTEND_ORIGINS.
- The UI is ready to be populated with the Phase 4–28 APIs.
