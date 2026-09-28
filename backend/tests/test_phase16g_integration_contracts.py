from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_required_phase16_backend_files_exist():
    required = [
        PROJECT_ROOT / "app" / "api" / "paper_ui.py",
        PROJECT_ROOT / "app" / "api" / "market_data_ui.py",
        PROJECT_ROOT / "app" / "api" / "research_ui.py",
        PROJECT_ROOT / "app" / "api" / "history_settings_ui.py",
    ]
    # This contract test is intended to run only after 16C–16F have been applied.
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise AssertionError("Missing Phase 16 backend UI files:\n" + "\n".join(missing))


def test_main_registers_phase16_ui_routers():
    main = (PROJECT_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    required = [
        "paper_ui_router",
        "market_data_ui_router",
        "research_ui_router",
        "history_settings_ui_router",
    ]
    missing = [name for name in required if name not in main]
    if missing:
        raise AssertionError("Missing router registrations/imports: " + ", ".join(missing))
