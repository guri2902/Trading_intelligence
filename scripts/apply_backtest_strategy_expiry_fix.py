from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
LOADER = ROOT / "backend" / "app" / "options_backtest" / "optionvault_loader.py"
BACKTEST = ROOT / "frontend" / "app" / "backtest" / "page.tsx"

if not LOADER.exists():
    raise SystemExit(f"ERROR: target not found: {LOADER}")
if not BACKTEST.exists():
    raise SystemExit(f"ERROR: target not found: {BACKTEST}")

# ------------------------------------------------------------------
# 1) Fix OptionVault expiry typing.
# HistoricalOptionBar.expiry is already a string. The discovery code
# incorrectly calls .date() on that string.
# ------------------------------------------------------------------
backup = LOADER.with_suffix(LOADER.suffix + ".expiryfixbak")
if not backup.exists():
    shutil.copy2(LOADER, backup)

text = LOADER.read_text(encoding="utf-8")
old = "expiry=str(first.expiry.date()),"
new = "expiry=str(first.expiry),"

if old not in text:
    raise SystemExit(
        "ERROR: Expected OptionVault expiry bug was not found. "
        "Search the file for: first.expiry"
    )

LOADER.write_text(text.replace(old, new, 1), encoding="utf-8")

# ------------------------------------------------------------------
# 2) Make a deterministic engine strategy the default selection.
# The prior UI patch correctly prepends the deterministic catalog, but
# retained `setStrategyId(merged[0].id)`, which can default back to a
# saved custom strategy such as hgjhv.
# ------------------------------------------------------------------
backup2 = BACKTEST.with_suffix(BACKTEST.suffix + ".strategydefaultfixbak")
if not backup2.exists():
    shutil.copy2(BACKTEST, backup2)

btext = BACKTEST.read_text(encoding="utf-8")
old2 = "if (merged.length) setStrategyId(merged[0].id);"

if old2 in btext:
    btext = btext.replace(
        old2,
        "if (finalStrategies.length) setStrategyId(finalStrategies[0].id);",
        1,
    )
else:
    # Accept a slightly different formatter.
    old2b = "if (merged.length) setStrategyId(merged[0].id)"
    if old2b in btext:
        btext = btext.replace(
            old2b,
            "if (finalStrategies.length) setStrategyId(finalStrategies[0].id)",
            1,
        )
    elif "setStrategyId(finalStrategies[0].id)" not in btext:
        raise SystemExit(
            "ERROR: Could not find the old default strategy assignment."
        )

BACKTEST.write_text(btext, encoding="utf-8")

print("[OK] OptionVault expiry discovery fixed.")
print("[OK] Backtest now defaults to the first deterministic engine strategy.")
print(f"[OK] Loader backup: {backup.name}")
print(f"[OK] Backtest backup: {backup2.name}")
print("Restart FastAPI + Next.js, then refresh /backtest.")
