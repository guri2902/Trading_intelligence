from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..research_data.openbb_adapter import OpenBBResearchAdapter
from ..research_data.sentiment import aggregate_sentiment
from ..research_data.models import NewsItem
from ..llm.agent_bridge import LLMResearchBridge
from ..llm.models import StructuredAgentPrompt

router = APIRouter(prefix="/phase14", tags=["phase14"])


class OpenBBRequest(BaseModel):
    symbol: str
    provider: str | None = None
    news_limit: int = 20


class SentimentRequest(BaseModel):
    symbol: str
    items: list[NewsItem]


class LLMResearchRequest(BaseModel):
    model_config = {"populate_by_name": True}

    agent_name: str
    task: str
    data: dict
    output_schema: dict = Field(alias="schema")
    constraints: list[str] = []
    provider: str | None = None
    model: str | None = None


@router.get("/health")
def health():
    adapter = OpenBBResearchAdapter()
    return {
        "openbb": adapter.health(),
        "llm": {
            "gemini_configured": bool(__import__("os").getenv("GEMINI_API_KEY")),
            "openai_compatible_configured": bool(__import__("os").getenv("LLM_API_KEY")),
        },
    }


@router.post("/openbb/research")
def openbb_research(request: OpenBBRequest):
    try:
        adapter = OpenBBResearchAdapter(provider=request.provider)
        fundamentals = adapter.fundamentals(request.symbol)
        news = adapter.company_news(
            request.symbol,
            limit=request.news_limit,
        )
        return {
            "fundamentals": fundamentals.model_dump(mode="json"),
            "news": news.model_dump(mode="json"),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/sentiment/aggregate")
def aggregate(request: SentimentRequest):
    return aggregate_sentiment(
        request.symbol,
        request.items,
    ).model_dump(mode="json")


@router.post("/llm/research")
def llm_research(request: LLMResearchRequest):
    try:
        bridge = LLMResearchBridge()
        return bridge.analyze(
            StructuredAgentPrompt(
                agent_name=request.agent_name,
                task=request.task,
                data=request.data,
                schema=request.output_schema,
                constraints=request.constraints,
            ),
            provider=request.provider,
            model=request.model,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
