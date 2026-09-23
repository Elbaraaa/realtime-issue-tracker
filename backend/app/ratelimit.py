"""Sliding-window limiter for failed sign-in attempts.

State is in-process, like the WebSocket hub: fine for one API replica. Multiple
replicas would need a shared store such as Redis behind the same interface.
"""

import math
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable


class FailureLimiter:
    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        failures = self._failures[key]
        while failures and failures[0] <= now - self.window:
            failures.popleft()
        if not failures:
            del self._failures[key]
        return failures

    def retry_after(self, key: str) -> int:
        """Seconds until `key` may try again, or 0 if it's allowed now."""
        with self._lock:
            now = self._clock()
            failures = self._prune(key, now)
            if len(failures) < self.limit:
                return 0
            return max(1, math.ceil(failures[0] + self.window - now))

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._failures[key].append(self._clock())

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()
