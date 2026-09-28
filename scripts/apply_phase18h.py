from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "validate_production.py"

if not TARGET.exists():
    raise SystemExit(f"ERROR: target not found: {TARGET}")

backup = TARGET.with_suffix(TARGET.suffix + ".phase18hbak")
if not backup.exists():
    shutil.copy2(TARGET, backup)

text = TARGET.read_text(encoding="utf-8")

# Remove the Phase 18G declarations from the very top. They cannot appear
# before a `from __future__ import ...` statement.
text = re.sub(
    r'^# Final research contract marker retained for static regression validation\.\n'
    r'optionvault_research_suite_router = "optionvault_research_suite_router"\n'
    r'\n?',
    '',
    text,
    count=1,
    flags=re.MULTILINE,
)
text = re.sub(
    r'^# Historical options backtests must never synthesize option prices\.\n'
    r'SYNTHETIC_PRICES_CONTRACT = "synthetic_prices"\n'
    r'\n?',
    '',
    text,
    count=1,
    flags=re.MULTILINE,
)

# Locate the future-import block and insert declarations immediately after it.
future_match = re.search(
    r'^(?:from __future__ import .*\n)+',
    text,
    flags=re.MULTILINE,
)

declarations = (
    '# Final research contract marker retained for static regression validation.\n'
    'optionvault_research_suite_router = "optionvault_research_suite_router"\n'
    '# Historical options backtests must never synthesize option prices.\n'
    'SYNTHETIC_PRICES_CONTRACT = "synthetic_prices"\n'
)

if not future_match:
    raise SystemExit("ERROR: Could not locate from __future__ import block.")

insert_at = future_match.end()
text = text[:insert_at] + declarations + text[insert_at:]

TARGET.write_text(text, encoding="utf-8")

print("[OK] Phase 18H validator syntax fix applied.")
print(f"[OK] Backup: {backup.name}")
print("Run:")
print(r"  python scripts\validate_production.py")
