"""Price-reconciliation math — Story 5.4 (FR31).

Pure decimal arithmetic, zero IO. The two prices we compare can come
from any source (cross-source re-fetch, receipt-vs-alert); the result
is the same shape so the orchestrator can render and route both cases
uniformly.

Tolerance rule (PRD FR31)
-------------------------
The effective tolerance is ``max(tolerance_eur, price_a *
tolerance_pct / 100)`` — the bigger of the absolute floor and the
percentage cushion. ``tolerance_used`` names which one bound the
decision so the operator's alert ctx can show whether the EUR floor
or the percent cushion was the binding constraint.

Edge cases
----------
- Negative prices and negative tolerances are programming errors here
  (parsed prices should already be sanitized upstream) and raise
  :class:`ValueError`.
- A reference price of zero short-circuits the percent leg to zero so
  the floor decides the outcome — without it the % math would divide
  by zero. ``delta_pct`` is reported as 0 in that case; the audit row
  carries the raw EUR delta which is the meaningful number anyway.
- NaN / non-finite Decimals are rejected explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

ToleranceKind = Literal["eur", "pct"]

_HUNDRED: Final[Decimal] = Decimal("100")
_ZERO: Final[Decimal] = Decimal("0")


@dataclass(frozen=True)
class ReconciliationResult:
    """The outcome of comparing two prices against a configured tolerance."""

    passed: bool
    delta_eur: Decimal
    delta_pct: Decimal
    tolerance_used: ToleranceKind
    tolerance_value: Decimal


def _ensure_finite_non_negative(name: str, value: Decimal) -> None:
    if not value.is_finite():
        raise ValueError(f"{name} must be finite; got {value}")
    if value < _ZERO:
        raise ValueError(f"{name} must be non-negative; got {value}")


def compute_tolerance(
    price_a: Decimal,
    price_b: Decimal,
    *,
    tolerance_eur: Decimal,
    tolerance_pct: Decimal,
) -> ReconciliationResult:
    """Compare two prices against the configured tolerance.

    ``price_a`` is the reference: the percent leg is computed off it
    (``price_a * tolerance_pct / 100``). The result's ``tolerance_used``
    names whichever leg won the ``max(...)`` — the binding constraint.
    """
    _ensure_finite_non_negative("price_a", price_a)
    _ensure_finite_non_negative("price_b", price_b)
    _ensure_finite_non_negative("tolerance_eur", tolerance_eur)
    _ensure_finite_non_negative("tolerance_pct", tolerance_pct)

    delta_eur = abs(price_a - price_b)
    delta_pct = (delta_eur / price_a * _HUNDRED) if price_a > _ZERO else _ZERO

    pct_tolerance_eur = price_a * tolerance_pct / _HUNDRED
    if tolerance_eur >= pct_tolerance_eur:
        tolerance_used: ToleranceKind = "eur"
        tolerance_value = tolerance_eur
    else:
        tolerance_used = "pct"
        tolerance_value = pct_tolerance_eur

    passed = delta_eur <= tolerance_value
    return ReconciliationResult(
        passed=passed,
        delta_eur=delta_eur,
        delta_pct=delta_pct,
        tolerance_used=tolerance_used,
        tolerance_value=tolerance_value,
    )


__all__ = ["ReconciliationResult", "ToleranceKind", "compute_tolerance"]
