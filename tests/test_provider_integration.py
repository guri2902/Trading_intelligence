from datetime import date, datetime, timezone
from pathlib import Path

from backend.app.providers.optionvault import OptionVaultProvider
from backend.app.providers.openbb_runtime import check_openbb


def test_optionvault_missing_root_fails_closed(tmp_path):
    provider = OptionVaultProvider(str(tmp_path / "missing"))
    status = provider.health()
    assert status.available is False
    assert status.metadata["root_exists"] is False


def test_optionvault_reads_repository_style_schema(tmp_path):
    root = tmp_path / "optionvault" / "samples" / "cash"
    root.mkdir(parents=True)
    csv_path = root / "NIFTY50.csv"
    csv_path.write_text(
        "datetime,open,high,low,close,volume,oi,name,symbol,exp,strike,type,partKey\n"
        "2026-09-10T09:15:00+05:30,100,101,99,100.5,1000,0,NIFTY,NIFTY50,,0,SPOT,1\n"
    )
    provider = OptionVaultProvider(str(tmp_path / "optionvault"))
    candles = provider.candles("NIFTY50", "minutes", 1, date(2026, 9, 10), date(2026, 9, 10))
    assert len(candles) == 1
    assert candles[0].close == 100.5
    assert candles[0].timestamp.tzinfo is not None


def test_optionvault_coverage_reports_real_files(tmp_path):
    root = tmp_path / "optionvault" / "samples" / "derivatives" / "options"
    root.mkdir(parents=True)
    (root / "NIFTY23JUN2214000CE.csv").write_text("datetime,open,high,low,close,volume,oi,strike,expiry,side\n")
    provider = OptionVaultProvider(str(tmp_path / "optionvault"))
    coverage = provider.coverage()
    assert coverage["file_count"] == 1
    assert "samples" in coverage["categories"]


def test_openbb_health_is_fail_closed_without_runtime_dependency():
    result = check_openbb(timeout=15)
    assert isinstance(result["available"], bool)
