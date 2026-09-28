from .engine import FeatureEngine
from .multitimeframe import build_multitimeframe_snapshot

class FeatureService:
    def __init__(self): self.engine=FeatureEngine()
    def calculate(self, rows, session_ids=None):
        return self.engine.calculate(rows, session_ids=session_ids)
    def calculate_multi_timeframe(self, rows_by_timeframe, session_ids_by_timeframe=None):
        result={}
        for tf, rows in rows_by_timeframe.items():
            sessions=session_ids_by_timeframe.get(tf) if session_ids_by_timeframe else None
            result[tf]=self.engine.calculate(rows, session_ids=sessions)
        return build_multitimeframe_snapshot(result)
