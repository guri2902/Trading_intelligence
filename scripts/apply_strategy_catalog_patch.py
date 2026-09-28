from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "frontend" / "app" / "backtest" / "page.tsx"

if not TARGET.exists():
    raise SystemExit(f"ERROR: target not found: {TARGET}")

backup = TARGET.with_suffix(TARGET.suffix + ".strategycatalogbak")
if not backup.exists():
    shutil.copy2(TARGET, backup)

text = TARGET.read_text(encoding="utf-8")

pattern = re.compile(
    r'fetch\(`\$\{API\}/strategy-studio/strategies`\)\s*'
    r'\.then\(r => r\.json\(\)\)\.then\(d => \{\s*'
    r'const xs = \(d\.strategies \|\| \[\]\)\.filter\(\(x: Strategy\) => x\.status !== "DISABLED"\);\s*'
    r'setStrategies\(xs\); if \(xs\.length\) setStrategyId\(xs\[0\]\.id\);\s*'
    r'\}\)\.catch\(\(\) => setError\("Unable to load strategies"\)\);',
    re.MULTILINE
)

replacement = """Promise.all([
        fetch(`${API}/strategy-studio/strategies`).then(r => r.json()),
        fetch(`${API}/strategy-studio/engine-strategies`).then(r => r.json()).catch(() => ({strategies: []}))
      ]).then(([stored, engineBody]) => {
        const storedStrategies = (stored.strategies || []).filter((x: Strategy) => x.status !== "DISABLED");
        const rawEngine = Array.isArray(engineBody)
          ? engineBody
          : (engineBody.strategies || engineBody.value || []);
        const engineStrategies = rawEngine.map((x: any, i: number) => {
          const engineName = String(x.engine_strategy || x.strategy || x.name || "");
          return {
            id: x.id || `builtin-${engineName.toLowerCase() || i}`,
            name: x.name || engineName,
            engine_strategy: x.engine_strategy || x.strategy || engineName,
            status: "ENABLED",
            instrument: "NIFTY",
            timeframe: "5m",
            description: x.description || "Implemented deterministic StrategyEngine strategy."
          };
        }).filter((x: any) => x.engine_strategy);

        const seen = new Set<string>();
        const merged = [...engineStrategies, ...storedStrategies].filter((x: any) => {
          const key = String(x.engine_strategy || x.id || x.name);
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        });

        setStrategies(merged);
        if (merged.length) setStrategyId(merged[0].id);
      }).catch(() => setError("Unable to load strategies"));"""

match = pattern.search(text)
if not match:
    raise SystemExit("ERROR: Could not locate the current strategy initialization block.")

TARGET.write_text(pattern.sub(replacement, text, count=1), encoding="utf-8")

print("[OK] Backtest now exposes the implemented deterministic engine strategies.")
print("[OK] Persisted custom strategies are retained.")
print(f"[OK] Backup: {backup.name}")
print("Restart Next.js and refresh /backtest.")
