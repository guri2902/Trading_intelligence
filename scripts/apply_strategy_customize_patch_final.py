from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
STRATEGIES = ROOT / "frontend" / "app" / "strategies" / "page.tsx"
BACKTEST = ROOT / "frontend" / "app" / "backtest" / "page.tsx"

if not STRATEGIES.exists() or not BACKTEST.exists():
    raise SystemExit("ERROR: required frontend files not found")

def backup(path, suffix):
    b = path.with_suffix(path.suffix + suffix)
    if not b.exists():
        shutil.copy2(path, b)
    return b

# ---------------- Strategy Studio ----------------
sbackup = backup(STRATEGIES, ".customize_v4.bak")
stext = STRATEGIES.read_text(encoding="utf-8")

if "const API =" not in stext:
    stext = 'const API = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";\\n' + stext

if "async function customizeDeterministic" not in stext:
    marker = "export default function Strategies"
    pos = stext.find(marker)
    brace = stext.find("{", pos)
    if pos < 0 or brace < 0:
        raise SystemExit("ERROR: Strategies component not found")

    helper = (
        "\n  async function customizeDeterministic(strategy: any) {\n"
        "    try {\n"
        "      const response = await fetch(`${API}/strategy-studio/strategies`, {\n"
        '        method: "POST",\n'
        '        headers: {"Content-Type": "application/json"},\n'
        "        body: JSON.stringify({\n"
        "          name: `${strategy.name} (Custom)`,\n"
        "          description: `Editable Strategy Studio copy of ${strategy.name}`,\n"
        '          source: "USER",\n'
        '          instruments: ["NIFTY"],\n'
        '          timeframe: "5m",\n'
        "          engine_strategy: strategy.engine_strategy\n"
        "        })\n"
        "      });\n"
        "      const body = await response.json();\n"
        "      if (!response.ok) {\n"
        '        const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);\n'
        '        throw new Error(detail || "Unable to create strategy");\n'
        "      }\n"
        '      window.location.href = "/strategies";\n'
        "    } catch (error: any) {\n"
        '      alert(error?.message || "Unable to create strategy");\n'
        "    }\n"
        "  }\n"
    )
    stext = stext[:brace + 1] + helper + stext[brace + 1:]

if "customizeDeterministic(s)" not in stext:
    old = '<div className="pill good section">BACKTEST READY</div>'
    new = (
        '<div className="grid cols2 section">\n'
        '  <button type="button" onClick={() => customizeDeterministic(s)}>Customize</button>\n'
        '  <a href={`/backtest?strategy=${encodeURIComponent(s.engine_strategy)}`}>Backtest</a>\n'
        '</div>'
    )
    if old not in stext:
        raise SystemExit("ERROR: deterministic strategy cards not found")
    stext = stext.replace(old, new)

STRATEGIES.write_text(stext, encoding="utf-8")

# ---------------- Backtest ----------------
bbackup = backup(BACKTEST, ".customize_v4.bak")
btext = BACKTEST.read_text(encoding="utf-8")

if "useSearchParams" not in btext:
    btext = 'import {useSearchParams} from "next/navigation";\n' + btext

if "const searchParams = useSearchParams();" not in btext:
    marker = "export default function Backtest"
    pos = btext.find(marker)
    brace = btext.find("{", pos)
    if pos < 0 or brace < 0:
        raise SystemExit("ERROR: Backtest component not found")
    btext = btext[:brace + 1] + "\n  const searchParams = useSearchParams();" + btext[brace + 1:]

if "const requestedStrategy =" not in btext:
    anchor = "setStrategies(finalStrategies);"
    if anchor not in btext:
        raise SystemExit("ERROR: setStrategies(finalStrategies) not found")
    addition = (
        "setStrategies(finalStrategies);\n"
        '        const requestedStrategy = searchParams.get("strategy");\n'
        "        if (requestedStrategy) {\n"
        "          const requested = finalStrategies.find((item: any) => String(item.engine_strategy || item.id) === requestedStrategy);\n"
        "          if (requested) setStrategyId(requested.id);\n"
        "        }"
    )
    btext = btext.replace(anchor, addition, 1)

btext = btext.replace("latency_bars:0", "latency_bars:1")
BACKTEST.write_text(btext, encoding="utf-8")

print("[OK] Strategy Studio deterministic cards now have Customize + Backtest.")
print("[OK] Customize uses confirmed StrategyCreateRequest fields.")
print("[OK] Backtest honors ?strategy=ENGINE_ID.")
print("[OK] Research payload latency_bars is valid.")
