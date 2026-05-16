"""Tests for the Wallapop unofficial-API adapter — Story 3.4."""

from __future__ import annotations

import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from salvager.adapters.wallapop_api import WallapopApiFetcher, load_cookies
from salvager.adapters.wallapop_api.cookies import WallapopCookiesError
from salvager.domain.errors import (
    WallapopApiError,
    WallapopSchemaDrift,
    WallapopSessionExpired,
)
from salvager.domain.listing import SearchQuery

# ─────────────────────────────────────────────────────────────────────────
# Cookies helper
# ─────────────────────────────────────────────────────────────────────────


def _valid_cookies_file(tmp_path: Path) -> Path:
    path = tmp_path / "wallapop_cookies.txt"
    path.write_text(
        "# Netscape HTTP Cookie File\n"
        ".wallapop.com\tTRUE\t/\tTRUE\t9999999999\tsession\tsecret-session\n"
        "#HttpOnly_.wallapop.com\tTRUE\t/\tTRUE\t9999999999\tcsrf\tcsrf-value\n",
        encoding="utf-8",
    )
    return path


def test_load_cookies_returns_httpx_cookies(tmp_path: Path) -> None:
    cookies = load_cookies(_valid_cookies_file(tmp_path))
    # SDK stores cookies in a private jar; assert via API rather than introspection.
    assert cookies.get("session", domain=".wallapop.com") == "secret-session"
    assert cookies.get("csrf", domain=".wallapop.com") == "csrf-value"


def test_load_cookies_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(WallapopCookiesError, match="not found"):
        load_cookies(tmp_path / "missing.txt")


def test_load_cookies_malformed_line_raises(tmp_path: Path) -> None:
    path = tmp_path / "wallapop_cookies.txt"
    path.write_text(".wallapop.com\tonly two fields\n", encoding="utf-8")
    with pytest.raises(WallapopCookiesError, match="expected 7 tab-separated"):
        load_cookies(path)


def test_load_cookies_skips_blank_lines_and_comments(tmp_path: Path) -> None:
    path = tmp_path / "wallapop_cookies.txt"
    path.write_text(
        "# comment\n\n.wallapop.com\tTRUE\t/\tTRUE\t9999999999\tsession\ts1\n",
        encoding="utf-8",
    )
    cookies = load_cookies(path)
    assert cookies.get("session", domain=".wallapop.com") == "s1"


# ─────────────────────────────────────────────────────────────────────────
# Fixtures for the fetcher tests
# ─────────────────────────────────────────────────────────────────────────


def _valid_search_payload() -> dict[str, Any]:
    return {
        "search_objects": [
            {
                "id": "abc123",
                "title": "WD Red Plus 4TB",
                "description": "Como nuevo, en caja.",
                "price": {"amount": "55.00", "currency": "EUR"},
                "location": {"city": "Madrid", "country_code": "ES"},
                "images": [{"original": "https://cdn.wallapop.com/abc123-original.jpg"}],
                "user": {"id": "u-42", "items_count": 17},
                "publish_date": "2026-05-10T08:30:00Z",
            },
            {
                "id": "def456",
                "title": "Ultrastar 14TB",
                "price": {"amount": "120.00", "currency": "EUR"},
                # description omitted (defaults to "")
                # location absent
                "images": [],
                "user": {"id": "u-99"},
            },
        ]
    }


def _build_fetcher(
    tmp_path: Path,
    handler: Callable[[httpx.Request], httpx.Response],
) -> WallapopApiFetcher:
    """Build a fetcher wired to an httpx.MockTransport."""
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        transport=transport,
        base_url="https://api.wallapop.com",
    )
    cookies_path = _valid_cookies_file(tmp_path)
    return WallapopApiFetcher(cookies_path, client=client)


# ─────────────────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_returns_domain_listings(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/general/search"
        assert request.url.params["keywords"] == "WD Red Plus 4TB"
        return httpx.Response(200, json=_valid_search_payload())

    fetcher = _build_fetcher(tmp_path, handler)
    try:
        listings = await fetcher.search(
            SearchQuery(keywords=["WD Red Plus 4TB"], marketplace="wallapop")
        )
    finally:
        await fetcher.aclose()

    assert len(listings) == 2

    first = listings[0]
    assert first.marketplace == "wallapop"
    assert first.listing_id == "abc123"
    assert first.url == "https://es.wallapop.com/item/abc123"
    assert first.title == "WD Red Plus 4TB"
    assert first.price_eur == Decimal("55.00")
    assert first.location == "Madrid"
    assert first.photo_urls == ["https://cdn.wallapop.com/abc123-original.jpg"]
    assert first.seller_id == "u-42"
    assert first.seller_history_count == 17
    assert first.published_at is not None

    second = listings[1]
    assert second.location is None
    assert second.photo_urls == []
    assert second.description == ""


@pytest.mark.asyncio
async def test_search_passes_max_price_filter(tmp_path: Path) -> None:
    seen_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(request.url.params)
        return httpx.Response(200, json={"search_objects": []})

    fetcher = _build_fetcher(tmp_path, handler)
    try:
        await fetcher.search(
            SearchQuery(
                keywords=["WD"],
                marketplace="wallapop",
                max_price_eur=Decimal("90.00"),
            )
        )
    finally:
        await fetcher.aclose()

    assert seen_params.get("max_sale_price") == "90.00"


