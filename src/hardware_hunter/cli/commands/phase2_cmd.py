"""``hardware-hunter phase2 enable/disable/status`` — Story 5.12.

Three operator-facing commands manage Phase 2 per-entry opt-in, plus
the per-entry / global disable paths and the at-a-glance status table.
All three respect the AR12 contract: ``wishlist.yaml`` is the canonical
source of truth, rewrites go through the ruamel round-trip loader so
comments and quoting survive, and the global Phase 2 lockout state
lives in SQLite (``phase2_state``) — the CLI never tries to hold state
in memory across invocations.

Recovery boundaries (FR35 / NFR-R4)
-----------------------------------
- ``enable`` is the *only* path that lifts the global lockout. It calls
  ``Phase2AuditWriter.clear_global_disable(entry_key)`` and resets the
  consecutive-failure counter, naming the entry being re-enabled.
- ``disable`` (per-entry) flips the wishlist flag and does NOT touch
  the global lockout — a single bad entry doesn't shut Phase 2 down.
- ``disable --all`` is the "kill everything" path, gated by a
  typing-a-number confirmation per UX-DR23. It also flips the global
  lockout with ``operator_disable_all`` for an extra layer of safety.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from pathlib import Path

from hardware_hunter.adapters.sqlite_store import Phase2AuditWriter, open_connection
from hardware_hunter.adapters.sqlite_store.migrations import db_path_under
from hardware_hunter.adapters.sqlite_store.phase2_state_reader import (
    SqlitePhase2StateReader,
)
from hardware_hunter.config.wishlist_yaml import load_wishlist, save_wishlist
from hardware_hunter.domain.phase2_audit import Phase2StateSnapshot
from hardware_hunter.domain.wishlist import Phase2Settings, Wishlist, WishlistEntry
from hardware_hunter.observability.logging import get_logger
from hardware_hunter.observability.styling import (
    ColumnSpec,
    print_table,
    render_prose,
    render_table,
)

_USAGE_EXIT = 2
_USER_CANCELLED_EXIT = 1


# ─────────────────────────────────────────────────────────────────────────
# Entry lookup — case-insensitive substring match on ref / model / display
# ─────────────────────────────────────────────────────────────────────────


def _resolve_entry(wishlist: Wishlist, query: str) -> WishlistEntry | None:
    """Find the wishlist entry the operator meant.

    Match rules (in order): exact ref (case-insensitive) wins; else a
    case-insensitive substring match against ref, model, or display
    name. If multiple substring matches exist, return None so the
    caller can render an ambiguous-query error.
    """
    needle = query.casefold()
    exact = [e for e in wishlist.entries if e.ref.casefold() == needle]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return None
    candidates = [
        e
        for e in wishlist.entries
        if needle in e.ref.casefold()
        or needle in e.model.casefold()
        or needle in e.display_name.casefold()
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _entry_not_found(query: str) -> int:
    render_prose(
        f"entry {query!r} not found in wishlist.yaml",
        style="error",
        hint="hardware-hunter wishlist list to see valid entry IDs",
    )
    return _USAGE_EXIT


# ─────────────────────────────────────────────────────────────────────────
# `phase2 enable`
# ─────────────────────────────────────────────────────────────────────────


def run_enable(
    *,
    query: str,
    wishlist_path: Path,
    data_dir: Path,
    is_tty: Callable[[], bool] = sys.stdin.isatty,
    input_fn: Callable[[str], str] = input,
) -> int:
    """Flip an entry's ``phase2.enabled`` and lift the global lockout."""
    wishlist = load_wishlist(wishlist_path)
    entry = _resolve_entry(wishlist, query)
    if entry is None:
        return _entry_not_found(query)

    max_price = entry.phase2.max_price_eur
    if max_price is None:
        if not is_tty():
            render_prose(
                f"{entry.display_name} has no phase2.max_price_eur set",
                style="error",
                hint="run this command in an interactive terminal to set it now, "
                "or edit wishlist.yaml directly",
            )
            return _USAGE_EXIT
        prompted = _prompt_for_max_price(entry, input_fn)
        if prompted is None:
            return _USER_CANCELLED_EXIT
        max_price = prompted

    new_phase2 = Phase2Settings(enabled=True, max_price_eur=max_price)
    updated_entry = entry.model_copy(update={"phase2": new_phase2})
    new_entries = [updated_entry if e is entry else e for e in wishlist.entries]
    new_wishlist = wishlist.model_copy(update={"entries": new_entries})
    # The loader attaches the ruamel doc to the original wishlist; we
    # carry it across model_copy explicitly so save_wishlist preserves
    # the file's comments and quoting.
    yaml_doc = getattr(wishlist, "__yaml_doc__", None)
    if yaml_doc is not None:
        object.__setattr__(new_wishlist, "__yaml_doc__", yaml_doc)
    save_wishlist(wishlist_path, new_wishlist)

    asyncio.run(_clear_lockout_and_reset_counter(data_dir, entry))
    render_prose(
        f"Phase 2 enabled for {entry.display_name} "
        f"(max: {_format_es(max_price)}; threshold: {entry.confidence_threshold}; "
        "circuit reset)",
        style="success",
    )
    return 0


