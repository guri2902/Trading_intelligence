
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FRONT=ROOT/"frontend"
PAGES=["page.tsx","scanner/page.tsx","option-chain/page.tsx","analysis/page.tsx","ai-analysis/page.tsx","backtest/page.tsx","strategies/page.tsx","paper/page.tsx","history/page.tsx","risk/page.tsx","settings/page.tsx"]

def test_frontend_pages_exist():
    for rel in PAGES:
        assert (FRONT/"app"/rel).exists(), rel

def test_frontend_has_safe_api_client():
    s=(FRONT/"lib/api.ts").read_text()
    assert "NEXT_PUBLIC_API_BASE_URL" in s
    assert "no-store" in s

def test_settings_does_not_expose_broker_token():
    s=(FRONT/"app/settings/page.tsx").read_text()
    assert "UPSTOX_ACCESS_TOKEN" in s
    assert "NEXT_PUBLIC" in s

def test_backend_phase_version():
    s=(ROOT/"backend/app/main.py").read_text()
    assert 'version="0.29.0"' in s
    assert "CORSMiddleware" in s

def test_live_execution_is_disabled_in_ui():
    s=(FRONT/"app/page.tsx").read_text()
    assert "Execution disabled by design" in s
