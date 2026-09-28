# Phase 29 — OpenBB + OptionVault integration

This integration keeps **Upstox as the live Indian market source**, adds **OpenBB as the actual research/data abstraction layer**, and adds **OptionVault as the historical local dataset provider**.

## OpenBB

The project already declares `openbb>=4,<5` in `backend/requirements.txt`.
Install dependencies from the project environment:

```powershell
pip install -r backend\requirements.txt
```

The adapter executes OpenBB calls in a child Python process. This avoids the `signal only works in main thread of the main interpreter` failure observed when OpenBB is touched from a FastAPI worker thread.

Supported paths:

- `OpenBBProvider.candles()` → `obb.equity.price.historical`
- `OpenBBResearchAdapter.fundamentals()` → `obb.equity.fundamental.metrics`
- `OpenBBResearchAdapter.company_news()` → `obb.news.company`
- `OpenBBResearchAdapter.macro_indicator()` → `obb.economy.indicators`

Optional configuration:

```env
OPENBB_PROVIDER=
OPENBB_SYMBOL_SUFFIX=
```

For example, when using a provider that expects NSE-style Yahoo symbols:

```env
OPENBB_PROVIDER=yfinance
OPENBB_SYMBOL_SUFFIX=.NS
```

Do not use OpenBB as the authoritative live options feed. Live market/options data remains Upstox.

## OptionVault

Point `OPTIONVAULT_ROOT` at the root of the downloaded OptionVault dataset or a repository checkout containing the `samples/` directory:

```env
OPTIONVAULT_ROOT=./data/optionvault
```

The adapter discovers `.csv`, `.parquet`, and `.feather` files recursively and understands the documented OptionVault fields such as:

- `datetime`
- `open`, `high`, `low`, `close`
- `volume`
- `oi`
- `expiry`
- `strike`
- `side`

No files are created automatically and no missing historical coverage is fabricated.

Useful endpoints:

```text
GET /providers/health
GET /providers/openbb/health
GET /providers/optionvault/health
GET /providers/optionvault/coverage
POST /phase14/openbb/research
```

## Provider status semantics

`available=true` means the actual dependency/data source was discovered and can be used.

`available=false` means the dependency or dataset is unavailable; this is a real status, not an artificial green state.
