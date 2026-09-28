from __future__ import annotations

import os

from .base import LLMProvider
from .http import post_json
from .models import LLMRequest, LLMResponse


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.base_url = base_url.rstrip("/")

    def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        url = (
            f"{self.base_url}/models/{request.model}:generateContent"
            f"?key={self.api_key}"
        )

        payload = {
            "system_instruction": {
                "parts": [{"text": request.system_instruction}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": request.user_input}],
                }
            ],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_output_tokens,
            },
        }

        if request.json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        raw = post_json(
            url,
            payload,
            headers={"Content-Type": "application/json"},
        )

        parts = (
            raw.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )
        text = "".join(
            str(part.get("text", ""))
            for part in parts
        )

        usage = raw.get("usageMetadata") or {}

        return LLMResponse(
            provider=self.name,
            model=request.model,
            text=text,
            raw=raw,
            usage=usage,
        )
