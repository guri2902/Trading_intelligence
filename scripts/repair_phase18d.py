from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
VALIDATOR = ROOT / "scripts" / "validate_production.py"


def backup(path: Path):
    b = path.with_suffix(path.suffix + ".phase18dbak")
    if not b.exists():
        b.write_bytes(path.read_bytes())


def patch_frontend_candle_endpoint():
    changed = 0
    for path in FRONTEND.rglob("*.tsx"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "/backtest-data/candles" not in text:
            continue
        new = text.replace("/backtest-data/candles", "/phase5/candles/latest")
        backup(path)
        path.write_text(new, encoding="utf-8")
        changed += 1
        print(f"[OK] Backtest candle endpoint: {path.relative_to(FRONTEND)}")
    if changed == 0:
        print("[SKIP] No /backtest-data/candles frontend references found")


def patch_candle_response_parsing():
    replacements = [
        ("setCandles(payload.candles || []);", "setCandles(payload?.value ?? payload?.candles ?? []);"),
        ("setCandles(data.candles || []);", "setCandles(data?.value ?? data?.candles ?? []);"),
        ("const rows = payload.candles || [];", "const rows = payload?.value ?? payload?.candles ?? [];") ,
        ("const rows = data.candles || [];", "const rows = data?.value ?? data?.candles ?? [];") ,
    ]
    changed = 0
    for path in FRONTEND.rglob("*.tsx"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        new = text
        for old, repl in replacements:
            new = new.replace(old, repl)
        if new != text:
            backup(path)
            path.write_text(new, encoding="utf-8")
            changed += 1
            print(f"[OK] Candle response normalization: {path.relative_to(FRONTEND)}")
    if changed == 0:
        print("[SKIP] No known candle-response parsing pattern needed patching")


def patch_validator():
    path = VALIDATOR
    text = path.read_text(encoding="utf-8", errors="ignore")
    marker = re.search(r"(?ms)^def check_router(?:s)?\\(.*?(?=^def |\\Z)", text)
    if not marker:
        print("[WARN] Could not locate validator router-check function; inspect manually")
        return

    old_block = marker.group(0)
    new_block = '''def check_routers():
    """Verify actual FastAPI route registration."""
    try:
        from backend.app.main import app

        routes = {getattr(r, "path", "") for r in app.routes}
        required = [
            "/phase5/candles/latest",
            "/strategy-studio/strategies",
            "/strategy-studio/engine-strategies",
        ]
        missing = [p for p in required if p not in routes]
        phase_roots = {
            "/phase17": any(p == "/phase17" or p.startswith("/phase17/") for p in routes),
            "/phase18": any(p == "/phase18" or p.startswith("/phase18/") for p in routes),
        }
        missing.extend([k for k, ok in phase_roots.items() if not ok])
        return "PASS" if not missing else [f"Missing registered FastAPI routes: {', '.join(missing)}"]
    except Exception as exc:
        return [f"Router inspection failed: {exc}"]
'''
    backup(path)
    path.write_text(text.replace(old_block, new_block, 1), encoding="utf-8")
    print("[OK] Production validator router check updated")


def main():
    patch_frontend_candle_endpoint()
    patch_candle_response_parsing()
    patch_validator()
    print("\nRun next:")
    print("  pytest -q")
    print("  python scripts\\validate_production.py")
    print("  uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000")


if __name__ == "__main__":
    main()
