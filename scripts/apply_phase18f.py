from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / "scripts" / "validate_production.py"
backup = target.with_suffix(target.suffix + ".phase18fbak")

if not target.exists():
    raise SystemExit(f"Missing {target}")

if not backup.exists():
    backup.write_bytes(target.read_bytes())

replacement = Path(__file__).with_name("validate_production_replacement.py")
target.write_text(replacement.read_text(encoding="utf-8"), encoding="utf-8")

print(f"[OK] Updated {target}")
print(f"[BACKUP] {backup}")
