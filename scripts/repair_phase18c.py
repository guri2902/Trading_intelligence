from __future__ import annotations

from pathlib import Path
import re
import os

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "backend" / "app"
API_DIR = APP / "api"
FRONTEND = ROOT / "frontend"


def backup(path: Path) -> None:
    p = path.with_suffix(path.suffix + ".phase18cbak")
    if not p.exists():
        p.write_bytes(path.read_bytes())


def discover_router(fragment: str):
    for p in sorted(API_DIR.glob("*.py")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        if fragment not in text:
            continue
        m = re.search(r"(?m)^(\w+)\s*=\s*APIRouter\(", text)
        if m:
            return p.stem, m.group(1)
    return None, None


def clean_main_router_lines(text: str, route_fragments: list[str]) -> str:
    lines = text.splitlines()
    out = []
    for line in lines:
        # Remove only lines introduced by the previous auto-wiring attempt.
        if "app.include_router(" in line and any(name in line for name in (
            "strategy_studio_router",
            "backtest_data_router",
            "strategy_studio",
            "backtest_data",
        )):
            continue
        if line.strip().startswith("from .api.") and any(name in line for name in (
            "strategy_studio_router",
            "backtest_data_router",
            "strategy_studio import",
            "backtest_data import",
        )):
            continue
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def add_import_after_api_imports(text: str, import_line: str) -> str:
    lines = text.splitlines()
    if import_line in lines:
        return text
    positions = [i for i, line in enumerate(lines) if line.startswith("from .api.")]
    idx = positions[-1] + 1 if positions else 0
    lines.insert(idx, import_line)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def ensure_include_at_end(text: str, include_line: str) -> str:
    if include_line in text:
        return text
    # Including a router at module end is valid and avoids nesting it inside
    # startup try/except blocks or other function bodies.
    if not text.endswith("\n"):
        text += "\n"
    return text + include_line + "\n"


def patch_main() -> None:
    main = APP / "main.py"
    text = main.read_text(encoding="utf-8")

    discoveries = []
    for fragment in ("strategy-studio", "backtest-data"):
        module, router = discover_router(fragment)
        if module and router:
            discoveries.append((fragment, module, router))
        else:
            print(f"[WARN] Could not discover router for {fragment}")

    cleaned = clean_main_router_lines(text, ["strategy-studio", "backtest-data"])

    for _, module, router in discoveries:
        import_line = f"from .api.{module} import {router} as {module}_router"
        include_line = f"app.include_router({module}_router)"
        cleaned = add_import_after_api_imports(cleaned, import_line)
        cleaned = ensure_include_at_end(cleaned, include_line)

    if cleaned != text:
        backup(main)
        main.write_text(cleaned, encoding="utf-8")
        print("[OK] Repaired backend/app/main.py router wiring")
    else:
        print("[SKIP] main.py already clean")


def find_shell() -> Path | None:
    candidates = []
    for pattern in ("Shell.tsx", "Shell.ts", "Shell.jsx", "Shell.js"):
        candidates.extend(FRONTEND.rglob(pattern))
    return sorted(candidates)[0] if candidates else None


def patch_frontend_shell_imports() -> None:
    shell = find_shell()
    if shell is None:
        print("[WARN] Could not find Shell component")
        return

    changed = 0
    for page in FRONTEND.rglob("*.tsx"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        if "from \"../../components/Shell\"" not in text and "from '../../components/Shell'" not in text:
            continue

        rel = os.path.relpath(shell, page.parent).replace("\\", "/")
        rel_no_ext = re.sub(r"\.(tsx|ts|jsx|js)$", "", rel)
        if not rel_no_ext.startswith("."):
            rel_no_ext = "./" + rel_no_ext

        new_text = text.replace(
            'from "../../components/Shell"',
            f'from "{rel_no_ext}"',
        ).replace(
            "from '../../components/Shell'",
            f"from '{rel_no_ext}'",
        )

        if new_text != text:
            backup(page)
            page.write_text(new_text, encoding="utf-8")
            changed += 1
            print(f"[OK] Fixed Shell import: {page.relative_to(FRONTEND)} -> {rel_no_ext}")

    if changed == 0:
        print("[SKIP] No broken Shell imports found")


def main() -> int:
    if not ROOT.exists():
        print(f"[FAIL] Project root not found: {ROOT}")
        return 2
    patch_main()
    patch_frontend_shell_imports()
    print("\nNow run:")
    print("  python -m compileall backend")
    print("  pytest -q")
    print("  python scripts\\validate_production.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
