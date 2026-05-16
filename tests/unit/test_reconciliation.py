"""Pure-domain reconciliation tests — Story 5.4.

Three layers:

  - tabular cases for the AC's explicit numbers (Q9 + receipt example);
  - rejection of malformed input (negative, NaN);
  - hypothesis property tests asserting the FR31 "max(eur, pct%)"
    invariant + reflexivity + commutativity of EUR delta.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from salvager.domain.reconciliation import (
    ReconciliationResult,
    compute_tolerance,
)

_TOL_EUR = Decimal("1.00")
_TOL_PCT = Decimal("5")


# ─────────────────────────────────────────────────────────────────────────
# Tabular — the AC's named scenarios
# ─────────────────────────────────────────────────────────────────────────


def test_q9_scenario_fails_on_pct_tolerance() -> None:
    """API 53.00 vs HTML 0.53 — the % cushion is 2.65, the delta is 52.47."""
    result = compute_tolerance(
        Decimal("53.00"),
        Decimal("0.53"),
        tolerance_eur=_TOL_EUR,
        tolerance_pct=_TOL_PCT,
    )
    assert result.passed is False
    assert result.delta_eur == Decimal("52.47")
    # 52.47 / 53 * 100 ≈ 99.0
    assert Decimal("98.9") < result.delta_pct < Decimal("99.1")
    # max(1.00, 53 * 5 / 100) = 2.65 → pct binds.
    assert result.tolerance_used == "pct"
    assert result.tolerance_value == Decimal("2.65")


def test_receipt_vs_alert_mismatch_fails() -> None:
    """Alert 48.00 vs receipt 56.00 — 8.00 € drift on a 5%/1€ tolerance."""
    result = compute_tolerance(
        Decimal("48.00"),
        Decimal("56.00"),
        tolerance_eur=_TOL_EUR,
        tolerance_pct=_TOL_PCT,
    )
    assert result.passed is False
    assert result.delta_eur == Decimal("8.00")


def test_within_tolerance_passes() -> None:
    result = compute_tolerance(
        Decimal("55.00"),
        Decimal("55.50"),
        tolerance_eur=_TOL_EUR,
        tolerance_pct=_TOL_PCT,
    )
    assert result == ReconciliationResult(
        passed=True,
        delta_eur=Decimal("0.50"),
        delta_pct=Decimal("0.50") / Decimal("55.00") * Decimal("100"),
        tolerance_used="pct",  # 55 * 5 / 100 = 2.75 > 1.00
        tolerance_value=Decimal("2.75"),
    )


def test_low_price_eur_floor_binds() -> None:
    """At small prices the EUR floor is the binding tolerance, not the %."""
    result = compute_tolerance(
        Decimal("5.00"),
        Decimal("5.80"),
        tolerance_eur=_TOL_EUR,
        tolerance_pct=_TOL_PCT,
    )
    # max(1.00, 5 * 5 / 100 = 0.25) = 1.00 → eur binds; 0.80 < 1.00 passes.
    assert result.tolerance_used == "eur"
    assert result.passed is True


# ─────────────────────────────────────────────────────────────────────────
# Edge cases — zero, NaN, negative
# ─────────────────────────────────────────────────────────────────────────


def test_zero_reference_price_shortcircuits_pct_to_zero() -> None:
    """price_a == 0 would divide by zero — the % leg is clamped to zero
    so the EUR floor decides the result."""
    result = compute_tolerance(
        Decimal("0"),
        Decimal("0.53"),
        tolerance_eur=_TOL_EUR,
        tolerance_pct=_TOL_PCT,
    )
    assert result.delta_pct == Decimal("0")
    assert result.tolerance_used == "eur"
    assert result.passed is True  # 0.53 <= 1.00


def test_negative_price_rejected() -> None:
    with pytest.raises(ValueError, match="price_a must be non-negative"):
        compute_tolerance(
            Decimal("-1"),
            Decimal("1"),
            tolerance_eur=_TOL_EUR,
            tolerance_pct=_TOL_PCT,
        )


def test_negative_tolerance_rejected() -> None:
    with pytest.raises(ValueError, match="tolerance_eur"):
        compute_tolerance(
            Decimal("10"),
            Decimal("10"),
            tolerance_eur=Decimal("-1"),
            tolerance_pct=_TOL_PCT,
        )


def test_nan_input_rejected() -> None:
    with pytest.raises(ValueError, match="must be finite"):
        compute_tolerance(
            Decimal("NaN"),
            Decimal("1"),
            tolerance_eur=_TOL_EUR,
            tolerance_pct=_TOL_PCT,
        )


# ─────────────────────────────────────────────────────────────────────────
# Property — FR31 "max(eur, pct)" invariant + commutativity of EUR delta
# ─────────────────────────────────────────────────────────────────────────

# Decimals with at most two decimal places (real-money grain) keep the
# hypothesis search efficient and the assertions stable.
_PRICES = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("10000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)
_TOLERANCE_EUR = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("100"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)
_TOLERANCE_PCT = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("100"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)


@settings(max_examples=200)
@given(price_a=_PRICES, price_b=_PRICES, tol_eur=_TOLERANCE_EUR, tol_pct=_TOLERANCE_PCT)
def test_tolerance_used_names_the_binding_leg(
    price_a: Decimal,
    price_b: Decimal,
    tol_eur: Decimal,
    tol_pct: Decimal,
) -> None:
    result = compute_tolerance(price_a, price_b, tolerance_eur=tol_eur, tolerance_pct=tol_pct)
    pct_leg = price_a * tol_pct / Decimal("100")
    expected_value = max(tol_eur, pct_leg)
    assert result.tolerance_value == expected_value
    if tol_eur >= pct_leg:
        assert result.tolerance_used == "eur"
    else:
        assert result.tolerance_used == "pct"


@settings(max_examples=200)
@given(price_a=_PRICES, price_b=_PRICES, tol_eur=_TOLERANCE_EUR, tol_pct=_TOLERANCE_PCT)
def test_pass_iff_delta_within_max_tolerance(
    price_a: Decimal,
    price_b: Decimal,
    tol_eur: Decimal,
    tol_pct: Decimal,
) -> None:
    result = compute_tolerance(price_a, price_b, tolerance_eur=tol_eur, tolerance_pct=tol_pct)
    delta = abs(price_a - price_b)
    expected_pass = delta <= max(tol_eur, price_a * tol_pct / Decimal("100"))
    assert result.passed is expected_pass


@settings(max_examples=200)
@given(price_a=_PRICES, price_b=_PRICES, tol_eur=_TOLERANCE_EUR, tol_pct=_TOLERANCE_PCT)
def test_eur_delta_is_commutative(
    price_a: Decimal,
    price_b: Decimal,
    tol_eur: Decimal,
    tol_pct: Decimal,
) -> None:
    """Swapping ``price_a`` and ``price_b`` keeps the EUR delta identical
    (the % leg is anchored on price_a, so the rest may differ)."""
    forward = compute_tolerance(price_a, price_b, tolerance_eur=tol_eur, tolerance_pct=tol_pct)
    backward = compute_tolerance(price_b, price_a, tolerance_eur=tol_eur, tolerance_pct=tol_pct)
    assert forward.delta_eur == backward.delta_eur


@given(price=_PRICES, tol_eur=_TOLERANCE_EUR, tol_pct=_TOLERANCE_PCT)
def test_identical_prices_always_pass(
    price: Decimal,
    tol_eur: Decimal,
    tol_pct: Decimal,
) -> None:
    result = compute_tolerance(price, price, tolerance_eur=tol_eur, tolerance_pct=tol_pct)
    assert result.passed is True
    assert result.delta_eur == Decimal("0")
