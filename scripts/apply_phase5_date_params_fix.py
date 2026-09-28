from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "backend" / "app" / "api" / "phase5.py"

if not TARGET.exists():
    raise SystemExit(f"ERROR: target not found: {TARGET}")

backup = TARGET.with_suffix(TARGET.suffix + ".dateparams.bak")
if not backup.exists():
    shutil.copy2(TARGET, backup)

text = TARGET.read_text(encoding="utf-8")

# Ensure Query is imported.
if "from fastapi import" not in text:
    raise SystemExit("ERROR: FastAPI import line not found.")

fastapi_line = re.search(r"^from fastapi import (.+)$", text, re.MULTILINE)
if not fastapi_line:
    raise SystemExit("ERROR: Could not locate FastAPI import.")

imports = fastapi_line.group(1)
if "Query" not in {x.strip() for x in imports.split(",")}:
    replacement = "from fastapi import " + imports.rstrip() + ", Query"
    text = text[:fastapi_line.start()] + replacement + text[fastapi_line.end():]

# Locate get_latest_candles signature.
m = re.search(
    r"@router\.get\(\"/candles/latest\"\)\s*\n"
    r"def get_latest_candles\(\n(?P<sig>.*?)\n\):",
    text,
    re.DOTALL,
)
if not m:
    # Accept a one-line signature as a fallback.
    m = re.search(
        r"@router\.get\(\"/candles/latest\"\)\s*\n"
        r"def get_latest_candles\((?P<sig>.*?)\):",
        text,
        re.DOTALL,
    )

if not m:
    raise SystemExit("ERROR: Could not locate get_latest_candles signature.")

sig = m.group("sig")

# Add the date query parameters only once.
if "from_date" not in sig:
    # Add before limit when present; otherwise append.
    if re.search(r"limit\s*:\s*int", sig):
        sig = re.sub(
            r"(    limit\s*:\s*int[^\n]*)",
            "    from_date: str | None = Query(None),\n"
            "    to_date: str | None = Query(None),\n"
            r"\1",
            sig,
            count=1,
        )
    else:
        sig = sig.rstrip() + (
            "\n    from_date: str | None = Query(None),\n"
            "    to_date: str | None = Query(None),"
        )
else:
    # Ensure both exist if a partial prior patch added only one.
    if "to_date" not in sig:
        sig = sig.rstrip() + "\n    to_date: str | None = Query(None),"
    if "from_date" not in sig:
        sig = sig.rstrip() + "\n    from_date: str | None = Query(None),"

new_func_header = text[m.start():m.end()]
new_func_header = new_func_header.replace(m.group("sig"), sig)
text = text[:m.start()] + new_func_header + text[m.end():]

# Validate the exact bad line will now reference parameters that exist.
if "query_limit = max(int(limit), 100000) if (from_date or to_date) else int(limit)" not in text:
    raise SystemExit(
        "ERROR: The date-aware query block is not present. "
        "This patch expects the previous historical-range patch to have been applied."
    )

TARGET.write_text(text, encoding="utf-8")

print("[OK] Added from_date and to_date query parameters to /phase5/candles/latest.")
print("[OK] Fixed the NameError in get_latest_candles().")
print(f"[OK] Backup: {backup.name}")
print("Restart FastAPI and click Reload historical data again.")
