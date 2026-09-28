from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AgentInput, AgentVerdict


class BaseAgent(ABC):
    name: str

    @abstractmethod
    def evaluate(self, data: AgentInput) -> AgentVerdict:
        raise NotImplementedError

    @staticmethod
    def evidence(source: str, statement: str, strength: float) -> dict:
        return {
            "source": source,
            "statement": statement,
            "strength": max(0.0, min(100.0, strength)),
        }
