"""Helpers shared by every LLM-backed :class:`ListingEvaluator` adapter.

Lives at adapter level (private — leading underscore) rather than in
``domain/`` because the budget guard semantics are domain-shaped but
the JSON extraction is a wire-format concern; keeping both in one
spot avoids file proliferation and the cross-package import noise
that two separate homes would create.

Adapter-discipline (NFR-M1) is unaffected: nothing here imports a
provider SDK; concrete adapters keep their SDK imports lazy and
local.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from salvager.domain.evaluation import ListingEvaluation
from salvager.domain.listing import Listing
from salvager.domain.wishlist import WishlistEntry

#: Hard cap on the model's ``one_line_take`` field. Anything longer
#: raises :class:`LlmEvaluationError` at the caller — operators expect
#: a Telegram-renderable single line, not a paragraph.
MAX_ONE_LINE_TAKE = 120


# ─────────────────────────────────────────────────────────────────────────
# Budget short-circuit
# ─────────────────────────────────────────────────────────────────────────


def exceeds_all_ceilings(listing: Listing, entry: WishlistEntry) -> bool:
    """True iff the listing price is strictly above every configured ceiling.

    A None ceiling means "container detection disabled for that variant"
    (FR5) — treat it as not-a-bound, so a None ceiling alone never
    triggers the short-circuit.
    """
    price = listing.price_eur
    ceilings = [c for c in (entry.max_price_solo, entry.max_price_in_device) if c is not None]
    if not ceilings:
        return False
    return all(price > ceiling for ceiling in ceilings)


def budget_short_circuit_evaluation(
    listing: Listing,
    entry: WishlistEntry,
) -> ListingEvaluation:
    """Return the ``confidence=low`` verdict adapters use when the
    pre-flight budget guard fires — same shape for every provider so
    the cache + downstream rendering treat both paths identically.
    """
    return ListingEvaluation(
        listing_id=listing.listing_id,
        entry_key=entry.entry_key,
        confidence="low",
        one_line_take=(f"EUR {listing.price_eur} — price exceeds wishlist max."),
        is_container=False,
        wrapper_text=None,
        extracted_text=None,
        evaluated_at=datetime.now(UTC),
        cache_hit=False,
    )


# ─────────────────────────────────────────────────────────────────────────
# JSON extraction
# ─────────────────────────────────────────────────────────────────────────

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json_object(raw: str) -> str:
    """Return the outermost ``{...}`` substring of ``raw``.

    Robust to LLMs that wrap JSON in markdown code fences or pad it
    with explanatory prose. Raises ``ValueError`` when no object is
    present — adapters wrap that as :class:`LlmEvaluationError`.
    """
    if not raw or not raw.strip():
        raise ValueError("empty LLM response")
    match = _JSON_OBJECT_RE.search(raw)
    if match is None:
        raise ValueError("no JSON object found in response")
    return match.group(0)
