from __future__ import annotations

import json

from .models import LLMRequest, StructuredAgentPrompt
from .router import LLMRouter
from .safe_prompt import build_safe_prompt


class LLMResearchBridge:
    def __init__(self, router: LLMRouter | None = None):
        self.router = router or LLMRouter()

    def analyze(
        self,
        prompt: StructuredAgentPrompt,
        *,
        provider: str | None = None,
        model: str | None = None,
    ):
        system, user = build_safe_prompt(prompt)
        response = self.router.get(provider).generate(
            LLMRequest(
                system_instruction=system,
                user_input=user,
                model=model or "default",
                temperature=0.0,
                max_output_tokens=1200,
                json_mode=True,
            )
        )

        try:
            parsed = json.loads(response.text)
        except json.JSONDecodeError:
            parsed = {"raw_text": response.text}

        return {
            "response": parsed,
            "provider": response.provider,
            "model": response.model,
            "usage": response.usage,
            "request_id": response.request_id,
        }
