
from typing import Any,Dict,List
from fastapi import APIRouter
from pydantic import BaseModel,Field
from backend.app.live.upstox_feed import UpstoxLiveFeed
router=APIRouter(prefix="/phase27",tags=["phase27"])
class LiveStatusRequest(BaseModel):
    instrument_keys:List[str]=Field(default_factory=list); mode:str="full"
@router.get("/health")
def health()->Dict[str,Any]:
    f=UpstoxLiveFeed()
    return {"phase":"27","status":"ok","provider":"upstox","credentials_configured":bool(f.access_token),"execution_enabled":False,"market_data_only":True}
@router.post("/validate-config")
def validate_config(req:LiveStatusRequest)->Dict[str,Any]:
    return {"provider":"upstox","credentials_configured":bool(UpstoxLiveFeed().access_token),"instrument_count":len(set(req.instrument_keys)),"mode":req.mode,"valid_mode":req.mode in {"ltpc","option_greeks","full","full_d30"},"execution_enabled":False}
