import sqlite3

DB = "trading_intelligence.db"

columns = {
    "underlying_ltp": "NUMERIC",
    "delta": "NUMERIC",
    "gamma": "NUMERIC",
    "theta": "NUMERIC",
    "vega": "NUMERIC",
    "rho": "NUMERIC",
}

with sqlite3.connect(DB) as conn:
    existing = {
        row[1]
        for row in conn.execute("PRAGMA table_info(market_snapshots)")
    }

    for name, sql_type in columns.items():
        if name not in existing:
            conn.execute(
                f"ALTER TABLE market_snapshots ADD COLUMN {name} {sql_type}"
            )
            print("ADDED:", name)
        else:
            print("EXISTS:", name)

    conn.commit()

print("Migration complete.")
