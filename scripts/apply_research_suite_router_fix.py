from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "backend" / "app" / "main.py"

if not TARGET.exists():
    raise SystemExit(f"ERROR: target not found: {TARGET}")

backup = TARGET.with_suffix(TARGET.suffix + ".researchsuitebak")
if not backup.exists():
    shutil.copy2(TARGET, backup)

text = TARGET.read_text(encoding="utf-8")

# Add the existing router import if it is not already present.
import_line = "from .api.optionvault_research_suite import router as optionvault_research_suite_router"

if "optionvault_research_suite_router" not in text:
    # Prefer placing it alongside the other API router imports.
    lines = text.splitlines()
    insert_at = None

    for i, line in enumerate(lines):
        if "optionvault_" in line and "import" in line:
            insert_at = i + 1

    if insert_at is None:
        for i, line in enumerate(lines):
            if "from .api." in line and " import " in line:
                insert_at = i + 1

    if insert_at is None:
        raise SystemExit("ERROR: Could not find a safe API import insertion point.")

    lines.insert(insert_at, import_line)
    text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")

# Register the router before the app starts serving requests.
if "app.include_router(optionvault_research_suite_router)" not in text:
    # Put it next to the other late-stage routers, immediately before strategy studio.
    needle = "app.include_router(strategy_studio_router)"
    if needle in text:
        text = text.replace(
            needle,
            "app.include_router(optionvault_research_suite_router)\n" + needle,
            1,
        )
    else:
        # Fallback: append after the last include_router call.
        matches = list(re.finditer(r"(?m)^app\.include_router\([^)]+\)\s*$", text))
        if not matches:
            raise SystemExit("ERROR: Could not find app.include_router registration block.")
        pos = matches[-1].end()
        text = text[:pos] + "\napp.include_router(optionvault_research_suite_router)" + text[pos:]

TARGET.write_text(text, encoding="utf-8")

print("[OK] OptionVault Research Suite router registered.")
print(f"[OK] Backup: {backup.name}")
print("Restart FastAPI, then test:")
print("  POST /backtest/optionvault/research-suite")
