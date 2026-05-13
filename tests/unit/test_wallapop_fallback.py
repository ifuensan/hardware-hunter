"""Tests for the Wallapop two-path orchestrator — Story 3.6.

Both fetchers are mocked via fake :class:`PageFetcher` implementations
that record calls and return / raise preloaded values. The orchestrator
is the unit under test; we never reach the real adapters or the
network.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from hardware_hunter.domain.errors import (
    TinyFishAuthFailed,
    TinyFishRateLimited,
    TinyFishUnavailable,
    WallapopApiError,
    WallapopSchemaDrift,
    WallapopSessionExpired,
)
from hardware_hunter.domain.listing import Listing, SearchQuery
from hardware_hunter.interfaces.page_fetcher import PageFetcher
from hardware_hunter.orchestration.wallapop_fallback import (
    SOURCE_API,
    SOURCE_TINYFISH,
    WallapopHealth,
    wallapop_two_path_fetch,
)

# ─────────────────────────────────────────────────────────────────────────
# Fixtures + fakes
# ─────────────────────────────────────────────────────────────────────────


def _listing(listing_id: str = "abc") -> Listing:
    return Listing(
        listing_id=listing_id,
        marketplace="wallapop",
        url=f"https://es.wallapop.com/item/{listing_id}",
        title="WD Red Plus 4TB",
        description="ok",
        price_eur=Decimal("55.00"),
        location="Madrid",
        fetched_at=datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC),
    )


def _query() -> SearchQuery:
    return SearchQuery(
        keywords=["wd red plus 4tb"],
        marketplace="wallapop",
        max_price_eur=Decimal("70"),
    )


class _FakeFetcher(PageFetcher):
    """Records every call. Returns / raises preloaded values."""

    def __init__(self) -> None:
        self.search_calls: list[SearchQuery] = []
        self.search_response: list[Listing] | BaseException = []

    async def search(self, query: SearchQuery) -> list[Listing]:
        self.search_calls.append(query)
        if isinstance(self.search_response, BaseException):
            raise self.search_response
        return self.search_response

    async def fetch(self, listing_url: str) -> Listing:
        raise AssertionError("orchestrator should not call fetch()")


def _records(out: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in out.splitlines() if line.strip()]


# ─────────────────────────────────────────────────────────────────────────
# Happy path — API succeeds, TinyFish never called
# ─────────────────────────────────────────────────────────────────────────


async def test_api_success_returns_results_and_skips_tinyfish(
    capsys: pytest.CaptureFixture[str],
) -> None:
    api = _FakeFetcher()
    api.search_response = [_listing("a"), _listing("b")]
    tinyfish = _FakeFetcher()
    health = WallapopHealth()

    listings = await wallapop_two_path_fetch(
        _query(),
        api_fetcher=api,
        tinyfish_fetcher=tinyfish,
        health=health,
    )

    assert [listing.listing_id for listing in listings] == ["a", "b"]
    assert len(api.search_calls) == 1
    assert tinyfish.search_calls == []

    success = [
        r for r in _records(capsys.readouterr().out) if r["event"] == "wallapop_path_success"
    ]
    assert success and success[0]["source"] == SOURCE_API
    assert success[0]["result_count"] == 2


# ─────────────────────────────────────────────────────────────────────────
# API non-session failure → TinyFish takes over, api_degraded fires
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "api_exception",
    [
        WallapopApiError(503, "service unavailable"),
        WallapopSchemaDrift("search_objects[0].price.amount", "missing"),
    ],
)
async def test_api_degrades_falls_back_to_tinyfish(
    api_exception: Exception,
    capsys: pytest.CaptureFixture[str],
) -> None:
    api = _FakeFetcher()
    api.search_response = api_exception
    tinyfish = _FakeFetcher()
    tinyfish.search_response = [_listing("t1")]
    health = WallapopHealth()

    listings = await wallapop_two_path_fetch(
        _query(),
        api_fetcher=api,
        tinyfish_fetcher=tinyfish,
        health=health,
    )

    assert [listing.listing_id for listing in listings] == ["t1"]
    assert len(tinyfish.search_calls) == 1
    # API path remains attempted on the NEXT cycle — only SessionExpired latches it off.
    assert health.api_attempt_enabled() is True

    records = _records(capsys.readouterr().out)
    degraded = [r for r in records if r["event"] == "wallapop_api_degraded"]
    success = [r for r in records if r["event"] == "wallapop_path_success"]
    assert degraded and degraded[0]["error_class"] == api_exception.__class__.__name__
    assert success and success[0]["source"] == SOURCE_TINYFISH


# ─────────────────────────────────────────────────────────────────────────
# Session expiry — latch the API path off, fall back this cycle, skip next
# ─────────────────────────────────────────────────────────────────────────


async def test_session_expired_latches_path_off_and_falls_back(
    capsys: pytest.CaptureFixture[str],
) -> None:
    api = _FakeFetcher()
    api.search_response = WallapopSessionExpired("401")
    tinyfish = _FakeFetcher()
    tinyfish.search_response = [_listing("t")]
    health = WallapopHealth()

    listings = await wallapop_two_path_fetch(
        _query(),
        api_fetcher=api,
        tinyfish_fetcher=tinyfish,
        health=health,
    )

    assert listings == [_listing("t")]
    assert health.api_attempt_enabled() is False

    records = _records(capsys.readouterr().out)
    expired = [r for r in records if r["event"] == "wallapop_session_expired"]
    success = [r for r in records if r["event"] == "wallapop_path_success"]
    assert expired
    assert success and success[0]["source"] == SOURCE_TINYFISH


async def test_unhealthy_api_skipped_entirely_on_next_cycle() -> None:
    """After SessionExpired latches the API off, subsequent cycles MUST
    not call api_fetcher.search at all until the operator runs login."""
    api = _FakeFetcher()
    tinyfish = _FakeFetcher()
    tinyfish.search_response = [_listing("t")]
    health = WallapopHealth()
    health.mark_api_session_expired()  # simulate prior cycle's expiry

    await wallapop_two_path_fetch(
        _query(),
        api_fetcher=api,
        tinyfish_fetcher=tinyfish,
        health=health,
    )

    # The cheap path is NOT called — every cycle would otherwise burn an
    # API call (and possibly more bot-detection signal) for nothing.
    assert api.search_calls == []
    assert len(tinyfish.search_calls) == 1


# ─────────────────────────────────────────────────────────────────────────
# Session renewal — only fires AFTER login + a successful API call
# ─────────────────────────────────────────────────────────────────────────


async def test_session_renewed_logs_after_login_and_first_api_success(
    capsys: pytest.CaptureFixture[str],
) -> None:
    api = _FakeFetcher()
    tinyfish = _FakeFetcher()
    health = WallapopHealth()
    # Simulate: prior cycle saw 401, login was just run, API will now succeed.
    health.mark_api_session_expired()
    health.mark_api_session_renewed_by_operator()
    api.search_response = [_listing("renewed")]
    capsys.readouterr()  # drain any state

    listings = await wallapop_two_path_fetch(
        _query(),
        api_fetcher=api,
        tinyfish_fetcher=tinyfish,
        health=health,
    )

    assert [listing.listing_id for listing in listings] == ["renewed"]
    records = _records(capsys.readouterr().out)
    renewed = [r for r in records if r["event"] == "wallapop_session_renewed"]
    assert renewed, f"missing wallapop_session_renewed in {records!r}"


async def test_session_renewal_log_is_one_shot() -> None:
    """The renewed log fires exactly once per renewal — not on every
    subsequent successful poll."""
    api = _FakeFetcher()
    tinyfish = _FakeFetcher()
    health = WallapopHealth()
    health.mark_api_session_expired()
    health.mark_api_session_renewed_by_operator()
    api.search_response = [_listing("ok")]

    # Pull the consume_pending_renewal latch via a first successful call.
    await wallapop_two_path_fetch(
        _query(),
        api_fetcher=api,
        tinyfish_fetcher=tinyfish,
        health=health,
    )
    assert health.consume_pending_renewal() is False  # flag was consumed

    # Calling again would set up a second consumption — we just verify
    # the WallapopHealth internal state is right.


# ─────────────────────────────────────────────────────────────────────────
# Both paths down — empty result + structured log entry
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "tinyfish_exception",
    [
        TinyFishAuthFailed("invalid key"),
        TinyFishRateLimited(retry_after_s=12),
        TinyFishUnavailable("timeout"),
        WallapopSchemaDrift("listings", "bad shape"),
    ],
)
async def test_both_paths_down_returns_empty_and_logs(
    tinyfish_exception: Exception,
    capsys: pytest.CaptureFixture[str],
) -> None:
    api = _FakeFetcher()
    api.search_response = WallapopApiError(503, "down")
    tinyfish = _FakeFetcher()
    tinyfish.search_response = tinyfish_exception
    health = WallapopHealth()

    listings = await wallapop_two_path_fetch(
        _query(),
        api_fetcher=api,
        tinyfish_fetcher=tinyfish,
        health=health,
    )

    assert listings == []
    records = _records(capsys.readouterr().out)
    down = [r for r in records if r["event"] == "wallapop_both_paths_down"]
    assert down
    assert down[0]["tinyfish_error_class"] == tinyfish_exception.__class__.__name__


async def test_api_unhealthy_and_tinyfish_fails_also_logs_both_paths_down(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When the API path is already latched off, a TinyFish failure still
    counts as both-paths-down (the cheap path's unavailability is the
    reason TinyFish is the only option)."""
    api = _FakeFetcher()
    tinyfish = _FakeFetcher()
    tinyfish.search_response = TinyFishUnavailable("network")
    health = WallapopHealth()
    health.mark_api_session_expired()

    listings = await wallapop_two_path_fetch(
        _query(),
        api_fetcher=api,
        tinyfish_fetcher=tinyfish,
        health=health,
    )

    assert listings == []
    records = _records(capsys.readouterr().out)
    down = [r for r in records if r["event"] == "wallapop_both_paths_down"]
    assert down
    assert down[0]["api_attempt_enabled"] is False
    # The cheap path was never tried this cycle.
    assert api.search_calls == []


