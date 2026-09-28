
from __future__ import annotations
import os
import platform
from typing import Any, Dict
from fastapi import APIRouter
router = APIRouter(prefix="/phase28", tags=["phase28"])


@router.get("/health")
def health() -> Dict[str, Any]:
    return {
        "phase": "28",
        "status": "ok",
        "service": "trading-intelligence-platform",
        "execution_enabled": False,
        "environment": os.getenv("APP_ENV", "development"),
        "python": platform.python_version(),
    }


@router.get("/readiness")
def readiness() -> Dict[str, Any]:
    token_ok = bool(os.getenv("UPSTOX_ACCESS_TOKEN"))
    db_url = os.getenv("DATABASE_URL", "sqlite://")
    return {
        "ready": True,
        "checks": {
            "database_configured": bool(db_url),
            "upstox_configured": token_ok,
            "live_execution_enabled": False,
        },
    }


@router.get("/metrics")
def metrics() -> Dict[str, Any]:
    # Lightweight JSON metrics endpoint; Prometheus export can wrap this later.
    return {
        "service_up": 1,
        "live_execution_enabled": 0,
        "phase": 28,
    }
