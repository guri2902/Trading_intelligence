from .engine import StrategyEngine
from .models import StrategyContext


class StrategyService:
    def __init__(self):
        self.engine = StrategyEngine()

    def evaluate(self, context: StrategyContext, custom_strategy=None):
        return self.engine.evaluate(context, custom_strategy=custom_strategy)
