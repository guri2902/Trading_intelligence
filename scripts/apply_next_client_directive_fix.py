from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "frontend" / "app" / "backtest" / "page.tsx"

if not TARGET.exists():
    raise SystemExit(f"ERROR: target not found: {TARGET}")

backup = TARGET.with_suffix(TARGET.suffix + ".clientdirectivebak")
if not backup.exists():
    shutil.copy2(TARGET, backup)

text = TARGET.read_text(encoding="utf-8")

# Next.js requires the client directive before any imports/expressions.
lines = text.splitlines()
lines = [line for line in lines if line.strip() != '"use client";' and line.strip() != "'use client';"]

# Remove useSearchParams import; use the URL directly inside the existing
# client-side effect so there is no extra App Router search-params hook.
lines = [
    line for line in lines
    if "useSearchParams" not in line
]
text = "\n".join(lines)
text = '"use client";\n\n' + text.lstrip("\n")

old = 'const requestedStrategy = searchParams.get("strategy");'
new = 'const requestedStrategy = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("strategy") : null;'

if old in text:
    text = text.replace(old, new, 1)
elif "const requestedStrategy =" not in text:
    print("[WARN] requestedStrategy logic not found; client directive fix will still be applied.")

TARGET.write_text(text, encoding="utf-8")

print("[OK] Backtest page client directive moved to the first line.")
print("[OK] Removed useSearchParams dependency; strategy query is read inside the client effect.")
print(f"[OK] Backup: {backup.name}")
print("Restart Next.js and refresh /backtest?strategy=VWAP_PULLBACK")
