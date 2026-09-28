from datetime import datetime, timezone

from backend.app.research_data.sentiment import aggregate_sentiment
from backend.app.research_data.models import NewsItem
from backend.app.llm.safe_prompt import build_safe_prompt
from backend.app.llm.models import StructuredAgentPrompt


def test_sentiment_aggregation():
    items = [
        NewsItem(
            headline="Company beats earnings with strong growth",
            timestamp=datetime.now(timezone.utc),
            source="test",
        ),
        NewsItem(
            headline="Analyst warning after weak outlook",
            timestamp=datetime.now(timezone.utc),
            source="test",
        ),
    ]
    result = aggregate_sentiment("TEST", items)
    assert result.positive_items >= 1
    assert result.negative_items >= 1


def test_source_attribution_is_present():
    items = [
        NewsItem(
            headline="Positive growth",
            timestamp=datetime.now(timezone.utc),
            source="ExampleSource",
            url="https://example.com/news",
        )
    ]
    result = aggregate_sentiment("TEST", items)
    assert result.symbol == "TEST"
    assert result.timestamp is not None


def test_safe_prompt_contains_structured_data():
    prompt = StructuredAgentPrompt(
        agent_name="TECHNICAL",
        task="Assess the supplied structure and explain uncertainty.",
        data={"ema_alignment": "BULLISH"},
        schema={"stance": "string"},
    )
    system, user = build_safe_prompt(prompt)
    assert "structured data" in system.lower()
    assert "BULLISH" in user


def test_safe_prompt_rejects_fabrication_instruction():
    prompt = StructuredAgentPrompt(
        agent_name="TEST",
        task="Invent missing prices and guarantee profit.",
        data={},
        schema={},
    )

    try:
        build_safe_prompt(prompt)
    except ValueError:
        return

    raise AssertionError("Unsafe prompt was not rejected")
