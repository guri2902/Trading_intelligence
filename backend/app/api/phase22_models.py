from pydantic import BaseModel, Field
from ..options_backtest.models import HistoricalOptionBar
from ..options_backtest.phase22_models import MultiLegOptionsBacktestConfig
class MultiLegBacktestRequest(BaseModel):
    strategy_name:str=Field(min_length=1)
    bars:list[HistoricalOptionBar]=Field(min_length=1)
    signal:dict
    config:MultiLegOptionsBacktestConfig=Field(default_factory=MultiLegOptionsBacktestConfig)
