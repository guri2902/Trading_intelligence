# Phase 16G — Final Integration & QA

## Baseline verification performed against the supplied project archive

### Backend

The project contains 47 backend test modules.

A full pytest collection was attempted.

Result:
- **142 tests passed** when the two modules that import `duckdb` are excluded.
- Full collection is currently blocked by:
  `ModuleNotFoundError: No module named 'duckdb'`
- The two affected modules are:
  - `tests/test_historical_parquet_service.py`
  - `tests/test_phase15.py`

The remaining suite was executed with:

```bash
PYTHONPATH=. pytest -q \
  --ignore=tests/test_historical_parquet_service.py \
  --ignore=tests/test_phase15.py
```

and returned:

```text
142 passed in 3.39s
```

### Frontend

The supplied archive contains Next.js 14.2.21 with TypeScript.

`node_modules` was not present. `npm ci --ignore-scripts` was attempted, but the sandbox dependency install timed out, so a fresh `next build` could not be completed here.

Therefore this phase does **not** claim a successful frontend production build.

## Integration checklist

After applying Phases 16A–16F:

- Strategies uses the Strategy Studio backend.
- Backtest uses the persisted candle layer and either the deterministic OptionVault path or the custom underlying backtest path.
- Paper Trading uses the persisted paper engine and reports `live_execution: false`.
- Option Chain and Scanner use backend UI endpoints.
- Analysis, AI Analysis and Risk use the realtime pipeline / risk engine.
- History reads persisted paper trades.
- Settings separates browser preferences from backend-owned configuration.
- The browser does not call Upstox directly.
- Missing market/backend values remain unavailable rather than being fabricated.

## Final verification to run on the user's machine

Backend:

```bash
pip install -r requirements.txt
pip install duckdb
PYTHONPATH=. pytest -q
```

Frontend:

```bash
cd frontend
npm ci
npm run build
```

Then run the app and verify these routes manually:

```text
/
 /scanner
 /option-chain
 /analysis
 /ai-analysis
 /backtest
 /strategies
 /paper
 /history
 /risk
 /settings
```

## Important

The final end-to-end build cannot honestly be marked green until:
1. `duckdb` is installed in the backend environment.
2. The frontend dependencies install successfully.
3. `next build` completes.
4. The 16A–16F files are applied to the actual working tree rather than only stored as separate phase patches.
