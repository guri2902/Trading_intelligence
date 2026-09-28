from __future__ import annotations

import os

from .base import LLMProvider
from .gemini import GeminiProvider
from .openai_compatible import OpenAICompatibleProvider


class LLMRouter:
    def __init__(self):
        self.providers: dict[str, LLMProvider] = {
            "gemini": GeminiProvider(),
            "openai_compatible": OpenAICompatibleProvider(),
        }

    def get(self, provider: str | None = None) -> LLMProvider:
        name = provider or os.getenv("LLM_PROVIDER", "gemini")
        if name not in self.providers:
            raise ValueError(f"Unknown LLM provider: {name}")
        return self.providers[name]
