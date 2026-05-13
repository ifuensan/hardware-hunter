"""Marketplace-shaped errors surfaced by adapters — Story 3.4 (NFR-I4).

These exception classes live in :mod:`domain` so the orchestration layer
(``orchestration/``) can catch them without importing any adapter
package. Adapters raise; the two-path Wallapop fallback (Story 3.6) and
the eBay daily-quota guard (Story 3.7) catch and decide.

The names are marketplace-specific because the *reactions* are
marketplace-specific (Wallapop session-expiry triggers a Telegram
operational alert + falls back to the TinyFish path; eBay 4xx triggers
a cadence backoff). Putting them in ``domain/`` keeps adapter imports
out of orchestration, which is the whole point.
"""

from __future__ import annotations


class MarketplaceError(RuntimeError):
    """Common base for any marketplace-shaped adapter failure."""


# ─────────────────────────────────────────────────────────────────────────
# Wallapop
# ─────────────────────────────────────────────────────────────────────────


class WallapopError(MarketplaceError):
    """Base class for any Wallapop adapter failure."""


class WallapopSessionExpired(WallapopError):
    """The session cookie is no longer valid (HTTP 401 from api.wallapop).

    The orchestration layer reacts by emitting an operational alert
    (``wallapop_session_expired``) and falling back to the TinyFish
    path for the rest of the poll cycle (NFR-R2).
    """


class WallapopApiError(WallapopError):
    """A non-401 4xx or 5xx response from the unofficial API."""

    def __init__(self, status_code: int, body_excerpt: str | None = None) -> None:
        self.status_code = status_code
        self.body_excerpt = body_excerpt
        suffix = f": {body_excerpt}" if body_excerpt else ""
        super().__init__(f"Wallapop API returned HTTP {status_code}{suffix}")


class WallapopSchemaDrift(WallapopError):
    """A 200 response was missing a field the adapter schema declares.

    The path identifies the offending location for the operational log
    (e.g. ``"search_objects[0].price.amount"``); operators see this in
    the structured-log line and know which selector to patch.
    """

    def __init__(self, field_path: str, detail: str | None = None) -> None:
        self.field_path = field_path
        self.detail = detail
        super().__init__(f"Wallapop schema drift at {field_path}{f': {detail}' if detail else ''}")


# ─────────────────────────────────────────────────────────────────────────
# eBay
# ─────────────────────────────────────────────────────────────────────────


class EbayError(MarketplaceError):
    """Base class for any eBay adapter failure."""


class EbayAuthFailed(EbayError):
    """OAuth refresh-token endpoint rejected the refresh token (HTTP 401).

    The operator must re-run ``hardware-hunter login ebay`` to capture
    fresh tokens; the daemon stops polling eBay until then.
    """


class EbayQuotaExceeded(EbayError):
    """Daily request budget would be exceeded by the next call.

    The poll loop reacts by halving the eBay cadence (2x backoff) until
    the next UTC-midnight quota reset. Operators see the
    ``ebay_quota_breach`` operational alert.
    """

    def __init__(self, used: int, budget: int) -> None:
        self.used = used
        self.budget = budget
        super().__init__(f"eBay daily quota exceeded: {used}/{budget} requests used")


class EbayApiError(EbayError):
    """A non-401 4xx or 5xx response from the eBay API."""

    def __init__(self, status_code: int, body_excerpt: str | None = None) -> None:
        self.status_code = status_code
        self.body_excerpt = body_excerpt
        suffix = f": {body_excerpt}" if body_excerpt else ""
        super().__init__(f"eBay API returned HTTP {status_code}{suffix}")


class EbaySchemaDrift(EbayError):
    """A 200 response was missing a field the adapter schema declares."""

    def __init__(self, field_path: str, detail: str | None = None) -> None:
        self.field_path = field_path
        self.detail = detail
        super().__init__(f"eBay schema drift at {field_path}{f': {detail}' if detail else ''}")
