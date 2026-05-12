"""Tests for the (c3) scope guard — FR3 enforcement at the schema layer."""

from __future__ import annotations

import io

import pytest
from ruamel.yaml import YAML

from hardware_hunter.domain.scope_guard import (
    FORBIDDEN_FIELDS,
    ScopeViolation,
    check_scope_violations,
)


def _load_with_line_info(yaml_text: str) -> object:
    """Parse YAML with ruamel so line numbers are attached to keys."""
    return YAML(typ="rt").load(io.StringIO(yaml_text))


# ─────────────────────────────────────────────────────────────────────────
# FORBIDDEN_FIELDS — immutability contract
# ─────────────────────────────────────────────────────────────────────────


def test_forbidden_fields_contains_locked_set() -> None:
    assert (
        frozenset(
            {
                "expected_resale_value",
                "min_margin_percent",
                "current_market_price",
                "target_resale_margin",
                "arbitrage_score",
                "resale_target",
            }
        )
        == FORBIDDEN_FIELDS
    )


def test_forbidden_fields_is_frozen() -> None:
    """frozenset has no .add() — module API alone cannot grow the set."""
    assert isinstance(FORBIDDEN_FIELDS, frozenset)
    with pytest.raises(AttributeError):
        FORBIDDEN_FIELDS.add("extra_field")  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────────────────


def test_compliant_yaml_returns_empty_list() -> None:
    yaml_text = """\
entries:
  - manufacturer: Western Digital
    model: WD Red Plus 4TB
    ref: WD40EFPX
    type: hdd
    max_price_solo: 60.00
    keywords:
      - "WD Red Plus 4TB"
    confidence_threshold: high
    phase2:
      enabled: false
"""
    assert check_scope_violations(_load_with_line_info(yaml_text)) == []


def test_empty_input_is_compliant() -> None:
    assert check_scope_violations({}) == []
    assert check_scope_violations({"entries": []}) == []
    assert check_scope_violations(None) == []


# ─────────────────────────────────────────────────────────────────────────
# Detection — every forbidden field, at every depth
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("forbidden", sorted(FORBIDDEN_FIELDS))
def test_each_forbidden_field_is_detected(forbidden: str) -> None:
    """Every member of FORBIDDEN_FIELDS triggers a violation."""
    yaml_text = f"""\
entries:
  - manufacturer: WD
    model: Red
    ref: WD40EFPX
    type: hdd
    {forbidden}: 100.00
"""
    violations = check_scope_violations(_load_with_line_info(yaml_text))
    assert len(violations) == 1
    assert violations[0].field_name == forbidden


def test_detection_is_case_insensitive() -> None:
    """YAML allows arbitrary key casing; CamelCase shouldn't slip past."""
    raw = {
        "entries": [
            {"manufacturer": "WD", "Expected_Resale_Value": 80.00},
        ],
    }
    violations = check_scope_violations(raw)
    assert len(violations) == 1
    assert violations[0].field_name == "expected_resale_value"


def test_violation_reports_dotted_path_with_index() -> None:
    yaml_text = """\
entries:
  - manufacturer: WD
    model: Red
    ref: WD40EFPX
    type: hdd
  - manufacturer: Crucial
    model: DDR4
    ref: CT16
    type: ram
    expected_resale_value: 80.00
"""
    violations = check_scope_violations(_load_with_line_info(yaml_text))
    assert len(violations) == 1
    assert violations[0].path == "entries[1].expected_resale_value"


def test_multiple_violations_returned_in_document_order() -> None:
    yaml_text = """\
entries:
  - manufacturer: WD
    expected_resale_value: 80.00
  - manufacturer: Crucial
    min_margin_percent: 15
"""
    violations = check_scope_violations(_load_with_line_info(yaml_text))
    assert [v.field_name for v in violations] == [
        "expected_resale_value",
        "min_margin_percent",
    ]
    assert [v.path for v in violations] == [
        "entries[0].expected_resale_value",
        "entries[1].min_margin_percent",
    ]


def test_violation_detected_in_nested_mapping() -> None:
    """Forbidden field hidden inside a nested mapping is still caught."""
    raw = {
        "entries": [
            {
                "manufacturer": "WD",
                "phase2": {
                    "enabled": True,
                    "arbitrage_score": 0.75,
                },
            },
        ],
    }
    violations = check_scope_violations(raw)
    assert len(violations) == 1
    assert violations[0].path == "entries[0].phase2.arbitrage_score"
    assert violations[0].field_name == "arbitrage_score"


# ─────────────────────────────────────────────────────────────────────────
# Line numbers — ruamel.yaml integration + graceful fallback
# ─────────────────────────────────────────────────────────────────────────


def test_line_number_present_for_ruamel_parsed_yaml() -> None:
    yaml_text = """\
entries:
  - manufacturer: WD
    model: Red
    ref: WD40EFPX
    type: hdd
    expected_resale_value: 80.00
"""
    violations = check_scope_violations(_load_with_line_info(yaml_text))
    assert len(violations) == 1
    # The forbidden line is the 6th line of the document (1-based).
    assert violations[0].line_number == 6


def test_line_number_is_none_for_plain_dict() -> None:
    """Plain dict (e.g. from PyYAML safe-load) has no line metadata."""
    raw = {"entries": [{"expected_resale_value": 80.00}]}
    violations = check_scope_violations(raw)
    assert len(violations) == 1
    assert violations[0].line_number is None


# ─────────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────────


def test_strings_are_not_walked_as_sequences() -> None:
    """``str`` is a Sequence too — make sure we don't recurse character by character."""
    raw = {"entries": [{"keywords": "expected_resale_value"}]}
    assert check_scope_violations(raw) == []


def test_violation_dataclass_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    violation = ScopeViolation(path="x.y", field_name="arbitrage_score", line_number=42)
    with pytest.raises(FrozenInstanceError):
        violation.path = "z"  # type: ignore[misc]
