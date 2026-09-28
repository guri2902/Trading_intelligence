from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "frontend" / "app" / "backtest" / "page.tsx"

if not TARGET.exists():
    raise SystemExit(f"ERROR: target not found: {TARGET}")

backup = TARGET.with_suffix(TARGET.suffix + ".phase18ibak")
if not backup.exists():
    shutil.copy2(TARGET, backup)

text = TARGET.read_text(encoding="utf-8")

old = '''      const body = await res.json(); if (!res.ok) throw new Error(body.detail || "Candle load failed");
      setRows(body.rows || []); setStatus(`${body.count || 0} persisted candles loaded · ${body.from || "—"} → ${body.to || "—"}`);'''

new = '''      const body = await res.json(); if (!res.ok) throw new Error(body.detail || "Candle load failed");
      const loadedRows = Array.isArray(body.rows) ? body.rows : (Array.isArray(body.value) ? body.value : []);
      setRows(loadedRows);
      const loadedCount = typeof body.count === "number" ? body.count : loadedRows.length;
      const loadedFrom = body.from || (loadedRows.length ? (loadedRows[0].ts || loadedRows[0].timestamp || loadedRows[0].datetime || "—") : "—");
      const loadedTo = body.to || (loadedRows.length ? (loadedRows[loadedRows.length - 1].ts || loadedRows[loadedRows.length - 1].timestamp || loadedRows[loadedRows.length - 1].datetime || "—") : "—");
      setStatus(`${loadedCount} persisted candles loaded · ${loadedFrom} → ${loadedTo}`);'''

if old not in text:
    pattern = re.compile(
        r'(?P<indent>\s*)const body = await res\.json\(\);\s*if \(!res\.ok\) throw new Error\(body\.detail \|\| "Candle load failed"\);\s*'
        r'setRows\(body\.rows \|\| \[\]\);\s*setStatus\(`\$\{body\.count \|\| 0\} persisted candles loaded · \$\{body\.from \|\| "—"\} → \$\{body\.to \|\| "—"\}`\);',
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        raise SystemExit("ERROR: Could not locate the candle response parsing block.")
    replacement = match.group("indent") + new.lstrip()
    text = pattern.sub(replacement, text, count=1)
else:
    text = text.replace(old, new, 1)

TARGET.write_text(text, encoding="utf-8")

print("[OK] Backtest candle response parsing fixed.")
print(f"[OK] Backup: {backup.name}")
print("Refresh /backtest and click: Reload historical data")
