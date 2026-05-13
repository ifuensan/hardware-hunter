"""eBay.es official-API adapter — Story 3.7.

Public surface:

  - :class:`EbayApiFetcher` — the concrete :class:`PageFetcher`
  - :class:`OAuthTokenStore` — load/save tokens with atomic-write + 0600
  - :class:`DailyQuotaTracker` — per-UTC-day request budget counter
"""

from hardware_hunter.adapters.ebay_api.fetcher import EbayApiFetcher
from hardware_hunter.adapters.ebay_api.quota import DailyQuotaTracker
from hardware_hunter.adapters.ebay_api.tokens import OAuthTokens, OAuthTokenStore

__all__ = [
    "DailyQuotaTracker",
    "EbayApiFetcher",
    "OAuthTokenStore",
    "OAuthTokens",
]
