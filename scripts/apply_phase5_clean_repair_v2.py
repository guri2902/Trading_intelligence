from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "backend" / "app" / "api" / "phase5.py"

if not TARGET.exists():
    raise SystemExit(f"ERROR: target not found: {TARGET}")

candidates = sorted(
    TARGET.parent.glob("phase5.py.*"),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)

source = None
source_path = None
for p in candidates:
    if p == TARGET:
        continue
    try:
        t = p.read_text(encoding="utf-8")
    except Exception:
        continue
    if "def get_latest_candles" in t and "query_limit" not in t and "from_date or to_date" not in t:
        source = t
        source_path = p
        break

if source is None:
    raise SystemExit("ERROR: no clean pre-date-range phase5.py backup found.")

current_backup = TARGET.with_suffix(TARGET.suffix + ".cleanrepair_v2.bak")
if not current_backup.exists():
    shutil.copy2(TARGET, current_backup)

m = re.search(r"^from fastapi import (.+)$", source, re.MULTILINE)
if not m:
    raise SystemExit("ERROR: FastAPI import line not found.")
imports = [x.strip() for x in m.group(1).split(',')]
if "Query" not in imports:
    new_import = "from fastapi import " + ", ".join(imports + ["Query"])
    source = source[:m.start()] + new_import + source[m.end():]

m = re.search(
    r'@router\.get\("/candles/latest"\)\s*\n'
    r'def get_latest_candles\((?P<sig>.*?)\):(?P<body>.*?)(?=\n@router\.|\Z)',
    source,
    re.DOTALL,
)
if not m:
    raise SystemExit("ERROR: clean get_latest_candles endpoint not found.")

sig = m.group('sig')
body = m.group('body')

if "from_date" not in sig:
    lm = re.search(r'(?m)^\s*limit\s*:', sig)
    if lm:
        sig = sig[:lm.start()] + (
            "    from_date: str | None = Query(None),\n"
            "    to_date: str | None = Query(None),\n"
            + sig[lm.start():]
        )
    else:
        sig = sig.rstrip() + (
            "\n    from_date: str | None = Query(None),\n"
            "    to_date: str | None = Query(None),"
        )

rows_pos = body.find('rows = latest_candles(')
if rows_pos < 0:
    raise SystemExit("ERROR: clean latest_candles call not found.")

depth = 0
rows_end = None
for i in range(rows_pos, len(body)):
    if body[i] == '(':
        depth += 1
    elif body[i] == ')':
        depth -= 1
        if depth == 0:
            rows_end = i + 1
            break

if rows_end is None:
    raise SystemExit("ERROR: could not parse latest_candles call.")

filter_block = '''
    if from_date or to_date:
        from datetime import datetime

        start_date = datetime.fromisoformat(from_date).date() if from_date else None
        end_date = datetime.fromisoformat(to_date).date() if to_date else None

        filtered = []
        for row in rows:
            raw_ts = row.get('timestamp')
            try:
                ts_date = datetime.fromisoformat(str(raw_ts).replace('Z', '+00:00')).date()
            except (TypeError, ValueError):
                continue

            if start_date and ts_date < start_date:
                continue
            if end_date and ts_date > end_date:
                continue

            filtered.append(row)

        rows = filtered[-int(limit):]
'''

body = body[:rows_end] + '\n' + filter_block + body[rows_end:]
new_endpoint = '@router.get("/candles/latest")\n' + 'def get_latest_candles(' + sig + '):' + body
new_source = source[:m.start()] + new_endpoint + source[m.end():]
TARGET.write_text(new_source, encoding='utf-8')

result = subprocess.run(
    [sys.executable, '-m', 'py_compile', str(TARGET)],
    capture_output=True,
    text=True,
)
if result.returncode != 0:
    shutil.copy2(source_path, TARGET)
    raise SystemExit('ERROR: py_compile failed; restored clean backup.\n' + (result.stderr or result.stdout))

print('[OK] Restored clean phase5 endpoint and reapplied date filtering.')
print('[OK] py_compile PASS.')
print(f'[OK] Clean source: {source_path.name}')
print(f'[OK] Backup of current file: {current_backup.name}')