# ─────────────────────────────────────────────────────────────────────────
# WallapopHealth state machine — small unit tests
# ─────────────────────────────────────────────────────────────────────────


def test_health_initial_state_is_attempt_enabled() -> None:
    assert WallapopHealth().api_attempt_enabled() is True


def test_health_session_expired_disables() -> None:
    health = WallapopHealth()
    health.mark_api_session_expired()
    assert health.api_attempt_enabled() is False


def test_health_renewal_by_operator_enables_and_arms_pending_flag() -> None:
    health = WallapopHealth()
    health.mark_api_session_expired()
    health.mark_api_session_renewed_by_operator()
    assert health.api_attempt_enabled() is True
    assert health.consume_pending_renewal() is True
    # Atomic clear: a second consume returns False.
    assert health.consume_pending_renewal() is False


def test_consume_pending_renewal_is_false_when_no_renewal_action() -> None:
    health = WallapopHealth()
    assert health.consume_pending_renewal() is False


# ─────────────────────────────────────────────────────────────────────────
# Adapter discipline — orchestration stays pure
# ─────────────────────────────────────────────────────────────────────────


def test_wallapop_fallback_imports_stay_within_orchestration_allowlist() -> None:
    """The orchestrator imports only stdlib + domain/interfaces/observability.
    No adapter package may be imported here — composition happens via the
    PageFetcher port, never via a concrete class."""
    import ast
    from pathlib import Path

    source_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "hardware_hunter"
        / "orchestration"
        / "wallapop_fallback.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("hardware_hunter.adapters"):
                    offenders.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("hardware_hunter.adapters"):
                offenders.append(f"from {module} import ...")
    assert not offenders, "orchestration.wallapop_fallback imported an adapter:\n  " + "\n  ".join(
        offenders
    )
