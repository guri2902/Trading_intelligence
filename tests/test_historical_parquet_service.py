from datetime import date
from pathlib import Path

from backend.app.data.historical_parquet import HistoricalParquetDataService, HistoricalQuery


def test_missing_root_returns_empty(tmp_path: Path):
    service = HistoricalParquetDataService(str(tmp_path / "missing"))
    assert service.health()["root_exists"] is False
    assert service.query_options(HistoricalQuery(symbol="NIFTY")) == []
