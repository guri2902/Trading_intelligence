from pathlib import Path
import shutil
import re

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "backend" / "app" / "api" / "phase5.py"

if not TARGET.exists():
    raise SystemExit(f"ERROR: target not found: {TARGET}")

# Find a backup created before the broken date-range patches.
backups = sorted(
    TARGET.parent.glob("phase5.py.*.bak"),
    key=lambda p: p.stat().st_mtime
)

original_backup = None
for candidate in backups:
    candidate_text = candidate.read_text(encoding="utf-8")
    if "query_limit" not in candidate_text and "from_date or to_date" not in candidate_text:
        if "def get_latest_candles" in candidate_text and "latest_candles(" in candidate_text:
            original_backup = candidate
            break

if original_backup is None:
    raise SystemExit(
        "ERROR: Could not find an unpatched phase5.py backup. "
        "List backend\\app\\api\\phase5.py.*.bak and inspect the files."
    )

current_backup = TARGET.with_suffix(TARGET.suffix + ".signaturefix.bak")
if not current_backup.exists():
    shutil.copy2(TARGET, current_backup)

text = original_backup.read_text(encoding="utf-8")

# Ensure Query is imported.
m_import = re.search(r"^from fastapi import (.+)$", text, re.MULTILINE)
if not m_import:
    raise SystemExit("ERROR: FastAPI import line not found.")

imports = [x.strip() for x in m_import.group(1).split(",")]
if "Query" not in imports:
    new_import = "from fastapi import " + ", ".join(imports + ["Query"])
    text = text[:m_import.start()] + new_import + text[m_import.end():]

# Find the endpoint.
m = re.search(
    r'@router\.get\("/candles/latest"\)\s*\n'
    r'def get_latest_candles\((?P<sig>.*?)\):(?P<body>.*?)(?=\n@router\.|\Z)',
    text,
    re.DOTALL,
)
if not m:
    raise SystemExit("ERROR: get_latest_candles endpoint not found in original backup.")

sig = m.group("sig")
body = m.group("body")

# Add optional date query params to the original signature.
if "from_date" not in sig:
    # Put them just before limit if possible.
    if re.search(r"(?m)^\s*limit\s*:", sig):
        sig = re.sub(
            r"(?m)^(\s*limit\s*:)",
            "    from_date: str | None = Query(None),\n    to_date: str | None = Query(None),\n\\1",
            sig,
            count=1,
        )
    else:
        sig = sig.rstrip() + (
            "\n    from_date: str | None = Query(None),"
            "\n    to_date: str | None = Query(None),"
        )

# Keep the original latest_candles call signature intact.
# Only change its limit value to query_limit when a named limit argument exists.
if "from_date or to_date" not in body:
    # If original call has `limit=limit`, use a larger DB fetch for date filtering.
    body = body.replace("limit=limit", "limit=query_limit", 1)

    # If there is no named limit argument, retain original call and filter what it returns.
    call_pos = body.find("rows = latest_candles(")
    if call_pos < 0:
        raise SystemExit("ERROR: original latest_candles call not found.")

    # Inject query_limit before the original rows call. It is harmless if the
    # original call uses a positional limit; the filter still works on the
    # returned rows.
    inject = (
        "\n"
        "    query_limit = max(int(limit), 100000) if (from_date or to_date) else int(limit)\n"
    )
    body = body[:call_pos] + inject + body[call_pos:]

    # Filter the returned persisted candles by date.
    if "if from_date or to_date:" not in body:
        marker = None
        # Place filtering after the complete latest_candles(...) assignment.
        # Find the end of the assignment's closing parenthesis.
        start = body.find("rows = latest_candles(")
        depth = 0
        end = None
        for i in range(start, len(body)):
            if body[i] == "(":
                depth += 1
            elif body[i] == ")":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            raise SystemExit("ERROR: Could not parse latest_candles call.")

        filter_block = """
    if from_date or to_date:
        from datetime import datetime
        start_date = datetime.fromisoformat(from_date).date() if from_date else None
        end_date = datetime.fromisoformat(to_date).date() if to_date else None
        filtered = []
        for row in rows:
            raw_ts = row.get("timestamp")
            try:
                ts_date = datetime.fromisoformat(
                    str(raw_ts).replace("Z", "+00:00")
                ).date()
            except (TypeError, ValueError):
                continue
            if start_date and ts_date < start_date:
                continue
            if end_date and ts_date > end_date:
                continue
            filtered.append(row)
        rows = filtered[-int(limit):]
"""
        body = body[:end] + filter_block + body[end:]

# Rebuild the endpoint and persist.
new_text = text[:m.start()] + (
    '@router.get("/candles/latest")\n'
    "def get_latest_candles("
    + sig
    + "):"
    + body
) + text[m.end():]

TARGET.write_text(new_text, encoding="utf-8")

print("[OK] Restored the original working latest_candles call signature.")
print("[OK] Added from_date/to_date query parameters.")
print("[OK] Added date filtering without passing unsupported canonical_key kwargs.")
print(f"[OK] Restored from backup: {original_backup.name}")
print(f"[OK] Current-code backup: {current_backup.name}")
print("Restart FastAPI and test the Backtest historical range again.")
