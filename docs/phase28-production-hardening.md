# Phase 28 — Production API / Monitoring / Security

## Security controls
- Bearer API-key authentication with constant-time token comparison.
- Scope-based authorization helper.
- Raw tokens are not persisted or written to audit logs.
- Secrets are read from environment variables.
- Request validation remains in Pydantic/FastAPI models.
- Sliding-window per-client/path rate limiting.
- Security response headers.
- Request IDs for correlation.

## Observability
- Structured JSON audit events.
- Request latency and HTTP status logging.
- Health, readiness and metrics endpoints.

## Execution safety
Live order execution remains disabled. Phase 28 does not add broker order
submission and cannot turn it on through an API request.
