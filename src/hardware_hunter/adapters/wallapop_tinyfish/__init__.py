"""Wallapop TinyFish fallback adapter — Story 3.5.

Used by the two-path Wallapop orchestrator (Story 3.6) when the
unofficial API path fails: session expiry, anti-bot challenge,
transient 5xx. TinyFish runs a real browser remotely against the
public Wallapop search URL and returns structured JSON we map to
:class:`Listing`.

Public surface:

  - :class:`WallapopTinyfishFetcher` — concrete :class:`PageFetcher`
"""

from hardware_hunter.adapters.wallapop_tinyfish.fetcher import WallapopTinyfishFetcher

__all__ = ["WallapopTinyfishFetcher"]
