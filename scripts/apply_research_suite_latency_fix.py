from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "frontend" / "app" / "backtest" / "page.tsx"

if not TARGET.exists():
    raise SystemExit(f"ERROR: target not found: {TARGET}")

backup = TARGET.with_suffix(TARGET.suffix + ".latencybak")
if not backup.exists():
    shutil.copy2(TARGET, backup)

text = TARGET.read_text(encoding="utf-8")

old = "config:{initial_capital:Number(capital), quantity:Number(quantity), slippage_bps:5, latency_bars:0},"
new = "config:{initial_capital:Number(capital), quantity:Number(quantity), slippage_bps:5, latency_bars:1},"

if old not in text:
    raise SystemExit("ERROR: Expected latency_bars:0 payload was not found.")

TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")

print("[OK] Research Suite payload fixed: latency_bars 0 -> 1.")
print(f"[OK] Backup: {backup.name}")
print("Restart Next.js and click Run Research Suite again.")
