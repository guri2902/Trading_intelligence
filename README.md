# Trading Intelligence Platform — Phase 2

This package adds the data-provider and data-quality boundary to Phase 1.

### Start

```bash
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Main endpoints

- `/health`
- `/market/candles`
- `/option-chain`

### Configuration

Copy `.env.example` to `.env` and set `UPSTOX_ACCESS_TOKEN` only on the server/development machine.

`LIVE_EXECUTION_ENABLED=false` remains the default.

### Test

From the project root:

```bash
pytest -q
```

### Important

The implementation does not claim that NSE live JSON scraping is enabled. The NSE adapter fails closed until a compliant acquisition path is configured. That is intentional.
