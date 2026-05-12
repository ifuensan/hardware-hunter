"""Scope guard — enforces the (c3) "no arbitrage" contract at the schema layer.

This module rejects any wishlist YAML that contains arbitrage-flavored
fields. The check runs BEFORE pydantic validation (per Story 2.3's
loader order) so the error anchors to the scope contract — pointing the
operator at ROADMAP.md and the future-research repo path — instead of
looking like a generic typo from pydantic's ``extra_forbidden``.

The forbidden set is a ``Final[frozenset[str]]`` deliberately: a unit
test asserts that the constant is immutable via the module API alone
(no rebinding, no in-place mutation possible). Expanding the set is a
PRD amendment, not a one-line change.

Why duck-typed line numbers
---------------------------
``ruamel.yaml.comments.CommentedMap`` exposes per-key line/col info via
``.lc.key(name)``. We attribute-test for ``.lc`` instead of importing
ruamel here so this module stays pure-domain — the YAML library lives
behind ``config/wishlist_yaml.py`` (Story 2.3).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

# Locked set per FR3. Anchored to the (c3) scope contract; growth is a
# PRD amendment, not a code change. Names are matched case-insensitively
# so neither YAML key-casing nor sneaky CamelCase variants can slip past.
FORBIDDEN_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "expected_resale_value",
        "min_margin_percent",
        "current_market_price",
        "target_resale_margin",
        "arbitrage_score",
        "resale_target",
    }
)


@dataclass(frozen=True)
class ScopeViolation:
    """One forbidden field found in the wishlist tree.

    The CLI (Story 2.4) formats the locked error template using these
    fields. The loader (Story 2.3) makes scope violations the
    highest-priority error so the operator sees one anchored to ROADMAP
    rather than a wall of pydantic noise.
    """

    path: str
    field_name: str
    line_number: int | None


def check_scope_violations(raw_yaml: object) -> list[ScopeViolation]:
    """Walk a parsed YAML structure and collect every forbidden-field hit.

    ``raw_yaml`` is whatever the YAML library returned — typically a dict
    or a ``ruamel.yaml.comments.CommentedMap`` at the top level. The walk
    is recursive and order-preserving so violation messages list hits in
    document order, which keeps error output readable on long wishlists.
    """
    return list(_walk(raw_yaml, path=""))


def _walk(node: Any, *, path: str) -> Iterator[ScopeViolation]:
    if isinstance(node, Mapping):
        for key, value in node.items():
            key_str = str(key)
            child_path = f"{path}.{key_str}" if path else key_str
            if key_str.lower() in FORBIDDEN_FIELDS:
                yield ScopeViolation(
                    path=child_path,
                    field_name=key_str.lower(),
                    line_number=_key_line(node, key),
                )
            yield from _walk(value, path=child_path)
    elif isinstance(node, Sequence) and not isinstance(node, str | bytes):
        for index, item in enumerate(node):
            yield from _walk(item, path=f"{path}[{index}]")


def _key_line(node: Mapping[Any, Any], key: object) -> int | None:
    """Pull the 1-based line number from a ruamel.yaml CommentedMap, if any.

    Returns ``None`` for plain dicts (loaded via PyYAML's safe-load) or
    when ruamel didn't attach position info for this key (e.g. dynamically
    constructed nodes). Callers must tolerate missing line numbers.
    """
    lc = getattr(node, "lc", None)
    if lc is None:
        return None
    try:
        position = lc.key(key)
    except (KeyError, AttributeError, TypeError):
        return None
    if not position:
        return None
    # ruamel uses 0-based line numbers; the operator-facing convention
    # (matching their editor's gutter) is 1-based.
    return int(position[0]) + 1
