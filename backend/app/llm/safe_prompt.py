from __future__ import annotations

import json

from .models import StructuredAgentPrompt


FORBIDDEN_INSTRUCTIONS = (
    "invent",
    "fabricate",
    "guess missing",
    "override deterministic",
    "guarantee profit",
)


def build_safe_prompt(prompt: StructuredAgentPrompt) -> tuple[str, str]:
    task_lower = prompt.task.lower()
    for forbidden in FORBIDDEN_INSTRUCTIONS:
        if forbidden in task_lower:
            raise ValueError(
                f"Unsafe/invalid agent task instruction: {forbidden}"
            )

    system = f"""
You are the {prompt.agent_name} specialist in a financial-market research system.

Rules:
1. Use only the structured data provided.
2. Never invent missing numeric facts.
3. Do not override deterministic market calculations.
4. Clearly separate evidence, inference and uncertainty.
5. Return JSON matching the supplied schema.
6. Never claim guaranteed profit or certainty.
7. If evidence is insufficient, return a no-trade/uncertain conclusion.
""".strip()

    user = (
        f"Task:\n{prompt.task}\n\n"
        f"Structured data:\n{json.dumps(prompt.data, default=str, separators=(',', ':'))}\n\n"
        f"Required JSON schema:\n{json.dumps(prompt.output_schema, separators=(',', ':'))}\n\n"
        f"Additional constraints:\n{json.dumps(prompt.constraints)}"
    )

    return system, user
