"""Daily-quota tracker for the eBay adapter — Story 3.7 / NFR-I5.

Counts requests issued since the last UTC-midnight boundary. The
adapter consults the tracker before each call: if the next request
would exceed the configured budget, the tracker refuses and the
fetcher raises :class:`EbayQuotaExceeded`.

The tracker is intentionally in-memory only — no disk persistence. The
daemon restarts crisply on SIGTERM (FR50), and a fresh boot mid-day
losing the count is fine: the eBay rate-limit is *eBay's* concern, not
the daemon's; our budget is the operator's belt-and-braces.
"""

from __future__ import annotations

from datetime import UTC, date, datetime


class DailyQuotaTracker:
    """Single-marketplace, single-day request budget."""

    def __init__(self, budget: int) -> None:
        if budget < 1:
            raise ValueError("daily quota must be >= 1")
        self._budget = budget
        self._date: date | None = None
        self._used = 0

    @property
    def budget(self) -> int:
        return self._budget

    @property
    def used(self) -> int:
        """Requests counted against today's window (after the latest reset)."""
        return self._used

    def remaining(self, *, now: datetime | None = None) -> int:
        """Requests still available in today's window."""
        self._maybe_reset(now)
        return max(0, self._budget - self._used)

    def can_consume(self, *, now: datetime | None = None) -> bool:
        """``True`` if a request can be charged against the budget."""
        return self.remaining(now=now) > 0

    def consume(self, *, now: datetime | None = None) -> None:
        """Charge one request.

        Caller is expected to gate via :meth:`can_consume` first; this
        method does not raise (it would inflate the call-site
        complexity for no win). If the caller forgets, ``used`` simply
        exceeds ``budget`` and ``remaining`` clamps to 0.
        """
        self._maybe_reset(now)
        self._used += 1

    def _maybe_reset(self, now: datetime | None) -> None:
        moment = now if now is not None else datetime.now(UTC)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        today = moment.astimezone(UTC).date()
        if self._date != today:
            self._date = today
            self._used = 0
