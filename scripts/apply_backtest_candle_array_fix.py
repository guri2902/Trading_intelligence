from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "frontend" / "app" / "backtest" / "page.tsx"

if not TARGET.exists():
    raise SystemExit(f"ERROR: target not found: {TARGET}")

backup = TARGET.with_suffix(TARGET.suffix + ".phase18jbak")
if not backup.exists():
    shutil.copy2(TARGET, backup)

text = TARGET.read_text(encoding="utf-8")

old = r"""      const body = await res.json(); if (!res.ok) throw new Error(body.detail || "Candle load failed");
      const loadedRows = Array.isArray(body.rows) ? body.rows : (Array.isArray(body.value) ? body.value : []);
      setRows(loadedRows);
      const loadedCount = typeof body.count === "number" ? body.count : loadedRows.length;
      const loadedFrom = body.from || (loadedRows.length ? (loadedRows[0].ts || loadedRows[0].timestamp || loadedRows[0].datetime || "—") : "—");
      const loadedTo = body.to || (loadedRows.length ? (loadedRows[loadedRows.length - 1].ts || loadedRows[loadedRows.length - 1].timestamp || loadedRows[loadedRows.length - 1].datetime || "—") : "—");
      setStatus(`${loadedCount} persisted candles loaded · ${loadedFrom} → ${loadedTo}`);"""

new = r"""      const body = await res.json(); if (!res.ok) throw new Error(body.detail || "Candle load failed");
      const loadedRows = Array.isArray(body)
        ? body
        : (Array.isArray(body.rows)
          ? body.rows
          : (Array.isArray(body.value) ? body.value : []));
      setRows(loadedRows);
      const loadedCount = !Array.isArray(body) && typeof body.count === "number"
        ? body.count
        : loadedRows.length;
      const loadedFrom = !Array.isArray(body) && body.from
        ? body.from
        : (loadedRows.length ? (loadedRows[0].timestamp || loadedRows[0].ts || loadedRows[0].datetime || "—") : "—");
      const loadedTo = !Array.isArray(body) && body.to
        ? body.to
        : (loadedRows.length ? (loadedRows[loadedRows.length - 1].timestamp || loadedRows[loadedRows.length - 1].ts || loadedRows[loadedRows.length - 1].datetime || "—") : "—");
      setStatus(String(loadedCount) + " persisted candles loaded · " + loadedFrom + " → " + loadedTo);"""

if old not in text:
    raise SystemExit("ERROR: Expected candle parsing block not found.")

TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")

print("[OK] Backtest now handles the actual JSON array response.")
print(f"[OK] Backup: {backup.name}")
print("Restart Next.js, refresh /backtest, then click 'Reload historical data'.")
