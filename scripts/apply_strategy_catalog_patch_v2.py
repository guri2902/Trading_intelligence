from pathlib import Path
import shutil
import re

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "frontend" / "app" / "backtest" / "page.tsx"

if not TARGET.exists():
    raise SystemExit(f"ERROR: target not found: {TARGET}")

backup = TARGET.with_suffix(TARGET.suffix + ".strategycatalogv2bak")
if not backup.exists():
    shutil.copy2(TARGET, backup)

text = TARGET.read_text(encoding="utf-8")

# Locate the strategy loading section by its stable statements rather than
# depending on one exact formatting style.
anchor = 'const xs = (d.strategies || []).filter((x: Strategy) => x.status !== "DISABLED");'
start = text.find("fetch(`${API}/strategy-studio/strategies`)")
anchor_pos = text.find(anchor, start)

if start == -1 or anchor_pos == -1:
    # Print useful diagnostics instead of silently failing.
    m = re.search(r'fetch\(`\$\{API\}/strategy-studio/strategies`.*?loadCandles\(\);', text, re.S)
    if not m:
        raise SystemExit(
            "ERROR: strategy loader not found. "
            "Run: Select-String -Path frontend\\app\\backtest\\page.tsx "
            "-Pattern 'strategy-studio/strategies' -Context 5,12"
        )
    start = m.start()
    end = m.end()
else:
    # Include through the existing catch(...) and preserve the following loadCandles() call.
    end = text.find("loadCandles();", anchor_pos)
    if end == -1:
        raise SystemExit("ERROR: Could not find loadCandles() after strategy loader.")
    end += len("loadCandles();")

replacement = """Promise.all([
        fetch(`${API}/strategy-studio/strategies`).then(r => r.json()),
        fetch(`${API}/strategy-studio/engine-strategies`).then(r => r.json()).catch(() => ({strategies: []}))
      ]).then(([storedBody, engineBody]) => {
        const storedStrategies = (storedBody.strategies || [])
          .filter((x: Strategy) => x.status !== "DISABLED");

        const engineList = Array.isArray(engineBody)
          ? engineBody
          : (engineBody.strategies || engineBody.value || []);

        const engineStrategies = engineList.map((x: any, i: number) => {
          const engineName = String(
            x.engine_strategy || x.strategy || x.name || ""
          ).trim();

          return {
            id: x.id || `builtin-${engineName.toLowerCase() || i}`,
            name: x.name || engineName,
            engine_strategy: x.engine_strategy || x.strategy || engineName,
            status: "ENABLED",
            instrument: "NIFTY",
            timeframe: "5m",
            description:
              x.description ||
              "Implemented deterministic StrategyEngine strategy."
          };
        }).filter((x: any) => x.engine_strategy);

        const merged: any[] = [];
        const seen = new Set<string>();

        for (const item of [...engineStrategies, ...storedStrategies]) {
          const key = String(item.engine_strategy || item.id || item.name);
          if (!key || seen.has(key)) continue;
          seen.add(key);
          merged.push(item);
        }

        setStrategies(merged);
        if (merged.length) setStrategyId(merged[0].id);
      }).catch(() => setError("Unable to load strategies"));
      loadCandles();"""

new_text = text[:start] + replacement + text[end:]
TARGET.write_text(new_text, encoding="utf-8")

print("[OK] Strategy catalog loader patched.")
print("[OK] Backtest now loads deterministic engine strategies + persisted custom strategies.")
print(f"[OK] Backup: {backup.name}")
print("Restart Next.js and refresh /backtest.")
