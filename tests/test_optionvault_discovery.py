from backend.app.api.optionvault_discovery import _iso


def test_iso_timestamp():
    assert _iso("2026-09-11T10:45:00+05:30") == "2026-09-11"