def _prompt_for_max_price(
    entry: WishlistEntry,
    input_fn: Callable[[str], str],
) -> Decimal | None:
    while True:
        try:
            raw = input_fn(
                f"Set phase2.max_price_eur for {entry.display_name} (e.g. 60.00; blank to cancel): "
            )
        except (EOFError, KeyboardInterrupt):
            return None
        if not raw.strip():
            return None
        try:
            value = Decimal(raw.strip().replace(",", "."))
        except InvalidOperation:
            render_prose(f"not a number: {raw!r}", style="error")
            continue
        if value <= Decimal("0"):
            render_prose("price must be > 0", style="error")
            continue
        return value


async def _clear_lockout_and_reset_counter(data_dir: Path, entry: WishlistEntry) -> None:
    writer = Phase2AuditWriter(db_path_under(data_dir))
    try:
        await writer.clear_global_disable(entry.entry_key)
        await writer.reset_failure_counter()
    finally:
        await writer.close()


# ─────────────────────────────────────────────────────────────────────────
# `phase2 disable` and `phase2 disable --all`
# ─────────────────────────────────────────────────────────────────────────


def run_disable(
    *,
    query: str | None,
    all_entries: bool,
    wishlist_path: Path,
    data_dir: Path,
    is_tty: Callable[[], bool] = sys.stdin.isatty,
    input_fn: Callable[[str], str] = input,
) -> int:
    if all_entries:
        return _disable_all(
            wishlist_path=wishlist_path,
            data_dir=data_dir,
            is_tty=is_tty,
            input_fn=input_fn,
        )
    if query is None:
        render_prose(
            "phase2 disable requires <entry> or --all",
            style="error",
            hint="hardware-hunter phase2 disable <entry-ref>",
        )
        return _USAGE_EXIT

    wishlist = load_wishlist(wishlist_path)
    entry = _resolve_entry(wishlist, query)
    if entry is None:
        return _entry_not_found(query)

    new_phase2 = Phase2Settings(enabled=False, max_price_eur=entry.phase2.max_price_eur)
    updated_entry = entry.model_copy(update={"phase2": new_phase2})
    new_entries = [updated_entry if e is entry else e for e in wishlist.entries]
    new_wishlist = wishlist.model_copy(update={"entries": new_entries})
    yaml_doc = getattr(wishlist, "__yaml_doc__", None)
    if yaml_doc is not None:
        object.__setattr__(new_wishlist, "__yaml_doc__", yaml_doc)
    save_wishlist(wishlist_path, new_wishlist)
    render_prose(f"Phase 2 disabled for {entry.display_name}", style="success")
    return 0


