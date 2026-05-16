"""Wallapop unofficial-API :class:`PageFetcher` — Story 3.4.

Searches ``api.wallapop.com/api/v3/general/search`` with the operator's
captured session cookie. Maps results into domain :class:`Listing`
instances; surfaces schema drift, session expiry, and other 4xx/5xx
failures as typed exceptions in :mod:`salvager.domain.errors`.

TLS: ``httpx.AsyncClient(verify=True)`` always. There is no codepath
that downgrades to ``verify=False`` (NFR-S3 — refuses to ship one).

Logging events
--------------
``wallapop_search_succeeded`` — latency_ms + result_count + marketplace
``wallapop_search_failed``    — error_class + status_code (when known)
``wallapop_schema_drift``     — error_class + field_path
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from salvager.adapters.wallapop_api.cookies import load_cookies
from salvager.adapters.wallapop_api.schema import (
    WallapopApiItem,
    WallapopApiSearchResponse,
)
from salvager.domain.errors import (
    WallapopApiError,
    WallapopSchemaDrift,
    WallapopSessionExpired,
)
from salvager.domain.listing import Listing, SearchQuery
from salvager.interfaces.page_fetcher import PageFetcher
from salvager.observability.logging import get_logger

_DEFAULT_BASE_URL = "https://api.wallapop.com"
_SEARCH_PATH = "/api/v3/general/search"
_DEFAULT_TIMEOUT = httpx.Timeout(10.0)
_ITEM_URL_TEMPLATE = "https://es.wallapop.com/item/{listing_id}"


class WallapopApiFetcher(PageFetcher):
    """``PageFetcher`` backed by Wallapop's unofficial JSON API."""

    def __init__(
        self,
        cookies_path: str | Path,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout: httpx.Timeout = _DEFAULT_TIMEOUT,
    ) -> None:
        """Build a fetcher.

        ``client`` is dependency-injected for tests — production calls
        leave it None and we construct one with the cookie jar and
        ``verify=True``. Tests pass an :class:`httpx.AsyncClient`
        wired to a :class:`httpx.MockTransport`.
        """
        self._base_url = base_url.rstrip("/")
        self._cookies_path = Path(cookies_path)
        self._owned_client = client is None
        if client is None:
            cookies = load_cookies(self._cookies_path)
            client = httpx.AsyncClient(
                cookies=cookies,
                timeout=timeout,
                verify=True,
                base_url=self._base_url,
            )
        self._client = client
        self._log = get_logger("adapter.wallapop_api")

    async def aclose(self) -> None:
        """Close the underlying HTTP client; idempotent."""
        if self._owned_client:
            await self._client.aclose()

    # ─────────────────────────────────────────────────────────────────
    # PageFetcher
    # ─────────────────────────────────────────────────────────────────

    async def search(self, query: SearchQuery) -> list[Listing]:
        params: dict[str, Any] = {"keywords": " ".join(query.keywords)}
        if query.max_price_eur is not None:
            params["max_sale_price"] = str(query.max_price_eur)

        started = time.perf_counter()
        try:
            response = await self._client.get(_SEARCH_PATH, params=params)
        except httpx.HTTPError as exc:
            self._log.error(
                "wallapop_search_failed",
                extra={"error_class": exc.__class__.__name__, "marketplace": "wallapop"},
            )
            raise WallapopApiError(0, str(exc)) from exc

        self._raise_for_status(response)
        try:
            payload = WallapopApiSearchResponse.model_validate(response.json())
        except ValidationError as exc:
            drift = _from_validation_error(exc)
            self._log.error(
                "wallapop_schema_drift",
                extra={
                    "error_class": "WallapopSchemaDrift",
                    "marketplace": "wallapop",
                    "field_path": drift.field_path,
                },
            )
            raise drift from exc

        listings = [_item_to_listing(item) for item in payload.search_objects]
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        self._log.info(
            "wallapop_search_succeeded",
            extra={
                "marketplace": "wallapop",
                "latency_ms": elapsed_ms,
                "result_count": len(listings),
            },
        )
        return listings

    async def fetch(self, listing_url: str) -> Listing:
        """Fetch one listing by URL.

        Used by ``salvager explain <url>`` (Epic 4) and the
        Phase 2 pre-buy reconciliation. The unofficial API exposes a
        per-item endpoint at the same path; we reuse the search method
        with an ``id`` filter rather than introducing a second route.
        """
        listing_id = listing_url.rstrip("/").rsplit("/", 1)[-1]
        started = time.perf_counter()
        try:
            response = await self._client.get(f"/api/v3/items/{listing_id}")
        except httpx.HTTPError as exc:
            raise WallapopApiError(0, str(exc)) from exc

        self._raise_for_status(response)
        try:
            item = WallapopApiItem.model_validate(response.json())
        except ValidationError as exc:
            raise _from_validation_error(exc) from exc

        listing = _item_to_listing(item)
        self._log.info(
            "wallapop_fetch_succeeded",
            extra={
                "marketplace": "wallapop",
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "listing_id": listing_id,
            },
        )
        return listing

    # ─────────────────────────────────────────────────────────────────
    # Internals
    # ─────────────────────────────────────────────────────────────────

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code == 401:
            self._log.warning(
                "wallapop_session_expired",
                extra={"marketplace": "wallapop", "status_code": 401},
            )
            raise WallapopSessionExpired("Wallapop returned HTTP 401 — session expired")
        if response.status_code >= 400:
            body = response.text[:200] if response.text else None
            self._log.error(
                "wallapop_api_error",
                extra={
                    "marketplace": "wallapop",
                    "status_code": response.status_code,
                    "error_class": "WallapopApiError",
                },
            )
            raise WallapopApiError(response.status_code, body)


def _item_to_listing(item: WallapopApiItem) -> Listing:
    """Project an upstream ``WallapopApiItem`` onto the domain shape."""
    return Listing(
        listing_id=item.id,
        marketplace="wallapop",
        url=_ITEM_URL_TEMPLATE.format(listing_id=item.id),
        title=item.title,
        description=item.description,
        price_eur=Decimal(str(item.price.amount)),
        location=item.location.city if item.location else None,
        photo_urls=[url for url in (item.preferred_photo_url(),) if url is not None],
        seller_id=item.user.id if item.user else None,
        seller_history_count=item.user.items_count if item.user else None,
        published_at=_parse_iso(item.publish_date),
        fetched_at=datetime.now(UTC),
    )


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _from_validation_error(exc: ValidationError) -> WallapopSchemaDrift:
    """Map pydantic's ValidationError to a single :class:`WallapopSchemaDrift`."""
    first = exc.errors()[0]
    path = ".".join(str(p) for p in first["loc"])
    return WallapopSchemaDrift(
        field_path=f"search_objects.{path}" if path else "<root>",
        detail=first["msg"],
    )
