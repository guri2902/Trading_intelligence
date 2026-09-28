from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests
from fastapi import APIRouter

router = APIRouter(tags=["Upstox Health"])

UPSTOX_PROFILE_URL = "https://api.upstox.com/v2/user/profile"


def _token() -> str | None:
    token = os.getenv("UPSTOX_ACCESS_TOKEN")
    if not token:
        return None

    token = token.strip()
    return token or None


def _safe_error(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None

    data = payload.get("errors")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            return (
                first.get("message")
                or first.get("errorCode")
                or first.get("code")
            )

    if isinstance(data, dict):
        return data.get("message") or data.get("error")

    return payload.get("message") or payload.get("error")


@router.get("/ui/upstox-health")
def upstox_health() -> dict[str, Any]:
    """
    Real Upstox authentication/REST health check.

    This endpoint deliberately does not expose the access token.
    It validates the configured token against Upstox's profile endpoint.
    """
    checked_at = datetime.now(timezone.utc).isoformat()

    token = _token()
    if not token:
        return {
            "provider": "upstox",
            "configured": False,
            "authenticated": False,
            "rest_api": "NOT_READY",
            "status": "NOT_CONFIGURED",
            "checked_at": checked_at,
            "http_status": None,
            "message": "UPSTOX_ACCESS_TOKEN is not configured.",
            "profile": None,
        }

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

    try:
        response = requests.get(
            UPSTOX_PROFILE_URL,
            headers=headers,
            timeout=10,
        )
    except requests.Timeout:
        return {
            "provider": "upstox",
            "configured": True,
            "authenticated": False,
            "rest_api": "TIMEOUT",
            "status": "UNREACHABLE",
            "checked_at": checked_at,
            "http_status": None,
            "message": "Upstox profile request timed out.",
            "profile": None,
        }
    except requests.RequestException as exc:
        return {
            "provider": "upstox",
            "configured": True,
            "authenticated": False,
            "rest_api": "ERROR",
            "status": "UNREACHABLE",
            "checked_at": checked_at,
            "http_status": None,
            "message": f"Upstox request failed: {exc}",
            "profile": None,
        }

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.ok:
        data = payload.get("data") if isinstance(payload, dict) else None
        data = data if isinstance(data, dict) else {}

        profile = {
            "email": data.get("email"),
            "user_name": data.get("user_name"),
            "user_type": data.get("user_type"),
            "is_active": data.get("is_active"),
            "exchanges": data.get("exchanges") or [],
            "products": data.get("products") or [],
            "order_types": data.get("order_types") or [],
        }

        return {
            "provider": "upstox",
            "configured": True,
            "authenticated": True,
            "rest_api": "OK",
            "status": "CONNECTED",
            "checked_at": checked_at,
            "http_status": response.status_code,
            "message": "Upstox access token validated successfully.",
            "profile": profile,
        }

    message = _safe_error(payload)

    if response.status_code in (401, 403):
        status = "AUTH_FAILED"
        rest_api = "REACHABLE"
        if not message:
            message = "Upstox rejected the access token."
    else:
        status = "API_ERROR"
        rest_api = "REACHABLE"
        if not message:
            message = f"Upstox returned HTTP {response.status_code}."

    return {
        "provider": "upstox",
        "configured": True,
        "authenticated": False,
        "rest_api": rest_api,
        "status": status,
        "checked_at": checked_at,
        "http_status": response.status_code,
        "message": message,
        "profile": None,
    }
