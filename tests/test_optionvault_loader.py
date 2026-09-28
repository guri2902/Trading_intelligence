from pathlib import Path

from backend.app.options_backtest.optionvault_loader import OptionVaultLoader


def test_optionvault_loader_maps_real_schema(tmp_path: Path):
    root = tmp_path / "data" / "optionvault"
    p = root / "samples" / "derivatives" / "options"
    p.mkdir(parents=True)
    f = p / "NIFTY23JUN2214000CE.csv"
    f.write_text(
        "datetime,open,high,low,close,volume,oi,name,symbol,strike,expiry,contract_type,side\n"
        "2023-06-01T09:15:00+05:30,100,105,99,103,1000,20000,NIFTY,NIFTY23JUN2214000CE,21400,2023-06-29,OPT,CE\n",
        encoding="utf-8",
    )
    rows = OptionVaultLoader(root).load_contract(f)
    assert len(rows) == 1
    assert rows[0].close == 103
    assert rows[0].option_type == "CE"
    assert rows[0].strike == 21400


def test_optionvault_loader_rejects_outside_root(tmp_path: Path):
    root = tmp_path / "data" / "optionvault"
    root.mkdir(parents=True)
    outside = tmp_path / "outside.csv"
    outside.write_text("x", encoding="utf-8")
    try:
        OptionVaultLoader(root).load_contract(outside)
    except ValueError as exc:
        assert str(exc) == "OPTIONVAULT_PATH_OUTSIDE_ROOT"
    else:
        raise AssertionError("outside path accepted")
