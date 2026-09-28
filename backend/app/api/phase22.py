from fastapi import APIRouter
from .phase22_models import MultiLegBacktestRequest
from ..options_backtest.phase22_engine import MultiLegOptionsBacktestEngine
router=APIRouter(prefix='/phase22',tags=['phase22'])
@router.get('/health')
def health(): return {'status':'ok','phase':22,'mode':'multi_leg_options_backtest','expiry_aware':True,'live_execution':False}
@router.post('/backtest')
def backtest(req: MultiLegBacktestRequest):
    return MultiLegOptionsBacktestEngine().run(req.bars,lambda ctx:req.signal,strategy_name=req.strategy_name,config=req.config).model_dump()
