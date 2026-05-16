"""Client-side sliding-window rate limiter for the TinyFish path.

TinyFish publishes a 5 req/min cap on its Search API and "higher but
undocumented" on Agent. We enforce 5/min client-side regardless —
per NFR-I2's "never trust remote alone" rule — so a tight poll loop
can't accidentally burn through the budget and get rate-limited mid-cycle.

The window is in-memory only. A daemon restart re-arms the counter,
which is fine: at restart we don't know what was sent before, and the
server-side limiter is the ultimate authority.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SlidingWindowRateLimiter:
    """Counts events in a rolling :attr:`window`. ``allow()`` returns
    True iff a new event would keep the count ``<= limit``."""

    def __init__(
        self,
        *,
        limit: int,
        window: timedelta,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if limit < 1:
            raise ValueError(f"limit must be >= 1; got {limit}")
        self._limit = limit
        self._window = window
        self._clock = clock
        self._events: deque[datetime] = deque()

    def allow(self) -> bool:
        """Return True if a new event fits inside the window's budget.

        Does NOT record the event — the caller should call
        :meth:`record` after the underlying operation succeeds (or
        even on failure, to avoid retry storms after a rate-limit-hit).
        """
        self._evict()
        return len(self._events) < self._limit

    def record(self) -> None:
        """Append a new event at the current clock value."""
        self._events.append(self._clock())
        self._evict()

    def retry_after_seconds(self) -> float:
        """When ``allow()`` is False, how long until the oldest in-window
        event ages out — i.e. the soonest a new call could succeed."""
        self._evict()
        if not self._events or len(self._events) < self._limit:
            return 0.0
        oldest = self._events[0]
        return max(0.0, (oldest + self._window - self._clock()).total_seconds())

    def _evict(self) -> None:
        threshold = self._clock() - self._window
        while self._events and self._events[0] < threshold:
            self._events.popleft()
