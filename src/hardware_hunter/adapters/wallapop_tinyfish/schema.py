"""Pydantic models for the TinyFish-shaped response payload.

The TinyFish agent runs a browser, executes our natural-language goal,
and returns a JSON object under ``AgentRunResponse.result``. Our goal
template asks for the exact shape :class:`TinyfishListingsResult`
declares. Any deviation (missing fields, wrong types, extra
top-level keys) raises :class:`pydantic.ValidationError` which the
adapter translates into :class:`WallapopSchemaDrift` with the offending
field path.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TinyfishListingItem(BaseModel):
    """One Wallapop listing card as extracted by the browser agent."""

    model_config = ConfigDict(extra="forbid")

    listing_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    title: str = Field(min_length=1)
    price_eur: Decimal
    location: str | None = None
    description: str | None = None
    photo_urls: list[str] = Field(default_factory=list)


class TinyfishListingsResult(BaseModel):
    """Envelope around the listings array.

    Wrapping in an object (rather than returning a top-level array)
    leaves room to add metadata fields without breaking the schema —
    a list-typed root would force a major-version bump on the prompt.
    """

    model_config = ConfigDict(extra="forbid")

    listings: list[TinyfishListingItem]
