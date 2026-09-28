
import asyncio
from backend.app.security.auth import APIKeyAuthenticator
from backend.app.security.rate_limit import SlidingWindowLimiter
from backend.app.security.observability import audit_event
from api.phase28 import health, readiness, metrics


def test_api_key_auth_and_scope():
    a=APIKeyAuthenticator("alice:supersecret:read|trade")
    p=a.authenticate("supersecret")
    assert p is not None and p.subject=="alice" and "trade" in p.scopes
    assert a.authenticate("wrong") is None


def test_rate_limiter():
    l=SlidingWindowLimiter(limit=2,window_seconds=60)
    assert l.allow("x",0)
    assert l.allow("x",1)
    assert not l.allow("x",2)
    assert l.remaining("x",2)==0
    assert l.allow("x",61)


def test_health_execution_off():
    assert health()["execution_enabled"] is False


def test_readiness_execution_off():
    r=readiness()
    assert r["checks"]["live_execution_enabled"] is False


def test_metrics_execution_off():
    assert metrics()["live_execution_enabled"]==0
