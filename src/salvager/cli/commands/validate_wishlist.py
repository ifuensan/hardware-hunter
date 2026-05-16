"""``salvager validate-wishlist`` — FR40 + Story 2.4.

Composes Stories 2.1/2.2/2.3 into a one-shot operator gate:

  1. File-not-found → exit 1 with a "run init to scaffold" hint
  2. Parse error / scope violation / pydantic error → exit 3 with the
     appropriate locked error template
  3. Otherwise → exit 0 with a single ``✓`` summary line

The (c3) scope-error template is locked at Story 2.2 and reproduced
below as ``SCOPE_ERROR_HINT_1`` / ``SCOPE_ERROR_HINT_2``. Any change to
that wording is a PRD amendment.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import typer

from salvager.config.wishlist_yaml import (
    WishlistParseError,
    WishlistScopeError,
    WishlistValidationError,
    load_wishlist,
)
from salvager.domain.wishlist import Wishlist
from salvager.observability.styling import render_prose

# Locked (c3) hint pair — Story 2.2 AC. Don't reword without PRD amendment.
SCOPE_ERROR_HINT_1 = (
    "salvager does not support arbitrage scoring per the (c3) scope contract."
)
SCOPE_ERROR_HINT_2 = (
    "See ROADMAP.md for the future-research repo path: "
    "github.com/ifuensan/salvager-research (stub)."
)

# Pydantic's duplicate-entry error message shape (defined in
# domain/wishlist.py). Parsed back out to resolve line numbers in the
# YAML doc for the operator-facing error.
_DUPLICATE_KEY_RE = re.compile(
    r"duplicate entry key .* entries\[(?P<a>\d+)\] and entries\[(?P<b>\d+)\]"
)


def run(path: Path, output_format: str) -> int:
    """Validate ``path`` and emit a human or JSON report. Returns the exit code."""
    if output_format not in {"human", "json"}:
        _render_error_or_json(
            output_format,
            message=f"unknown --format value: {output_format!r}",
            hint="use --format human or --format json",
            exit_code=2,
        )
        return 2

    if not path.exists():
        _render_error_or_json(
            output_format,
            message=f"wishlist.yaml not found at {path}",
            hint="run salvager init to scaffold one",
            exit_code=1,
        )
        return 1

    try:
        wishlist = load_wishlist(path)
    except WishlistScopeError as exc:
        _emit_scope_error(output_format, exc)
        return 3
    except WishlistValidationError as exc:
        _emit_validation_error(output_format, exc)
        return 3
    except WishlistParseError as exc:
        _emit_parse_error(output_format, exc)
        return 3

    _emit_success(output_format, wishlist)
    return 0


# ─────────────────────────────────────────────────────────────────────────
# Renderers
# ─────────────────────────────────────────────────────────────────────────


def _emit_success(output_format: str, wishlist: Wishlist) -> None:
    entry_count = len(wishlist.entries)
    phase2_enabled_count = sum(1 for e in wishlist.entries if e.phase2.enabled)

    if output_format == "json":
        typer.echo(
            json.dumps(
                {
                    "valid": True,
                    "entry_count": entry_count,
                    "phase2_enabled_count": phase2_enabled_count,
                }
            )
        )
        return

    render_prose(
        f"wishlist.yaml is valid ({entry_count} entries; "
        f"{phase2_enabled_count} with Phase 2 enabled)",
        style="success",
    )


def _emit_scope_error(output_format: str, exc: WishlistScopeError) -> None:
    """Render the locked (c3) error template."""
    first = exc.violations[0]
    entry_name = _resolve_entry_name(exc.doc, first.path)
    location = f"{exc.path}:{first.line_number}" if first.line_number else f"{exc.path}"
    entry_suffix = f" (entry: {entry_name})" if entry_name else ""
    message = f"{location}: forbidden field '{first.field_name}'{entry_suffix}"

    if output_format == "json":
        _json_error(message=message, exit_code=3)
        return

    render_prose(message, style="error", hint=SCOPE_ERROR_HINT_1)
    sys.stderr.write(f"hint: {SCOPE_ERROR_HINT_2}\n")

    extras = len(exc.violations) - 1
    if extras > 0:
        render_prose(
            f"{extras} additional scope violation(s) — fix one at a time and re-run.",
            style="secondary",
        )


def _emit_validation_error(output_format: str, exc: WishlistValidationError) -> None:
    first = exc.errors[0]
    msg = first["msg"]

    # Cross-entry duplicate detection — the AC requires naming BOTH entries
    # with their line numbers.
    match = _DUPLICATE_KEY_RE.search(msg)
    if match and exc.doc is not None:
        index_a = int(match["a"])
        index_b = int(match["b"])
        line_a = _resolve_entry_line(exc.doc, index_a)
        line_b = _resolve_entry_line(exc.doc, index_b)
        loc_a = f"{exc.path}:{line_a}" if line_a else f"{exc.path} entries[{index_a}]"
        loc_b = f"{exc.path}:{line_b}" if line_b else f"{exc.path} entries[{index_b}]"
        rendered = f"duplicate entry key — {loc_a} and {loc_b}"
        if output_format == "json":
            _json_error(message=rendered, exit_code=3)
            return
        render_prose(
            rendered,
            style="error",
            hint="each (manufacturer, model, ref) tuple must be unique (FR4)",
        )
        return

    loc = first.get("loc_str") or ".".join(str(p) for p in first.get("loc", ()))
    line_part = f":{first['line_number']}" if first.get("line_number") else ""
    rendered = f"{exc.path}{line_part}: {loc}: {msg}"
    if output_format == "json":
        _json_error(message=rendered, exit_code=3)
        return
    render_prose(rendered, style="error", hint="run --format json for machine-readable output")


def _emit_parse_error(output_format: str, exc: WishlistParseError) -> None:
    message = f"{exc.path}:{exc.line}:{exc.column}: malformed YAML"
    if output_format == "json":
        _json_error(message=message, exit_code=3)
        return
    render_prose(
        message, style="error", hint="re-run with --format json to see the ruamel.yaml diagnostic"
    )


def _render_error_or_json(
    output_format: str, *, message: str, hint: str | None, exit_code: int
) -> None:
    if output_format == "json":
        _json_error(message=message, exit_code=exit_code)
        return
    render_prose(message, style="error", hint=hint)


def _json_error(*, message: str, exit_code: int) -> None:
    """Write a single-line JSON error envelope to stderr (UX-DR21 contract)."""
    sys.stderr.write(
        json.dumps({"error": "validate_wishlist", "message": message, "exit_code": exit_code})
        + "\n"
    )


# ─────────────────────────────────────────────────────────────────────────
# Doc helpers — resolve entry context for the error templates
# ─────────────────────────────────────────────────────────────────────────


def _resolve_entry_name(doc: Any, violation_path: str) -> str | None:
    """Pull the entry's ``model`` field (per the locked Story 2.2 template).

    The violation path looks like ``entries[2].expected_resale_value``;
    we extract the index and fish ``model`` out of the parsed YAML. The
    entry may be invalid (e.g. missing ``model``), in which case we
    return None and the caller drops the ``(entry: …)`` suffix.
    """
    index = _parse_entry_index(violation_path)
    entry = _entry_at(doc, index)
    if entry is None:
        return None
    model = entry.get("model") if hasattr(entry, "get") else None
    return str(model) if model else None


def _resolve_entry_line(doc: Any, index: int) -> int | None:
    """1-based line number of ``entries[index]`` from ruamel's lc info."""
    entries = _entries_seq(doc)
    if entries is None or index >= len(entries):
        return None
    lc = getattr(entries, "lc", None)
    if lc is None:
        return None
    try:
        position = lc.item(index)
    except (KeyError, AttributeError, TypeError):
        return None
    if not position:
        return None
    return int(position[0]) + 1


def _parse_entry_index(violation_path: str) -> int | None:
    """``entries[2].foo`` → ``2``; returns None for any other shape."""
    match = re.match(r"entries\[(\d+)\]", violation_path)
    if not match:
        return None
    return int(match.group(1))


def _entry_at(doc: Any, index: int | None) -> Any:
    if index is None:
        return None
    entries = _entries_seq(doc)
    if entries is None or index >= len(entries):
        return None
    return entries[index]


def _entries_seq(doc: Any) -> Any:
    """Return the ``entries`` sequence from a parsed wishlist doc, or None."""
    if doc is None or not hasattr(doc, "get"):
        return None
    entries = doc.get("entries")
    if entries is None or not hasattr(entries, "__len__"):
        return None
    return entries
