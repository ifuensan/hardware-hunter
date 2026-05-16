"""``BrowserSession`` port — Story 5.3 (FR25 / FR30 / NFR-S5).

The port through which the Phase 2 buy orchestrator (Story 5.7) talks
to *any* marketplace's checkout flow. Two adapters implement it:

  - ``adapters/tinyfish_browser.wallapop_pay.WallapopPayFlow`` — drives
    Wallapop Pay (the only Wallapop rail that's both safe and
    user-buyable from inside the app).
  - ``adapters/tinyfish_browser.ebay_checkout.EbayCheckoutFlow`` —
    drives eBay.es' official checkout.

The orchestration layer composes ``BrowserSession`` only — it never
sees the TinyFish SDK directly. This is how NFR-M1 (adapter discipline)
holds for the buy path, and how Story 5.14's payment-rail lint can
guarantee no Bizum / transferencia / PayPal / bank-transfer codepath
ever lands in business logic.

The return type is a tagged union (``BuyResult``) so the orchestrator
gets a single object to branch on — never an exception that has to be
caught-and-classified at the call-site.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from hardware_hunter.domain.errors import BuyFailureReason
from hardware_hunter.domain.listing import Listing


class BuySuccess(BaseModel):
    """The marketplace's checkout confirmed and we captured the receipt.

    Field semantics:

      - ``price_paid_eur`` — the price the marketplace charged, parsed
        off the confirmation page. May differ from the listing price by
        a few cents (rounding / shipping); the reconciler (Story 5.4)
        is the authority on whether the delta is acceptable.
      - ``payment_method`` — one of the protected rails. The renderer
        translates this to a Spanish label.
      - ``receipt_id`` — the marketplace's transaction identifier,
        used as the natural key when the operator types
        ``phase2 reconcile <id>``.
      - ``screenshot_url`` — the path or URL to the captured
        confirmation screenshot. UX-DR9 makes this mandatory; if the
        capture failed, the flow returns ``BuyFailure(screenshot_missing)``
        instead, even though the buy may have succeeded.
      - ``total_seconds`` — wall-clock from ``execute_buy`` entry to
        return; surfaced in the receipt alert + the operational alert
        when it exceeds the budget.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["success"] = "success"
    price_paid_eur: Decimal = Field(gt=0)
    payment_method: Literal["wallapop_pay", "ebay_checkout"]
    receipt_id: str = Field(min_length=1)
    screenshot_url: str = Field(min_length=1)
    total_seconds: int = Field(ge=0)


class BuyFailure(BaseModel):
    """The checkout did NOT complete (or completed without a captured
    receipt). The orchestrator surfaces this to the operator via
    :func:`render_phase2_buy_failure` and writes an audit row.

    ``ctx`` carries the variant-specific detail the renderer needs:
    e.g. ``{"missing": ["buy_button"]}`` for ``missing_element``,
    ``{"error_class": "TimeoutError"}`` for ``timeout``. Each
    ``BuyFailureReason`` documents its own ctx contract.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["failure"] = "failure"
    reason: BuyFailureReason
    ctx: dict[str, Any] = Field(default_factory=dict)


#: Discriminated union — the orchestrator pattern-matches on ``kind``.
BuyResult = Annotated[BuySuccess | BuyFailure, Field(discriminator="kind")]


class BrowserSession(ABC):
    """Port for one marketplace's checkout flow.

    The contract is fail-closed: any uncertainty about whether the buy
    happened, whether the receipt was captured, or whether the payment
    rail is the right one MUST surface as a :class:`BuyFailure` (never
    a silent ``BuySuccess``). FR28 is built around this — the
    operator's confidence that "alert says success ⇒ purchase
    happened" depends on it.
    """

    @abstractmethod
    async def execute_buy(self, listing: Listing, max_price_eur: Decimal) -> BuyResult:
        """Drive the marketplace's checkout for ``listing``.

        ``max_price_eur`` is the operator-declared ceiling (FR26). The
        flow embeds it in the agent goal and refuses the buy with
        ``BuyFailure(reason=marketplace_error, ctx={"observed_price_eur": ...})``
        if the marketplace shows a price above it — the reconciler
        verifies the same invariant against the receipt afterward.
        """


__all__ = [
    "BrowserSession",
    "BuyFailure",
    "BuyResult",
    "BuySuccess",
]
