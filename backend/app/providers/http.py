from __future__ import annotations

import time
from typing import Any

import requests


class HttpClient:
    def __init__(
        self,
        timeout_seconds: float = 15.0,
        retries: int = 3,
        backoff_seconds: float = 0.8,
    ) -> None:
        self.session = requests.Session()
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.backoff_seconds = backoff_seconds

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    timeout=self.timeout_seconds,
                )
                if response.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(
                        f"retryable status={response.status_code}",
                        response=response,
                    )
                response.raise_for_status()
                return response
            except (requests.RequestException, requests.Timeout) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                time.sleep(self.backoff_seconds * (2**attempt))

        raise RuntimeError(f"HTTP request failed after retries: {last_error}")
