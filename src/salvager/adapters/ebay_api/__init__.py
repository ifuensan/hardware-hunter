"""eBay.es official-API adapter — Story 3.7 / Story 2.10.

Public surface:

  - :class:`EbayApiFetcher` — the concrete :class:`PageFetcher`
  - :class:`OAuthTokenStore` — load/save tokens with atomic-write + 0600
  - :class:`DailyQuotaTracker` — per-UTC-day request budget counter
  - :func:`build_consent_url` / :func:`exchange_code_for_tokens` — the
    OAuth authorization-code flow behind ``login ebay``
"""

from salvager.adapters.ebay_api.fetcher import EbayApiFetcher
from salvager.adapters.ebay_api.oauth import (
    DEFAULT_SCOPE,
    build_consent_url,
    exchange_code_for_tokens,
)
from salvager.adapters.ebay_api.quota import DailyQuotaTracker
from salvager.adapters.ebay_api.tokens import OAuthTokens, OAuthTokenStore

__all__ = [
    "DEFAULT_SCOPE",
    "DailyQuotaTracker",
    "EbayApiFetcher",
    "OAuthTokenStore",
    "OAuthTokens",
    "build_consent_url",
    "exchange_code_for_tokens",
]
