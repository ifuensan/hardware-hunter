"""Parser-registry tests — Story 5.13.

Drives every shipped v1.0 fixture through its real parser and asserts
the parsed value matches the independently-verified expected price. The
Q9 regression (comma-vs-dot) is the headline case.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from salvager.orchestration.phase2_parsers import default_price_parser_registry
from salvager.orchestration.smoke_test import discover_fixtures

SHIPPED_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "price_parsers" / "active"


def test_default_registry_covers_every_shipped_fixture_kind() -> None:
    fixtures = discover_fixtures(SHIPPED_FIXTURES)
    registry = default_price_parser_registry()
    missing = {f.kind for f in fixtures} - set(registry)
    assert not missing, f"no parser registered for kind(s): {missing}"


@pytest.mark.parametrize(
    "fixture_name",
    [
        "wallapop_api_typical",
        "wallapop_html_typical",
        "ebay_api_typical",
        "wallapop_html_comma_vs_dot",
    ],
)
def test_each_fixture_parses_to_its_expected_price(fixture_name: str) -> None:
    expected = json.loads(
        (SHIPPED_FIXTURES / f"{fixture_name}.expected.json").read_text(encoding="utf-8")
    )
    response_path = next(
        p
        for p in SHIPPED_FIXTURES.iterdir()
        if p.stem == fixture_name and not p.name.endswith(".expected.json")
    )
    parser = default_price_parser_registry()[expected["kind"]]
    parsed = parser(response_path.read_bytes())
    assert parsed == Decimal(expected["price_eur"]), (
        f"{fixture_name}: parsed {parsed} != expected {expected['price_eur']}"
    )


def test_q9_regression_is_decoded_correctly() -> None:
    """The Spanish 53,00 € must yield Decimal('53.00'), not 0.53 or 5300."""
    body = (SHIPPED_FIXTURES / "wallapop_html_comma_vs_dot.html").read_bytes()
    parsed = default_price_parser_registry()["wallapop_html"](body)
    assert parsed == Decimal("53.00")