# ─────────────────────────────────────────────────────────────────────────
# Error mapping (NFR-I4)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_http_401_raises_session_expired(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    fetcher = _build_fetcher(tmp_path, handler)
    try:
        with pytest.raises(WallapopSessionExpired):
            await fetcher.search(SearchQuery(keywords=["x"], marketplace="wallapop"))
    finally:
        await fetcher.aclose()


@pytest.mark.asyncio
async def test_http_500_raises_api_error_with_status_and_body(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream broken")

    fetcher = _build_fetcher(tmp_path, handler)
    try:
        with pytest.raises(WallapopApiError) as excinfo:
            await fetcher.search(SearchQuery(keywords=["x"], marketplace="wallapop"))
    finally:
        await fetcher.aclose()

    assert excinfo.value.status_code == 500
    assert excinfo.value.body_excerpt == "upstream broken"


@pytest.mark.asyncio
async def test_http_429_raises_api_error(tmp_path: Path) -> None:
    """429 (rate limited) is treated as a generic API error — the
    orchestration layer handles backoff, not the adapter."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    fetcher = _build_fetcher(tmp_path, handler)
    try:
        with pytest.raises(WallapopApiError) as excinfo:
            await fetcher.search(SearchQuery(keywords=["x"], marketplace="wallapop"))
    finally:
        await fetcher.aclose()
    assert excinfo.value.status_code == 429


@pytest.mark.asyncio
async def test_missing_required_field_raises_schema_drift(tmp_path: Path) -> None:
    """A 200 response missing a required field surfaces as schema drift."""
    bad_payload = {
        "search_objects": [
            {
                # 'id' missing — required field
                "title": "WD Red Plus 4TB",
                "price": {"amount": "55.00", "currency": "EUR"},
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=bad_payload)

    fetcher = _build_fetcher(tmp_path, handler)
    try:
        with pytest.raises(WallapopSchemaDrift) as excinfo:
            await fetcher.search(SearchQuery(keywords=["x"], marketplace="wallapop"))
    finally:
        await fetcher.aclose()
    # The path mentions the missing field.
    assert "id" in excinfo.value.field_path


@pytest.mark.asyncio
async def test_unknown_extra_fields_are_tolerated(tmp_path: Path) -> None:
    """Wallapop adds fields over time; ignoring extras is the design."""
    payload = _valid_search_payload()
    payload["search_objects"][0]["surprise_field"] = "this is fine"
    payload["new_top_level"] = {"x": 1}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    fetcher = _build_fetcher(tmp_path, handler)
    try:
        listings = await fetcher.search(SearchQuery(keywords=["x"], marketplace="wallapop"))
    finally:
        await fetcher.aclose()
    assert len(listings) == 2


# ─────────────────────────────────────────────────────────────────────────
# Logging — wallapop_search_succeeded carries the documented fields
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_successful_search_logs_event_with_latency_and_count(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The structured logger writes JSON Lines to stdout (NFR-O1); the
    package-root logger has ``propagate=False`` so pytest's ``caplog``
    can't see it. Parsing the captured stdout is the right surface."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_valid_search_payload())

    fetcher = _build_fetcher(tmp_path, handler)
    try:
        await fetcher.search(SearchQuery(keywords=["x"], marketplace="wallapop"))
    finally:
        await fetcher.aclose()

    records = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    success = [r for r in records if r.get("event") == "wallapop_search_succeeded"]
    assert len(success) == 1
    record = success[0]
    assert record["marketplace"] == "wallapop"
    assert record["result_count"] == 2
    assert isinstance(record["latency_ms"], int)


# ─────────────────────────────────────────────────────────────────────────
# Single-listing fetch (used by `explain <url>` later)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_single_listing(tmp_path: Path) -> None:
    item = _valid_search_payload()["search_objects"][0]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/items/abc123"
        return httpx.Response(200, json=item)

    fetcher = _build_fetcher(tmp_path, handler)
    try:
        listing = await fetcher.fetch("https://es.wallapop.com/item/abc123")
    finally:
        await fetcher.aclose()
    assert listing.listing_id == "abc123"
    assert listing.price_eur == Decimal("55.00")


# ─────────────────────────────────────────────────────────────────────────
# verify=True — no codepath downgrades TLS (NFR-S3)
# ─────────────────────────────────────────────────────────────────────────


def test_fetcher_module_never_disables_tls_verification() -> None:
    """AST check: no call passes ``verify=False`` anywhere in the adapter
    source. Substring grep would false-positive on the docstring that
    explains *why* there is no such codepath."""
    import ast

    src_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "salvager"
        / "adapters"
        / "wallapop_api"
        / "fetcher.py"
    )
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                is_verify_false = (
                    kw.arg == "verify"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is False
                )
                if is_verify_false:
                    pytest.fail(f"fetcher.py passes verify=False at line {node.lineno} — NFR-S3")
