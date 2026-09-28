from __future__ import annotations

from typing import Any

import requests


def post_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str],
    timeout: float = 60,
) -> dict:
    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()
