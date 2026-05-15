"""Reconciler orchestrator tests — Story 5.4.

The pure math is covered in ``test_reconciliation.py``; this module
exercises the wiring: the cross-source fetch happens via the injected
fetcher, the receipt-vs-alert path is sync and reads the right fields,
and a fetcher failure propagates so the buy orchestrator can fail-closed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from hardware_hunter.domain.alert import AlertSnapshot
from hardware_hunter.domain.evaluation import ListingEvaluation
from hardware_hunter.domain.listing import Listing, SearchQuery
from hardware_hunter.domain.phase2_audit import TransactionRecord
from hardware_hunter.interfaces.page_fetcher import PageFetcher
from hardware_hunter.orchestration.reconciler import Reconciler

_T0 = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_ENTRY_KEY = ("Western Digital", "WD Red Plus 4TB", "WD40EFPX")
_ALERT_ID = UUID("12345678-1234-1234-1234-123456789abc")
_LISTING_URL = "https://es.wallapop.com/item/abc123"


def _listing(price: str) -> Listing:
    return Listing(
        listing_id="abc123",
        marketplace="wallapop",
        url=_LISTING_URL,
        title="WD Red Plus 4TB",
        description="ok",
        price_eur=Decimal(price),
        location="Madrid",
        photo_urls=[],
        fetched_at=_T0,
    )


def _alert_snapshot(price: str) -> AlertSnapshot:
    return AlertSnapshot(
        alert_id=_ALERT_ID,
        entry_key=_ENTRY_KEY,
        entry_display_name="WD Red Plus 4TB",
        listing=_listing(price),
        evaluation=ListingEvaluation(
            listing_id="abc123",
            entry_key=_ENTRY_KEY,
            confidence="high",
            one_line_take="Strong match.",
            is_container=False,
            evaluated_at=_T0,
        ),
        phase="phase2",
        phase2_max_price_eur=Decimal("60.00"),
        rendered_at=_T0,
    )


def _transaction(price: str) -> TransactionRecord:
    return TransactionRecord(
        alert_id=_ALERT_ID,
        price_paid_eur=Decimal(price),
        payment_method="wallapop_pay",
        receipt_id="WP-2026-0001",
        screenshot_path="/app/data/screenshots/x.png",
        total_seconds=42,
        committed_at=_T0,
    )


class _ScriptedFetcher(PageFetcher):
    """Returns a preloaded listing (or raises) on every ``fetch`` call."""

    def __init__(self, *, response: Listing | BaseException) -> None:
        self._response = response
        self.fetch_calls: list[str] = []

    async def search(self, query: SearchQuery) -> list[Listing]:  # pragma: no cover
        raise AssertionError("reconciler should not call search()")

    async def fetch(self, listing_url: str) -> Listing:
        self.fetch_calls.append(listing_url)
        if isinstance(self._response, BaseException):
            raise self._response
        return self._response


def _reconciler(fetcher: PageFetcher) -> Reconciler:
    return Reconciler(
        cross_source_fetcher=fetcher,
        tolerance_eur=Decimal("1.00"),
        tolerance_pct=Decimal("5"),
    )


# ─────────────────────────────────────────────────────────────────────────
# Cross-source reconciliation
# ─────────────────────────────────────────────────────────────────────────


async def test_cross_source_pass_when_prices_agree() -> None:
    fetcher = _ScriptedFetcher(response=_listing("55.50"))
    reconciler = _reconciler(fetcher)

    outcome = await reconciler.reconcile_cross_source(_listing("55.00"))

    assert outcome.result.passed is True
    assert outcome.primary_price_eur == Decimal("55.00")
    assert outcome.cross_source_price_eur == Decimal("55.50")
    assert fetcher.fetch_calls == [_LISTING_URL]


async def test_cross_source_q9_scenario_fails() -> None:
    """API says 53.00 €, the cross-source path returns 0.53 € — Q9 caught."""
    fetcher = _ScriptedFetcher(response=_listing("0.53"))
    reconciler = _reconciler(fetcher)

    outcome = await reconciler.reconcile_cross_source(_listing("53.00"))

    assert outcome.result.passed is False
    assert outcome.result.delta_eur == Decimal("52.47")
    assert outcome.primary_price_eur == Decimal("53.00")
    assert outcome.cross_source_price_eur == Decimal("0.53")


async def test_cross_source_fetch_failure_propagates() -> None:
    """Reconciliation is fail-closed: if we can't verify, we don't pay."""
    fetcher = _ScriptedFetcher(response=RuntimeError("alternate path down"))
    reconciler = _reconciler(fetcher)

    with pytest.raises(RuntimeError, match="alternate path down"):
        await reconciler.reconcile_cross_source(_listing("55.00"))


# ─────────────────────────────────────────────────────────────────────────
# Receipt-vs-alert reconciliation
# ─────────────────────────────────────────────────────────────────────────


def test_receipt_matches_alert_within_tolerance() -> None:
    fetcher = _ScriptedFetcher(response=_listing("0.00"))  # unused on this path
    reconciler = _reconciler(fetcher)

    result = reconciler.reconcile_receipt_vs_alert(_alert_snapshot("55.00"), _transaction("55.50"))
    assert result.passed is True


def test_receipt_mismatch_caught() -> None:
    fetcher = _ScriptedFetcher(response=_listing("0.00"))
    reconciler = _reconciler(fetcher)

    result = reconciler.reconcile_receipt_vs_alert(_alert_snapshot("48.00"), _transaction("56.00"))
    assert result.passed is False
    assert result.delta_eur == Decimal("8.00")
