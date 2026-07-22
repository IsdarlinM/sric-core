from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RateLimitPolicy:
    global_rps: int = 3
    per_host_rps: int = 2

    def __post_init__(self) -> None:
        if self.global_rps < 1 or self.per_host_rps < 1:
            raise ValueError("rate limits must be >= 1 request per second")


class RateLimitExceeded(RuntimeError):
    pass


class RateLimiter:
    """In-process one-second sliding-window limiter for active executor gates."""

    def __init__(
        self, policy: RateLimitPolicy, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.policy = policy
        self.clock = clock
        self._global: deque[float] = deque()
        self._hosts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @staticmethod
    def _prune(queue: deque[float], now: float) -> None:
        cutoff = now - 1.0
        while queue and queue[0] <= cutoff:
            queue.popleft()

    def acquire(self, host: str) -> None:
        now = self.clock()
        with self._lock:
            host_queue = self._hosts[host]
            self._prune(self._global, now)
            self._prune(host_queue, now)
            if len(self._global) >= self.policy.global_rps:
                raise RateLimitExceeded("global active-request rate limit exceeded")
            if len(host_queue) >= self.policy.per_host_rps:
                raise RateLimitExceeded(f"per-host active-request rate limit exceeded for {host}")
            self._global.append(now)
            host_queue.append(now)