def _disable_all(
    *,
    wishlist_path: Path,
    data_dir: Path,
    is_tty: Callable[[], bool],
    input_fn: Callable[[str], str],
) -> int:
    if not is_tty():
        render_prose(
            "--all requires an interactive terminal",
            style="error",
            hint="re-run in a TTY, or disable entries individually",
        )
        return _USER_CANCELLED_EXIT

    wishlist = load_wishlist(wishlist_path)
    enabled_entries = [e for e in wishlist.entries if e.phase2.enabled]
    count = len(enabled_entries)
    if count == 0:
        render_prose("no entries currently have Phase 2 enabled", style="info")
        return 0

    try:
        confirmation = input_fn(f"Type the number {count} to confirm: ")
    except (EOFError, KeyboardInterrupt):
        confirmation = ""
    if confirmation.strip() != str(count):
        render_prose("aborted — no changes made", style="info")
        return _USER_CANCELLED_EXIT

    new_entries = [
        e.model_copy(
            update={"phase2": Phase2Settings(enabled=False, max_price_eur=e.phase2.max_price_eur)}
        )
        if e.phase2.enabled
        else e
        for e in wishlist.entries
    ]
    new_wishlist = wishlist.model_copy(update={"entries": new_entries})
    yaml_doc = getattr(wishlist, "__yaml_doc__", None)
    if yaml_doc is not None:
        object.__setattr__(new_wishlist, "__yaml_doc__", yaml_doc)
    save_wishlist(wishlist_path, new_wishlist)

    asyncio.run(_set_global_lockout(data_dir, reason="operator_disable_all"))
    log = get_logger("cli.phase2")
    log.warning(
        "phase2_disabled",
        extra={
            "reason": "operator_disable_all",
            "entries_disabled": count,
            "last_affected_entry": enabled_entries[-1].display_name,
        },
    )
    render_prose(
        f"Phase 2 disabled for {count} entries · global lockout activated "
        "(reason: operator_disable_all)",
        style="success",
    )
    return 0


async def _set_global_lockout(data_dir: Path, *, reason: str) -> None:
    writer = Phase2AuditWriter(db_path_under(data_dir))
    try:
        await writer.set_global_disable(reason)
    finally:
        await writer.close()


# ─────────────────────────────────────────────────────────────────────────
# `phase2 status`
# ─────────────────────────────────────────────────────────────────────────


def run_status(
    *,
    wishlist_path: Path,
    data_dir: Path,
    output_format: str = "human",
    circuit_breaker_threshold: int = 3,
    width: int = 80,
) -> int:
    if output_format not in ("human", "json"):
        render_prose(
            f"unknown --format value: {output_format!r}",
            style="error",
            hint="use --format human or --format json",
        )
        return _USAGE_EXIT

    if not wishlist_path.exists():
        render_prose(
            f"wishlist not found at {wishlist_path}",
            style="error",
            hint="run `hardware-hunter init` to scaffold one",
        )
        return _USER_CANCELLED_EXIT
    wishlist = load_wishlist(wishlist_path)
    state = _read_state_or_default(data_dir)
    last_buy_by_entry = _last_buy_attempt_per_entry(data_dir)

    rows: list[dict[str, object]] = []
    json_entries: list[dict[str, object]] = []
    for entry in wishlist.entries:
        last_attempt, outcome = last_buy_by_entry.get(entry.entry_key, (None, None))
        max_price = (
            _format_es(entry.phase2.max_price_eur)
            if entry.phase2.max_price_eur is not None
            else None
        )
        rows.append(
            {
                "Entry": entry.display_name,
                "Phase 2 Enabled?": "yes" if entry.phase2.enabled else "no",
                "Max Price": max_price,
                "Confidence Threshold": entry.confidence_threshold,
                "Last Buy Attempt": last_attempt,
                "Outcome": outcome,
            }
        )
        json_entries.append(
            {
                "entry_key": list(entry.entry_key),
                "display_name": entry.display_name,
                "phase2_enabled": entry.phase2.enabled,
                "max_price_eur": (
                    str(entry.phase2.max_price_eur)
                    if entry.phase2.max_price_eur is not None
                    else None
                ),
                "confidence_threshold": entry.confidence_threshold,
                "last_buy_attempt": last_attempt,
                "outcome": outcome,
            }
        )

    circuit_label = _circuit_label(state, circuit_breaker_threshold)
    smoke_label = _smoke_label(state)
    footer = (
        f"Globally disabled: {'yes' if state.globally_disabled else 'no'} · "
        f"Circuit: {circuit_label} · "
        f"Last smoke: {smoke_label}"
    )

    if output_format == "json":
        payload = {
            "entries": json_entries,
            "globally_disabled": state.globally_disabled,
            "disabled_reason": state.disabled_reason,
            "disabled_at": state.disabled_at.isoformat() if state.disabled_at else None,
            "consecutive_failures": state.consecutive_failures,
            "circuit_breaker_threshold": circuit_breaker_threshold,
            "last_smoke_result": state.last_smoke_result,
            "last_smoke_at": (state.last_smoke_at.isoformat() if state.last_smoke_at else None),
        }
        print(json.dumps(payload, indent=2))
        return 0

    columns: list[ColumnSpec] = [
        {"key": "Entry"},
        {"key": "Phase 2 Enabled?"},
        {"key": "Max Price", "align": "right"},
        {"key": "Confidence Threshold"},
        {"key": "Last Buy Attempt"},
        {"key": "Outcome"},
    ]
    print_table(render_table(rows, columns, width=width), width=width)
    render_prose(footer, style="info")
    return 0


