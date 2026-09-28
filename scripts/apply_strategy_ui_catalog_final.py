from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BACKTEST = ROOT / "frontend" / "app" / "backtest" / "page.tsx"
STRATEGIES = ROOT / "frontend" / "app" / "strategies" / "page.tsx"

CATALOG = '''const DETERMINISTIC_STRATEGY_CATALOG = [
  { id:"builtin-vwap-pullback", name:"VWAP Pullback", engine_strategy:"VWAP_PULLBACK", description:"Trend-aligned pullback toward VWAP with ATR-based invalidation." },
  { id:"builtin-ema-continuation", name:"EMA Continuation", engine_strategy:"EMA_CONTINUATION", description:"EMA 9/20/50 alignment with RSI, relative-volume context and ATR risk." },
  { id:"builtin-orb", name:"Opening Range Breakout", engine_strategy:"ORB", description:"Break of the current trading-session opening range." },
  { id:"builtin-orb-retest", name:"Opening Range Retest", engine_strategy:"ORB_RETEST", description:"Opening-range breakout followed by retest confirmation." },
  { id:"builtin-sr-rejection", name:"Support/Resistance Rejection", engine_strategy:"SR_REJECTION", description:"Rejection from a detected support or resistance zone." },
  { id:"builtin-range-fade", name:"Range Fade", engine_strategy:"RANGE_FADE", description:"Mean reversion only when structure classifies the market as RANGE." },
  { id:"builtin-momentum", name:"Momentum Continuation", engine_strategy:"MOMENTUM_CONTINUATION", description:"Trend, momentum, VWAP and relative-volume alignment." },
  { id:"builtin-volatility-breakout", name:"Volatility Breakout", engine_strategy:"VOLATILITY_BREAKOUT", description:"Structural breakout/breakdown using ATR and day-range context." },
  { id:"builtin-option-directional", name:"Option Directional", engine_strategy:"OPTION_DIRECTIONAL", description:"CE/PE direction from the existing options engine; still requires underlying and risk confirmation." },
];'''

def backup(path, suffix):
    b = path.with_suffix(path.suffix + suffix)
    if not b.exists():
        shutil.copy2(path, b)
    return b

for path in (BACKTEST, STRATEGIES):
    if not path.exists():
        raise SystemExit(f"ERROR: missing {path}")

bak = backup(BACKTEST, ".strategycatalogfinalbak")
text = BACKTEST.read_text(encoding="utf-8")

if "DETERMINISTIC_STRATEGY_CATALOG" not in text:
    marker = "export default function Backtest"
    if marker not in text:
        raise SystemExit("ERROR: Backtest component declaration not found")
    text = text.replace(marker, CATALOG + "\n" + marker, 1)

if "deterministicFallback" not in text:
    anchor = "setStrategies(merged);"
    if anchor not in text:
        raise SystemExit("ERROR: run the strategy catalog v2 patch first; setStrategies(merged) not found")
    repl = """const deterministicFallback = DETERMINISTIC_STRATEGY_CATALOG.map((x: any) => ({
          ...x,
          status: "ENABLED",
          instrument: "NIFTY",
          timeframe: "5m",
        }));
        const finalStrategies = [...deterministicFallback, ...merged].filter((item: any, index: number, all: any[]) =>
          index === all.findIndex((x: any) => String(x.engine_strategy || x.id) === String(item.engine_strategy || item.id))
        );
        setStrategies(finalStrategies);"""
    text = text.replace(anchor, repl, 1)
BACKTEST.write_text(text, encoding="utf-8")

bak = backup(STRATEGIES, ".strategycatalogfinalbak")
text = STRATEGIES.read_text(encoding="utf-8")
if "DETERMINISTIC_STRATEGY_CATALOG" not in text:
    marker = "export default function Strategies"
    if marker not in text:
        raise SystemExit("ERROR: Strategies component declaration not found")
    text = text.replace(marker, CATALOG + "\n" + marker, 1)

if "Deterministic Engine Strategies" not in text:
    pos = text.rfind("</Shell>")
    if pos == -1:
        raise SystemExit("ERROR: Strategies closing Shell not found")
    block = """<div className="section">
        <div className="eyebrow">Deterministic engine</div>
        <h2>Deterministic Engine Strategies</h2>
        <div className="grid cols3 section">
          {DETERMINISTIC_STRATEGY_CATALOG.map((s) => (
            <div className="card" key={s.engine_strategy}>
              <h3>{s.name}</h3>
              <div className="small">{s.engine_strategy}</div>
              <div className="small">{s.description}</div>
              <div className="pill good section">BACKTEST READY</div>
            </div>
          ))}
        </div>
      </div>"""
    text = text[:pos] + block + text[pos:]
STRATEGIES.write_text(text, encoding="utf-8")
print("[OK] Strategy catalog is now guaranteed visible in Backtest and Strategies.")
