from __future__ import annotations

import os

from .base import LLMProvider
from .http import post_json
from .models import LLMRequest, LLMResponse


class OpenAICompatibleProvider(LLMProvider):
    """
    Generic OpenAI-compatible chat-completions adapter.

    This intentionally supports arbitrary compatible endpoints through:
      LLM_API_BASE_URL
      LLM_API_KEY
    """

    name = "openai_compatible"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = (
            base_url
            or os.getenv("LLM_API_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")

    def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY is not configured")

        payload = {
            "model": request.model,
            "messages": [
                {
                    "role": "system",
                    "content": request.system_instruction,
                },
                {
                    "role": "user",
                    "content": request.user_input,
                },
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }

        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}

        raw = post_json(
            f"{self.base_url}/chat/completions",
            payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        choice = (raw.get("choices") or [{}])[0]
        message = choice.get("message") or {}

        return LLMResponse(
            provider=self.name,
            model=request.model,
            text=str(message.get("content") or ""),
            raw=raw,
            usage=raw.get("usage") or {},
            request_id=raw.get("id"),
        )