def _read_state_or_default(data_dir: Path) -> Phase2StateSnapshot:
    """Read the persisted Phase 2 state or a clean default when the DB
    isn't present yet (pre-init / pre-daemon environments)."""
    db_path = db_path_under(data_dir)
    if not db_path.exists():
        return Phase2StateSnapshot(globally_disabled=False, consecutive_failures=0)
    return asyncio.run(_read_state(data_dir))


async def _read_state(data_dir: Path) -> Phase2StateSnapshot:
    reader = SqlitePhase2StateReader(db_path_under(data_dir))
    try:
        return await reader.read()
    finally:
        await reader.close()


def _last_buy_attempt_per_entry(
    data_dir: Path,
) -> dict[tuple[str, str, str], tuple[str | None, str | None]]:
    """Most-recent ``transactions.committed_at`` joined to the alert's entry."""
    db_path = db_path_under(data_dir)
    if not db_path.exists():
        return {}
    connection: sqlite3.Connection = open_connection(db_path)
    try:
        rows = connection.execute(
            """
            SELECT a.entry_manufacturer, a.entry_model, a.entry_ref,
                   MAX(t.committed_at) AS last_attempt
            FROM transactions t
            JOIN alert_snapshots a ON a.alert_id = t.alert_id
            GROUP BY a.entry_manufacturer, a.entry_model, a.entry_ref
            """
        ).fetchall()
    finally:
        connection.close()

    out: dict[tuple[str, str, str], tuple[str | None, str | None]] = {}
    for row in rows:
        key = (
            str(row["entry_manufacturer"]),
            str(row["entry_model"]),
            str(row["entry_ref"]),
        )
        out[key] = (str(row["last_attempt"]), "success")
    return out


def _circuit_label(state: Phase2StateSnapshot, threshold: int) -> str:
    if state.consecutive_failures >= threshold:
        return f"open {state.consecutive_failures}/{threshold}"
    return f"closed {state.consecutive_failures}/{threshold}"


def _smoke_label(state: Phase2StateSnapshot) -> str:
    if state.last_smoke_at is None or state.last_smoke_result is None:
        return "never run"
    return f"{state.last_smoke_result} at {state.last_smoke_at.isoformat()}"


def _format_es(value: Decimal) -> str:
    """ES-style EUR — mirrors the renderer's ``_format_price_es`` so the
    CLI and Telegram surface stay visually consistent."""
    quantized = value.quantize(Decimal("0.01"))
    integer_part, _, decimal_part = str(quantized).partition(".")
    sign = ""
    if integer_part.startswith("-"):
        sign = "-"
        integer_part = integer_part[1:]
    chunks: list[str] = []
    while len(integer_part) > 3:
        chunks.append(integer_part[-3:])
        integer_part = integer_part[:-3]
    chunks.append(integer_part)
    grouped = ".".join(reversed(chunks))
    return f"{sign}{grouped},{decimal_part} €"


__all__ = ["run_disable", "run_enable", "run_status"]
