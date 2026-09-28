from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def backup(path: Path) -> None:
    backup_path = path.with_suffix(path.suffix + ".phase18bak")
    if not backup_path.exists():
        backup_path.write_bytes(path.read_bytes())


def replace_once(path: Path, old: str, new: str, label: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"[SKIP] {label}: already patched")
        return False
    if old not in text:
        print(f"[WARN] {label}: pattern not found")
        return False
    backup(path)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[OK] {label}")
    return True


def patch_validate_script() -> None:
    path = ROOT / "scripts" / "validate_production.py"
    replace_once(
        path,
        'run_command(["npm", "run", "build"], frontend)',
        'run_command(["npm.cmd", "run", "build"], frontend)',
        "Windows npm invocation",
    )


def patch_backtest_entry_bar() -> None:
    path = ROOT / "backend" / "app" / "backtest" / "engine.py"
    replace_once(
        path,
        'if open_trade and i >= open_trade["entry_index"]:',
        'if open_trade and i > open_trade["entry_index"]:',
        "no exit on entry bar",
    )


def patch_optionvault_loader() -> None:
    path = ROOT / "backend" / "app" / "options_backtest" / "optionvault_loader.py"
    text = path.read_text(encoding="utf-8")

    # Convert expiry to the string required by HistoricalOptionBar.
    variants = [
        (
            'expiry=self._date(row["expiry"]),',
            'expiry=self._date(row["expiry"]).date().isoformat(),',
        ),
        (
            'expiry=self._date(row["expiry"]),\r\n',
            'expiry=self._date(row["expiry"]).date().isoformat(),\r\n',
        ),
    ]
    for old, new in variants:
        if new in text:
            print("[SKIP] OptionVault expiry mapping: already patched")
            return
        if old in text:
            backup(path)
            path.write_text(text.replace(old, new, 1), encoding="utf-8")
            print("[OK] OptionVault expiry mapping")
            return

    # Safer fallback: patch the helper so every caller receives an ISO date string.
    m = re.search(
        r'(?ms)^(\s*def _date\(self, value: str\).*?^\s*return )([^\n]+)$',
        text,
    )
    if m and ".isoformat()" not in m.group(0):
        old = m.group(0)
        new = old.replace(
            m.group(2),
            f"{m.group(2)}.date().isoformat()",
            1,
        )
        backup(path)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        print("[OK] OptionVault expiry helper mapping")
        return

    print("[WARN] OptionVault expiry mapping: pattern not found")


def discover_router_module(api_dir: Path, route_fragment: str):
    for path in api_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if route_fragment not in text:
            continue
        # Capture the first APIRouter assignment in the module.
        m = re.search(r'(?m)^(\w+)\s*=\s*APIRouter\(', text)
        if m:
            return path, m.group(1)
    return None


def ensure_router_in_main(module_path: Path, router_name: str) -> None:
    main = ROOT / "backend" / "app" / "main.py"
    text = main.read_text(encoding="utf-8")
    module_name = module_path.stem
    import_line = f"from .api.{module_name} import {router_name} as {module_name}_router"
    include_line = f"app.include_router({module_name}_router)"

    changed = False
    if import_line not in text:
        # Insert after the last existing relative API import.
        lines = text.splitlines()
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("from .api.") or line.startswith("from .api "):
                insert_at = i + 1
        lines.insert(insert_at, import_line)
        text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
        changed = True

    if include_line not in text:
        # Append immediately after existing include_router calls.
        lines = text.splitlines()
        last = max((i for i, line in enumerate(lines) if "app.include_router(" in line), default=-1)
        if last >= 0:
            lines.insert(last + 1, include_line)
        else:
            lines.append(include_line)
        text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
        changed = True

    if changed:
        backup(main)
        main.write_text(text, encoding="utf-8")
        print(f"[OK] Router wiring: {module_name}")
    else:
        print(f"[SKIP] Router wiring: {module_name} already present")


def patch_missing_ui_routers() -> None:
    api_dir = ROOT / "backend" / "app" / "api"
    for fragment in ("/strategy-studio", "strategy-studio", "/backtest-data", "backtest-data"):
        found = discover_router_module(api_dir, fragment)
        if found:
            ensure_router_in_main(*found)
            # one module is enough for each route family
            if "strategy" in fragment:
                break

    # Run a second independent scan for backtest-data.
    found = discover_router_module(api_dir, "backtest-data")
    if found:
        ensure_router_in_main(*found)


def main() -> int:
    print(f"Project root: {ROOT}")
    required = [
        ROOT / "scripts" / "validate_production.py",
        ROOT / "backend" / "app" / "backtest" / "engine.py",
        ROOT / "backend" / "app" / "options_backtest" / "optionvault_loader.py",
        ROOT / "backend" / "app" / "main.py",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print("[FAIL] Missing expected files:")
        for p in missing:
            print("  ", p)
        return 2

    patch_validate_script()
    patch_backtest_entry_bar()
    patch_optionvault_loader()
    patch_missing_ui_routers()

    print("\nFixes applied. Backups use the .phase18bak suffix.")
    print("Now run:")
    print("  pytest -q")
    print("  python scripts\\validate_production.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
