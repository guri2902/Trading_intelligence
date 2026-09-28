from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from . import __init__ as _unused
from ..db.session import get_db
from ..paper.engine import PaperTradingEngine
from ..paper.models import PaperCloseRequest, PaperMarkRequest, PaperOrderRequest

router = APIRouter(prefix="/phase19", tags=["phase19"])
engine = PaperTradingEngine()

class PaperAccountRequest(BaseModel):
    account_id: str = "default"
    starting_equity: float = Field(gt=0)

@router.get("/health")
def health():
    return {"status":"ok","phase":19,"mode":"paper_trading","live_execution":False}

@router.post("/account")
def account(req: PaperAccountRequest, db: Session = Depends(get_db)):
    return engine.ensure_account(db, req.account_id, req.starting_equity).model_dump(mode="json")

@router.get("/account/{account_id}")
def account_view(account_id: str, db: Session = Depends(get_db)):
    try: return engine.account(db, account_id).model_dump(mode="json")
    except ValueError as e: raise HTTPException(404, str(e))

@router.post("/positions/open")
def open_position(req: PaperOrderRequest, db: Session = Depends(get_db)):
    try: return engine.open(db, req).model_dump(mode="json")
    except ValueError as e: raise HTTPException(400, str(e))

@router.post("/positions/mark")
def mark(req: PaperMarkRequest, db: Session = Depends(get_db)):
    return [p.model_dump(mode="json") for p in engine.mark(db, req)]

@router.post("/positions/close")
def close(req: PaperCloseRequest, db: Session = Depends(get_db)):
    try: return engine.close(db, req).model_dump(mode="json")
    except ValueError as e: raise HTTPException(404, str(e))
