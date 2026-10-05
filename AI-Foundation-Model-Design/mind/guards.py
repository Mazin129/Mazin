"""
guards — production-reliability primitives (senior review H1 + H4).

FaultCounters: the swallow-and-continue pattern is intentional in a chat assistant
(a degraded answer beats a 500), but the failures were INVISIBLE. These counters make
degradation observable: every swallowed exception notes its module, /api/telemetry
exposes the totals, and the recent tail shows exactly which path degraded last.

AskGate: bounds concurrent /api/ask generations (senior review H4). A locked
browser tab used to queue unbounded slow LLM generations; the gate returns 429
"busy" beyond the cap instead.
"""
from __future__ import annotations

import threading
import time
from collections import deque


class FaultCounters:
    def __init__(self, recent_max=30):
        self._lock = threading.Lock()
        self._by_module = {}
        self._total = 0
        self._recent = deque(maxlen=recent_max)

    def note(self, module, error):
        """Record one swallowed exception. Cheap (O(1)); never raises."""
        try:
            with self._lock:
                self._total += 1
                self._by_module[module] = self._by_module.get(module, 0) + 1
                self._recent.append({"module": module, "error": str(error)[:160],
                                     "ts": time.time()})
        except Exception:
            pass

    def snapshot(self):
        with self._lock:
            return {"total": self._total, "by_module": dict(self._by_module),
                    "recent": list(self._recent)}

    def __len__(self):
        return self._total


class AskGate:
    """Non-blocking concurrency gate for /api/ask (H4). acquire() False → caller
    answers 429 busy. release() on every exit path."""

    def __init__(self, capacity=2):
        self.capacity = max(1, int(capacity))
        self._lock = threading.Lock()
        self._in_flight = 0

    def acquire(self):
        with self._lock:
            if self._in_flight >= self.capacity:
                return False
            self._in_flight += 1
            return True

    def release(self):
        with self._lock:
            self._in_flight = max(0, self._in_flight - 1)

    @property
    def in_flight(self):
        with self._lock:
            return self._in_flight


FAULTS = FaultCounters()
