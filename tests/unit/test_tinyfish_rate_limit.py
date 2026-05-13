"""Tests for :class:`SlidingWindowRateLimiter` — Story 3.5 component.

The limiter is tested in isolation here so the fetcher tests can
focus on adapter behaviour, not window arithmetic. A controllable
clock makes every assertion deterministic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from hardware_hunter.adapters.wallapop_tinyfish.rate_limit import (
    SlidingWindowRateLimiter,
)


class _Clock:
    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now = self.now + timedelta(**kwargs)


def test_allows_up_to_limit_without_recording() -> None:
    clock = _Clock()
    limiter = SlidingWindowRateLimiter(limit=3, window=timedelta(minutes=1), clock=clock)
    # `allow` is a pure query — repeated calls without `record` keep returning True.
    for _ in range(10):
        assert limiter.allow() is True


def test_record_advances_count_toward_limit() -> None:
    clock = _Clock()
    limiter = SlidingWindowRateLimiter(limit=2, window=timedelta(minutes=1), clock=clock)
    limiter.record()
    assert limiter.allow() is True
    limiter.record()
    assert limiter.allow() is False


def test_window_slides_forward_evicting_old_events() -> None:
    clock = _Clock()
    limiter = SlidingWindowRateLimiter(limit=2, window=timedelta(minutes=1), clock=clock)
    limiter.record()
    limiter.record()
    assert limiter.allow() is False
    clock.advance(seconds=61)
    # Both prior events aged out of the window → budget refills.
    assert limiter.allow() is True


def test_retry_after_seconds_returns_time_until_oldest_ages_out() -> None:
    clock = _Clock()
    limiter = SlidingWindowRateLimiter(limit=1, window=timedelta(seconds=60), clock=clock)
    limiter.record()
    clock.advance(seconds=20)
    # 40 more seconds until the only event ages out.
    assert limiter.retry_after_seconds() == pytest.approx(40.0)


def test_retry_after_seconds_zero_when_budget_free() -> None:
    clock = _Clock()
    limiter = SlidingWindowRateLimiter(limit=2, window=timedelta(minutes=1), clock=clock)
    assert limiter.retry_after_seconds() == 0.0
    limiter.record()
    # Still room → 0.
    assert limiter.retry_after_seconds() == 0.0


def test_limit_must_be_at_least_one() -> None:
    with pytest.raises(ValueError, match="limit must be >= 1"):
        SlidingWindowRateLimiter(limit=0, window=timedelta(minutes=1))
