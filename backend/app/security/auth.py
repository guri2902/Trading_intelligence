
from __future__ import annotations
import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


def _hash_token(token: str) -> str:
    pepper = os.getenv("APP_AUTH_PEPPER", "")
    return hashlib.sha256((pepper + token).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Principal:
    subject: str
    scopes: frozenset[str]


class APIKeyAuthenticator:
    """
    Server-side API-key authenticator. Raw tokens are never logged or stored.
    Configure APP_API_KEYS as comma-separated subject:token[:scope1|scope2...].
    """

    def __init__(self, raw_config: str | None = None):
        raw_config = raw_config if raw_config is not None else os.getenv("APP_API_KEYS", "")
        self._keys = {}
        for entry in raw_config.split(","):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split(":")
            if len(parts) < 2:
                continue
            subject, token = parts[0], parts[1]
            scopes = frozenset(parts[2].split("|")) if len(parts) >= 3 and parts[2] else frozenset()
            self._keys[_hash_token(token)] = Principal(subject=subject, scopes=scopes)

    def authenticate(self, token: str) -> Principal | None:
        candidate = _hash_token(token)
        for stored, principal in self._keys.items():
            if hmac.compare_digest(stored, candidate):
                return principal
        return None

_bearer = HTTPBearer(auto_error=False)

def require_scopes(required: Iterable[str] = ()):
    required = frozenset(required)
    async def dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> Principal:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
        principal = APIKeyAuthenticator().authenticate(credentials.credentials)
        if principal is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
        missing = required - principal.scopes
        if missing:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient scope")
        return principal
    return dependency
