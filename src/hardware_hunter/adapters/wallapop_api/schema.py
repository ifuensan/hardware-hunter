"""Pydantic schema for the Wallapop unofficial-API response — NFR-I4.

The shapes here are the contract we expect from
``api.wallapop.com/api/v3/general/search``. Required fields are strict —
a missing one trips :class:`WallapopSchemaDrift` via pydantic's
``ValidationError`` (the fetcher wraps it). Extras are tolerated
(Wallapop adds fields over time; we read what we need and ignore the
rest).

Only the fields that map to ``domain.listing.Listing`` are declared;
this is intentionally a *projection* of the upstream response, not a
mirror of it.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class WallapopApiPrice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    amount: Decimal
    currency: str


class WallapopApiLocation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    city: str | None = None
    country_code: str | None = None


class WallapopApiImage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Wallapop returns several sizes; we keep the largest for the alert card.
    original: str | None = None
    medium: str | None = None
    small: str | None = None


class WallapopApiUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    items_count: int | None = None


class WallapopApiItem(BaseModel):
    """One result row from the unofficial-API search endpoint."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    description: str = ""
    price: WallapopApiPrice
    location: WallapopApiLocation | None = None
    images: list[WallapopApiImage] = Field(default_factory=list)
    user: WallapopApiUser | None = None
    publish_date: str | None = None  # ISO 8601 (UTC), parsed by the mapper

    def preferred_photo_url(self) -> str | None:
        """Pick the highest-quality image URL we have, falling back gracefully."""
        for image in self.images:
            if image.original:
                return image.original
            if image.medium:
                return image.medium
            if image.small:
                return image.small
        return None


class WallapopApiSearchResponse(BaseModel):
    """Top-level shape of the unofficial-API search response."""

    model_config = ConfigDict(extra="ignore")

    search_objects: list[WallapopApiItem] = Field(default_factory=list)
