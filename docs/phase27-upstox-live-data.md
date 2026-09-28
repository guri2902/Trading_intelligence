
# Phase 27 — Upstox Live Market Data

Uses Upstox's current Market Data Feed V3 boundary. V3 uses an authorized
WebSocket, binary subscription messages, and Protobuf market messages. The
adapter supports the documented subscription modes and normalizes LTPC,
best bid/ask, volume, OI, IV and option Greeks when present.

The adapter deliberately does not place orders. Live execution remains
disabled. Ticks can be rejected as stale or crossed before entering the
authoritative validation/feature/signal pipeline.
