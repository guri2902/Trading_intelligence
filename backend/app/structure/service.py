from .engine import MarketStructureEngine


class StructureService:
    def __init__(self):
        self.engine = MarketStructureEngine()

    def analyze(self, rows):
        return self.engine.analyze(rows)
