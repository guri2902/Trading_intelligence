import json
import sqlite3

conn = sqlite3.connect("trading_intelligence.db")

rows = conn.execute("""
SELECT
    c.timestamp,
    c.open,
    c.high,
    c.low,
    c.close,
    c.volume
FROM candles c
JOIN instruments i ON i.id = c.instrument_id
WHERE i.segment = 'NSE_INDEX'
  AND i.trading_symbol = 'NIFTY'
  AND c.timeframe = 'minutes:5'
  AND c.source = 'upstox'
ORDER BY c.timestamp
""").fetchall()

payload = {
    "rows": [
        {
            "timestamp": r[0],
            "open": r[1],
            "high": r[2],
            "low": r[3],
            "close": r[4],
            "volume": r[5],
        }
        for r in rows
    ],
    "strategy": "ALL",
    "mode": "UNDERLYING",
    "config": {
        "initial_capital": 100000,
        "risk_per_trade_pct": 1,
        "max_concurrent_positions": 1,
        "quantity": 1,
        "allow_short": True,
        "costs": {
            "brokerage_per_order": 0,
            "stt_rate": 0,
            "exchange_txn_rate": 0,
            "gst_rate": 0,
            "sebi_rate": 0,
            "stamp_duty_rate": 0,
            "slippage_bps": 0,
            "latency_bars": 0,
            "partial_fill_ratio": 1
        }
    }
}

with open("scripts/phase10_real_payload.json", "w") as f:
    json.dump(payload, f, indent=2)

print("ROWS:", len(rows))
print("Created scripts/phase10_real_payload.json")
