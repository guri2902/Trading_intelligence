# Phase 15 — Integration & QA

This is the cross-page final integration pass after Phases 1–14.

## Apply

1. Keep the existing Shell from Phase 2.
2. Keep the page files from Phases 3–13.
3. Append Phase 14 global polish.
4. Append `frontend/app/integration-qa.css.patch` to `globals.css`.
5. Apply `frontend/app/integration-qa-layout.patch` only if your root layout has a matching wrapper.
6. Run the QA checks below.

## QA checklist

### Navigation
- All sidebar destinations load without runtime exceptions.
- Active navigation state remains visible.
- Sidebar grouping remains Market Data / Research / Trading / System.
- Top market strip never displays fabricated numbers.

### Data integrity
- Missing backend values display `—`.
- Backend errors remain visible.
- No UI invents market prices, Greeks, balances, P&L, sentiment or fundamentals.
- Scanner score bars require finite numeric scores.
- Backtest metrics only use returned backend metrics.
- Paper retains `SIMULATION ONLY`.
- Risk does not invent limits.

### Theme / responsive
- Light and dark themes remain readable.
- Keyboard focus is visible.
- Tables scroll horizontally on narrow screens.
- Reduced motion is respected.
- Page-level horizontal overflow is prevented.

### Interaction
- Disabled buttons remain non-actionable.
- Filters survive normal refreshes.
- History CSV exports the currently filtered records.
- Settings persist locally.
- Compact-table preference applies globally.
- No UI implies server persistence without a confirmed backend write contract.

## Scope

Frontend-only integration and QA hardening. No backend assumptions or new API contracts are introduced.
