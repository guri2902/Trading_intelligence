from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..options_backtest.optionvault_loader import OptionVaultLoader

router = APIRouter(prefix="/backtest/optionvault", tags=["OptionVault Backtest"])


class ContractLoadRequest(BaseModel):
    path: str = Field(min_length=1)


@router.get("/coverage")
def coverage():
    loader = OptionVaultLoader()
    contracts = loader.discover_contracts()
    return {
        "root": str(Path(loader.root_dir)),
        "root_exists": loader.root_dir.exists(),
        "option_file_count": len(loader.option_files()),
        "contracts": [c.__dict__ for c in contracts],
        "data_source": "OptionVault",
        "synthetic_prices": False,
    }


@router.post("/load")
def load_contract(req: ContractLoadRequest):
    try:
        rows = OptionVaultLoader().load_contract(req.path)
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=422, detail="OPTIONVAULT_NO_VALID_ROWS")
    return {
        "contract_key": rows[0].contract_key,
        "underlying": rows[0].underlying_symbol,
        "expiry": rows[0].expiry.isoformat(),
        "strike": rows[0].strike,
        "option_type": rows[0].option_type,
        "rows": len(rows),
        "first_timestamp": rows[0].timestamp.isoformat(),
        "last_timestamp": rows[-1].timestamp.isoformat(),
        "used_actual_option_prices": True,
        "synthetic_prices": False,
    }
