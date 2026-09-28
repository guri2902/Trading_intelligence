
from pathlib import Path
import shutil
import re

ROOT = Path(__file__).resolve().parents[1]
PHASE5 = ROOT / "backend" / "app" / "api" / "phase5.py"
BACKTEST = ROOT / "frontend" / "app" / "backtest" / "page.tsx"

for target in (PHASE5, BACKTEST):
    if not target.exists():
        raise SystemExit(f"ERROR: target not found: {target}")

def backup(path: Path, suffix: str):
    b = path.with_suffix(path.suffix + suffix)
    if not b.exists():
        shutil.copy2(path, b)
    return b

# ---------------- BACKEND ----------------
pbackup = backup(PHASE5, ".historical_range_v3.bak")
ptext = PHASE5.read_text(encoding="utf-8")
ptext = ptext.replace("le=5000", "le=100000")

pat = re.compile(
    r'(?P<indent>^[ \t]*)rows\s*=\s*latest_candles\((?P<body>.*?)\)\s*\n',
    re.MULTILINE | re.DOTALL,
)
m = pat.search(ptext)
if not m:
    raise SystemExit("ERROR: Could not locate rows = latest_candles(...) in phase5.py")

indent = m.group("indent")
new_block = "\n".join([
    f"{indent}query_limit = max(int(limit), 100000) if (from_date or to_date) else int(limit)",
    f"{indent}rows = latest_candles(",
    f"{indent}    db,",
    f"{indent}    canonical_key=canonical_key,",
    f"{indent}    timeframe=timeframe,",
    f"{indent}    limit=query_limit,",
    f"{indent})",
    f"{indent}if from_date or to_date:",
    f"{indent}    from datetime import datetime",
    f"{indent}    start_date = datetime.fromisoformat(from_date).date() if from_date else None",
    f"{indent}    end_date = datetime.fromisoformat(to_date).date() if to_date else None",
    f"{indent}    filtered = []",
    f"{indent}    for row in rows:",
    f"{indent}        raw_ts = row.get('timestamp')",
    f"{indent}        try:",
    f"{indent}            ts_date = datetime.fromisoformat(str(raw_ts).replace('Z', '+00:00')).date()",
    f"{indent}        except (TypeError, ValueError):",
    f"{indent}            continue",
    f"{indent}        if start_date and ts_date < start_date:",
    f"{indent}            continue",
    f"{indent}        if end_date and ts_date > end_date:",
    f"{indent}            continue",
    f"{indent}        filtered.append(row)",
    f"{indent}    rows = filtered[-int(limit):]",
])
ptext = ptext[:m.start()] + new_block + "\n" + ptext[m.end():]
PHASE5.write_text(ptext, encoding="utf-8")

# ---------------- FRONTEND ----------------
bbackup = backup(BACKTEST, ".historical_range_v3.bak")
btext = BACKTEST.read_text(encoding="utf-8")

old = re.compile(r"  async function loadCandles\(\) \{.*?\n  \}\n\n  const selected =", re.DOTALL)

new_fn = r'''
  async function loadCandles() {
    setError("");
    setStatus("Loading historical NIFTY candles…");

    try {
      if (!fromDate || !toDate) {
        throw new Error("Select both From and To dates before loading historical data.");
      }

      const ingest = new URLSearchParams({
        provider: "upstox",
        instrument_key: "NSE_INDEX|Nifty 50",
        canonical_key: "NSE_INDEX|Nifty 50",
        unit: "minutes",
        interval: "5",
        from_date: fromDate,
        to_date: toDate,
      });

      setStatus("Downloading/persisting selected NIFTY history…");

      const ingestRes = await fetch(`${API}/phase5/ingest/candles?${ingest.toString()}`, {
        method: "POST",
        cache: "no-store",
      });
      const ingestBody = await ingestRes.json();

      if (!ingestRes.ok) {
        const detail =
          typeof ingestBody.detail === "string"
            ? ingestBody.detail
            : JSON.stringify(ingestBody.detail);
        throw new Error(detail || "Historical candle ingestion failed.");
      }

      const requestedLimit = Math.max(30, Number(limit) || 5000);

      const q = new URLSearchParams({
        canonical_key: "NSE_INDEX|Nifty 50",
        timeframe: "minutes:5",
        limit: String(requestedLimit),
        from_date: fromDate,
        to_date: toDate,
      });

      const res = await fetch(`${API}/phase5/candles/latest?${q.toString()}`, {
        cache: "no-store",
      });
      const body = await res.json();

      if (!res.ok) {
        const detail =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail);
        throw new Error(detail || "Historical candle query failed.");
      }

      const loadedRows = Array.isArray(body)
        ? body
        : (Array.isArray(body.rows)
          ? body.rows
          : (Array.isArray(body.value) ? body.value : []));

      if (!loadedRows.length) {
        throw new Error(`No persisted NIFTY candles found for ${fromDate} to ${toDate}.`);
      }

      setRows(loadedRows);

      const firstTs =
        loadedRows[0]?.timestamp ||
        loadedRows[0]?.ts ||
        loadedRows[0]?.datetime ||
        "—";
      const lastTs =
        loadedRows[loadedRows.length - 1]?.timestamp ||
        loadedRows[loadedRows.length - 1]?.ts ||
        loadedRows[loadedRows.length - 1]?.datetime ||
        "—";

      setStatus(
        `${loadedRows.length} persisted candles loaded · ${firstTs} → ${lastTs}`
      );
    } catch (e: any) {
      setError(e.message || "Historical candle load failed");
      setStatus("");
      setRows([]);
    }
  }

  const selected ='''

m2 = old.search(btext)
if not m2:
    raise SystemExit("ERROR: Could not locate loadCandles() in backtest/page.tsx")

btext = btext[:m2.start()] + new_fn + btext[m2.end():]
btext = btext.replace('max="5000" value={limit}', 'max="50000" value={limit}', 1)
btext = btext.replace("latency_bars:0", "latency_bars:1")
BACKTEST.write_text(btext, encoding="utf-8")

print("[OK] Backtest downloads/persists the selected historical range.")
print("[OK] Backend filters /phase5/candles/latest by from_date/to_date.")
print("[OK] Backtest Bars maximum increased to 50,000.")
print(f"[OK] Backend backup: {pbackup.name}")
print(f"[OK] Frontend backup: {bbackup.name}")
print("A valid UPSTOX_ACCESS_TOKEN is required for historical download.")
