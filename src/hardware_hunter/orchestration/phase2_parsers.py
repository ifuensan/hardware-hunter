"""Smoke-test price parsers — Story 5.13 wiring for Story 5.6.

The smoke-test orchestrator takes a registry of ``kind → parser``; this
module is where the v1.0 canonical fixture set is wired to real
extraction logic. The parsers are deliberately small and dependency-free
(stdlib JSON + regex) so the smoke test stays portable and fast.

When real adapter parsers (e.g. a future HTML-parsing Wallapop fetcher)
are introduced, *those* parsers should be invoked from here so the smoke
test exercises the same code path the daemon uses in production.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal

from hardware_hunter.orchestration.smoke_test import PriceParser


def parse_wallapop_api_price(body: bytes) -> Decimal:
    """Extract ``price.amount`` from a Wallapop unofficial-API JSON payload."""
    data = json.loads(body.decode("utf-8"))
    return Decimal(str(data["price"]["amount"]))


def parse_ebay_api_price(body: bytes) -> Decimal:
    """Extract ``price.value`` from an eBay Browse API item summary."""
    data = json.loads(body.decode("utf-8"))
    return Decimal(str(data["price"]["value"]))


#: Match ``data-price-amount="55.00"`` (canonical, locale-free).
_PRICE_ATTR_RE = re.compile(r'data-price-amount="([0-9]+(?:\.[0-9]+)?)"')

#: Fallback: the rendered "55,00 €" / "55 €" span inside item-detail__price-amount.
_PRICE_TEXT_RE = re.compile(
    r'class="item-detail__price-amount"[^>]*>\s*([\d.,]+)\s*€',
    flags=re.IGNORECASE,
)


def parse_wallapop_html_price(body: bytes) -> Decimal:
    """Pull the price out of a Wallapop listing page.

    Preference order:
      1. ``data-price-amount`` attribute (machine-readable, dot decimal).
      2. The rendered Spanish text inside ``.item-detail__price-amount``
         (comma decimal — the Q9 regression hides exactly here).
    """
    text = body.decode("utf-8")
    if match := _PRICE_ATTR_RE.search(text):
        return Decimal(match.group(1))
    if match := _PRICE_TEXT_RE.search(text):
        raw = match.group(1)
        # Spanish locale: comma is the decimal separator. A naïve parser
        # would treat "53,00" as thousands → 5300 or 0.53 — both wrong.
        # The fix is explicit: drop dots (thousands), swap commas for
        # the decimal point, then construct the Decimal.
        normalized = raw.replace(".", "").replace(",", ".")
        return Decimal(normalized)
    raise ValueError("no price found in HTML")


def default_price_parser_registry() -> dict[str, PriceParser]:
    """Return the kind→parser registry for the v1.0 fixture set."""
    return {
        "wallapop_api": parse_wallapop_api_price,
        "wallapop_html": parse_wallapop_html_price,
        "ebay_api": parse_ebay_api_price,
    }


__all__ = [
    "default_price_parser_registry",
    "parse_ebay_api_price",
    "parse_wallapop_api_price",
    "parse_wallapop_html_price",
]
