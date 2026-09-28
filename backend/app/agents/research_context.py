from __future__ import annotations

from typing import Any

from ..research_data.models import ResearchBundle
from .models import AgentInput


def enrich_agent_input(data: AgentInput, bundle: ResearchBundle | None) -> AgentInput:
    """Merge sourced research into the agent input without changing deterministic fields."""
    if bundle is None:
        return data
    patch: dict[str, Any] = {}
    if bundle.fundamentals:
        patch["fundamentals"] = bundle.fundamentals.model_dump(mode="json")
    if bundle.sentiment:
        patch["sentiment"] = bundle.sentiment.model_dump(mode="json")
    if bundle.news:
        patch["news"] = bundle.news.model_dump(mode="json")
    return data.model_copy(update=patch)
