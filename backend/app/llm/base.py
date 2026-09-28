from __future__ import annotations

from abc import ABC, abstractmethod

from .models import LLMRequest, LLMResponse


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError
