
from __future__ import annotations
import os
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .security.rate_limit import SlidingWindowLimiter
from .security.observability import audit_event, request_id


class ProductionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: SlidingWindowLimiter | None = None):
        super().__init__(app)
        self.limiter = limiter or SlidingWindowLimiter(
            limit=int(os.getenv("RATE_LIMIT_PER_MINUTE", "120")),
            window_seconds=60,
        )

    async def dispatch(self, request, call_next):
        rid = request.headers.get("X-Request-ID") or request_id()
        client = request.client.host if request.client else "unknown"
        key = f"{client}:{request.url.path}"
        if not self.limiter.allow(key):
            audit_event("rate_limit_rejected", request_id=rid, path=request.url.path)
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded", "request_id": rid},
                headers={"X-Request-ID": rid, "Retry-After": "60"},
            )
        started = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed = (time.perf_counter() - started) * 1000
            audit_event(
                "http_request",
                request_id=rid,
                method=request.method,
                path=request.url.path,
                status_code=getattr(response, "status_code", 500),
                latency_ms=round(elapsed, 2),
            )
            if response is not None:
                response.headers["X-Request-ID"] = rid
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["X-Frame-Options"] = "DENY"
                response.headers["Referrer-Policy"] = "no-referrer"
                response.headers["Cache-Control"] = "no-store"
