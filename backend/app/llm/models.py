from __future__ import annotations

from pydantic import BaseModel, Field


class LLMRequest(BaseModel):
    system_instruction: str
    user_input: str
    model: str
    temperature: float = Field(default=0.0, ge=0, le=2)
    max_output_tokens: int = Field(default=1200, ge=1, le=16000)
    json_mode: bool = True


class LLMResponse(BaseModel):
    provider: str
    model: str
    text: str
    raw: dict = {}
    usage: dict = {}
    request_id: str | None = None


class StructuredAgentPrompt(BaseModel):
    model_config = {"populate_by_name": True}

    agent_name: str
    task: str
    data: dict
    output_schema: dict = Field(alias="schema")
    constraints: list[str] = []
