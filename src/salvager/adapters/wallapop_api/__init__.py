"""Wallapop unofficial-API adapter — Story 3.4.

Public surface:

  - :class:`WallapopApiFetcher` — the concrete :class:`PageFetcher`
  - :func:`load_cookies` — Netscape cookies.txt → httpx.Cookies

Implementation detail (schema, mapping) lives in submodules.
"""

from salvager.adapters.wallapop_api.cookies import load_cookies
from salvager.adapters.wallapop_api.fetcher import WallapopApiFetcher

__all__ = ["WallapopApiFetcher", "load_cookies"]
