
from __future__ import annotations
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict

logger = logging.getLogger("trading_intelligence")


def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(message)s",
    )


def audit_event(event: str, **fields: Any) -> None:
    # Never pass secrets/tokens into this function. Sensitive keys are scrubbed.
    sensitive = {"token", "access_token", "authorization", "api_key", "secret", "password"}
    safe = {k: ("[REDACTED]" if k.lower() in sensitive else v) for k, v in fields.items()}
    safe["event"] = event
    logger.info(json.dumps(safe, default=str, separators=(",", ":")))


def request_id() -> str:
    return uuid.uuid4().hex


@dataclass
class RequestTimer:
    started: float = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self.started) * 1000.0
