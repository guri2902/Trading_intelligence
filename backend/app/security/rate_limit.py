
from __future__ import annotations
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Deque, Dict, Tuple


@dataclass
class SlidingWindowLimiter:
    limit: int = 60
    window_seconds: int = 60
    _events: Dict[str, Deque[float]] = field(default_factory=lambda: defaultdict(deque))
    _lock: Lock = field(default_factory=Lock)

    def allow(self, key: str, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            q = self._events[key]
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(current)
            return True

    def remaining(self, key: str, now: float | None = None) -> int:
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            q = self._events[key]
            while q and q[0] <= cutoff:
                q.popleft()
            return max(self.limit - len(q), 0)
