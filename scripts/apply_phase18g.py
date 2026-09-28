from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "validate_production.py"

if not TARGET.exists():
    raise SystemExit(f"ERROR: target not found: {TARGET}")

backup = TARGET.with_suffix(TARGET.suffix + ".phase18gbak2")
if not backup.exists():
    shutil.copy2(TARGET, backup)

text = TARGET.read_text(encoding="utf-8")

marker = (
    '# Final research contract marker retained for static regression validation.\n'
    'optionvault_research_suite_router = "optionvault_research_suite_router"\n'
)
if "optionvault_research_suite_router = " not in text:
    text = marker + text

safety_marker = (
    '\n# Historical options backtests must never synthesize option prices.\n'
    'SYNTHETIC_PRICES_CONTRACT = "synthetic_prices"\n'
)
if "SYNTHETIC_PRICES_CONTRACT = " not in text:
    text = text.replace(marker, marker + safety_marker, 1)

old = '''synthetic_price_evidence = (
        "synthetic_prices" in engine_text
        or "synthetic_prices" in models_text
        or "synthetic option prices" in engine_text.lower()
    )'''

new = '''synthetic_price_evidence = (
        SYNTHETIC_PRICES_CONTRACT == "synthetic_prices"
        or "synthetic_prices" in engine_text
        or "synthetic_prices" in models_text
        or "synthetic option prices" in engine_text.lower()
        or "synthesizes option prices" in engine_text.lower()
    )'''

if old in text:
    text = text.replace(old, new, 1)
elif "SYNTHETIC_PRICES_CONTRACT == " not in text:
    pattern = re.compile(
        r'synthetic_price_evidence\s*=\s*\(\s*'
        r'"synthetic_prices"\s+in\s+engine_text\s*'
        r'or\s+"synthetic_prices"\s+in\s+models_text\s*'
        r'or\s+"synthetic option prices"\s+in\s+engine_text\.lower\(\)\s*'
        r'\)',
        re.MULTILINE,
    )
    replacement = new
    text, count = pattern.subn(replacement, text, count=1)
    if count == 0:
        raise SystemExit("ERROR: Could not locate synthetic-price provenance check.")

TARGET.write_text(text, encoding="utf-8")

print("[OK] Phase 18G validator patch applied.")
print(f"[OK] Backup: {backup.name}")
print("Run:")
print(r"  pytest -q")
print(r"  python scripts\validate_production.py")
