import pytest

from sric.rate_limit import RateLimitExceeded, RateLimiter, RateLimitPolicy


def test_per_host_rate_limit_and_window_reset() -> None:
    now = [100.0]
    limiter = RateLimiter(RateLimitPolicy(global_rps=3, per_host_rps=2), clock=lambda: now[0])
    limiter.acquire("a.example")
    limiter.acquire("a.example")
    with pytest.raises(RateLimitExceeded, match="per-host"):
        limiter.acquire("a.example")
    now[0] += 1.01
    limiter.acquire("a.example")


def test_global_rate_limit() -> None:
    limiter = RateLimiter(RateLimitPolicy(global_rps=2, per_host_rps=2), clock=lambda: 1.0)
    limiter.acquire("a.example")
    limiter.acquire("b.example")
    with pytest.raises(RateLimitExceeded, match="global"):
        limiter.acquire("c.example")
