"""Tests for the wishlist domain schema — FR1 / FR2 / FR4 / FR5."""

from __future__ import annotations

import warnings
from decimal import Decimal

import pytest
from pydantic import ValidationError

from salvager.domain.wishlist import (
    SOFT_ENTRY_CAP,
    Phase2Settings,
    Wishlist,
    WishlistEntry,
)


def _valid_entry_kwargs(**overrides: object) -> dict[str, object]:
    """Minimum-valid kwargs; tests override individual fields."""
    base: dict[str, object] = {
        "manufacturer": "Western Digital",
        "model": "WD Red Plus 4TB",
        "ref": "WD40EFPX",
        "type": "hdd",
        "max_price_solo": Decimal("60.00"),
        "max_price_in_device": Decimal("90.00"),
        "keywords": ["WD Red Plus 4TB", "WD40EFPX"],
        "container_keywords": ["NAS", "Synology"],
        "confidence_threshold": "high",
    }
    base.update(overrides)
    return base


# ─────────────────────────────────────────────────────────────────────────
# Required fields + computed properties (FR1, FR2, FR4)
# ─────────────────────────────────────────────────────────────────────────


def test_entry_accepts_full_valid_payload() -> None:
    entry = WishlistEntry(**_valid_entry_kwargs())  # type: ignore[arg-type]
    assert entry.manufacturer == "Western Digital"
    assert entry.type == "hdd"
    assert entry.phase2.enabled is False  # default


def test_entry_key_tuple_matches_fr4() -> None:
    entry = WishlistEntry(**_valid_entry_kwargs())  # type: ignore[arg-type]
    assert entry.entry_key == ("Western Digital", "WD Red Plus 4TB", "WD40EFPX")


def test_display_name_format() -> None:
    entry = WishlistEntry(**_valid_entry_kwargs())  # type: ignore[arg-type]
    assert entry.display_name == "Western Digital WD Red Plus 4TB (WD40EFPX)"


def test_unknown_field_is_rejected() -> None:
    """extra='forbid' on the model — typos surface at parse time."""
    with pytest.raises(ValidationError, match="extra_forbidden"):
        WishlistEntry(**_valid_entry_kwargs(bogus_field="oops"))  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────
# FR5 — price ceiling nullability + container detection helper
# ─────────────────────────────────────────────────────────────────────────


def test_max_price_in_device_none_disables_container_detection() -> None:
    entry = WishlistEntry(
        **_valid_entry_kwargs(max_price_in_device=None)  # type: ignore[arg-type]
    )
    assert entry.max_price_in_device is None
    assert entry.container_detection_enabled() is False


def test_container_detection_enabled_when_in_device_price_present() -> None:
    entry = WishlistEntry(**_valid_entry_kwargs())  # type: ignore[arg-type]
    assert entry.container_detection_enabled() is True


def test_both_prices_none_is_rejected() -> None:
    """FR5: an entry with no price ceiling at all is invalid."""
    with pytest.raises(
        ValidationError, match="at least one of max_price_solo or max_price_in_device"
    ):
        WishlistEntry(
            **_valid_entry_kwargs(max_price_solo=None, max_price_in_device=None)  # type: ignore[arg-type]
        )


# ─────────────────────────────────────────────────────────────────────────
# Phase2Settings
# ─────────────────────────────────────────────────────────────────────────


def test_phase2_defaults_to_disabled() -> None:
    settings = Phase2Settings()
    assert settings.enabled is False
    assert settings.max_price_eur is None


def test_phase2_settings_extra_forbidden() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        Phase2Settings(enabled=True, bogus="x")  # type: ignore[call-arg]


def test_phase2_max_price_accepts_decimal() -> None:
    settings = Phase2Settings(enabled=True, max_price_eur=Decimal("75.00"))
    assert settings.max_price_eur == Decimal("75.00")


# ─────────────────────────────────────────────────────────────────────────
# Wishlist wrapper — uniqueness + soft cap
# ─────────────────────────────────────────────────────────────────────────


def test_wishlist_accepts_distinct_entries() -> None:
    wishlist = Wishlist(
        entries=[
            WishlistEntry(**_valid_entry_kwargs()),  # type: ignore[arg-type]
            WishlistEntry(**_valid_entry_kwargs(ref="OTHER_REF")),  # type: ignore[arg-type]
        ]
    )
    assert len(wishlist.entries) == 2


def test_wishlist_rejects_duplicate_entry_keys() -> None:
    entry_a = WishlistEntry(**_valid_entry_kwargs())  # type: ignore[arg-type]
    entry_b = WishlistEntry(**_valid_entry_kwargs())  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="duplicate entry key"):
        Wishlist(entries=[entry_a, entry_b])


def test_wishlist_duplicate_error_names_both_indices() -> None:
    entry_a = WishlistEntry(**_valid_entry_kwargs())  # type: ignore[arg-type]
    entry_b = WishlistEntry(**_valid_entry_kwargs(ref="OTHER"))  # type: ignore[arg-type]
    entry_c = WishlistEntry(**_valid_entry_kwargs())  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as exc_info:
        Wishlist(entries=[entry_a, entry_b, entry_c])
    msg = str(exc_info.value)
    assert "entries[0]" in msg
    assert "entries[2]" in msg


def test_wishlist_soft_cap_emits_user_warning() -> None:
    """FR3: > 100 entries is a soft nudge, not a hard error."""
    entries = [
        WishlistEntry(**_valid_entry_kwargs(ref=f"REF_{i:03d}"))  # type: ignore[arg-type]
        for i in range(SOFT_ENTRY_CAP + 1)
    ]
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        Wishlist(entries=entries)
    user_warnings = [w for w in captured if issubclass(w.category, UserWarning)]
    assert len(user_warnings) == 1
    assert "soft cap" in str(user_warnings[0].message)


def test_wishlist_below_soft_cap_no_warning() -> None:
    entries = [
        WishlistEntry(**_valid_entry_kwargs(ref=f"REF_{i:03d}"))  # type: ignore[arg-type]
        for i in range(5)
    ]
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        Wishlist(entries=entries)
    assert [w for w in captured if issubclass(w.category, UserWarning)] == []


def test_wishlist_extra_field_at_top_level_rejected() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        Wishlist(entries=[], schema_version="v2")  # type: ignore[call-arg]


# ─────────────────────────────────────────────────────────────────────────
# Literal types
# ─────────────────────────────────────────────────────────────────────────


def test_type_must_be_hdd_or_ram() -> None:
    with pytest.raises(ValidationError):
        WishlistEntry(**_valid_entry_kwargs(type="gpu"))  # type: ignore[arg-type]


def test_confidence_threshold_must_be_known_value() -> None:
    with pytest.raises(ValidationError):
        WishlistEntry(**_valid_entry_kwargs(confidence_threshold="extreme"))  # type: ignore[arg-type]
