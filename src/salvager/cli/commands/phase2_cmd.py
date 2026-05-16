"""``salvager phase2 enable/disable/status`` — Story 5.12.

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
import time
from collections.abc import Callable, Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from salvager.adapters.sqlite_store import Phase2AuditWriter, open_connection
from salvager.adapters.sqlite_store.migrations import db_path_under
from salvager.adapters.sqlite_store.phase2_state_reader import (
    SqlitePhase2StateReader,
)
from salvager.config.config_yaml import load_config
from salvager.config.env import load_env_or_exit
from salvager.config.wishlist_yaml import load_wishlist, save_wishlist
from salvager.domain.alert import AlertSnapshot
from salvager.domain.evaluation import ListingEvaluation
from salvager.domain.listing import Listing
from salvager.domain.phase2_audit import (
    Phase2StateSnapshot,
    TransactionRecord,
)
from salvager.domain.reconciliation import (
    ReconciliationResult,
    compute_tolerance,
)
from salvager.domain.wishlist import Phase2Settings, Wishlist, WishlistEntry
from salvager.observability.logging import get_logger
from salvager.observability.styling import (
    ColumnSpec,
    print_table,
    render_prose,
    render_table,
)
from salvager.orchestration.degradation_reporter import Reporter
from salvager.orchestration.phase2_parsers import (
    default_price_parser_registry,
)
from salvager.orchestration.smoke_test import (
    FixtureOutcome,
    PriceParser,
    SmokeTestFixture,
    SmokeTestSummary,
    discover_fixtures,
)
from salvager.orchestration.smoke_test import (
    run_smoke_test as run_smoke_test_orchestrator,
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
        hint="salvager wishlist list to see valid entry IDs",
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
            hint="salvager phase2 disable <entry-ref>",
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
            hint="run `salvager init` to scaffold one",
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


__all__ = [
    "run_disable",
    "run_enable",
    "run_reconcile",
    "run_smoke_test",
    "run_status",
]


# ─────────────────────────────────────────────────────────────────────────
# `phase2 smoke-test` — Story 5.13 manual trigger for Story 5.6 run
# ─────────────────────────────────────────────────────────────────────────


def run_smoke_test(
    *,
    env_path: Path,
    config_path: Path,
    data_dir: Path,
    fixtures_dir: Path,
    width: int = 100,
    reporter_factory: Callable[[], Reporter] | None = None,
    parsers: Mapping[str, PriceParser] | None = None,
) -> int:
    """Re-run the daily smoke test on demand.

    On any fixture failure the orchestrator auto-disables Phase 2 globally
    (per Story 5.6) and we exit 5 — the Phase 2 guardrail code per FR48.
    ``reporter_factory`` + ``parsers`` are injection seams: tests pass
    fakes, production picks up the defaults wired below.
    """
    config = load_config(config_path)

    try:
        fixtures = discover_fixtures(fixtures_dir)
    except FileNotFoundError as exc:
        render_prose(
            f"smoke-test fixtures not found: {exc}",
            style="error",
            hint=f"check --fixtures-dir (default: {fixtures_dir})",
        )
        return _USAGE_EXIT

    if reporter_factory is None:
        env = load_env_or_exit(env_path)
        reporter = _build_default_reporter(env, config)
    else:
        reporter = reporter_factory()

    parser_registry = parsers if parsers is not None else default_price_parser_registry()

    started = time.monotonic()
    summary = asyncio.run(
        _run_smoke_test_async(
            fixtures=fixtures,
            parsers=parser_registry,
            data_dir=data_dir,
            reporter=reporter,
            tolerance_eur=config.phase2.reconciliation_tolerance_eur,
            tolerance_pct=config.phase2.reconciliation_tolerance_pct,
        )
    )
    elapsed = time.monotonic() - started

    _render_smoke_test_summary(summary, elapsed, width=width)
    return 5 if summary.any_failed else 0


async def _run_smoke_test_async(
    *,
    fixtures: list[SmokeTestFixture],
    parsers: Mapping[str, PriceParser],
    data_dir: Path,
    reporter: Reporter,
    tolerance_eur: Decimal,
    tolerance_pct: Decimal,
) -> SmokeTestSummary:
    writer = Phase2AuditWriter(db_path_under(data_dir))
    reader = SqlitePhase2StateReader(db_path_under(data_dir))
    try:
        return await run_smoke_test_orchestrator(
            fixtures=fixtures,
            parsers=parsers,
            audit_writer=writer,
            state_reader=reader,
            reporter=reporter,
            tolerance_eur=tolerance_eur,
            tolerance_pct=tolerance_pct,
        )
    finally:
        await writer.close()
        await reader.close()


def _build_default_reporter(env: object, config: object) -> Reporter:
    from salvager.adapters.telegram_bot.surface import TelegramBotSurface
    from salvager.orchestration.degradation_reporter import (
        DegradationReporter,
    )
    from salvager.orchestration.health_state import HealthState

    telegram = TelegramBotSurface(
        bot_token=env.TELEGRAM_BOT_TOKEN,  # type: ignore[attr-defined]
        recipient_chat_id=env.TELEGRAM_CHAT_ID,  # type: ignore[attr-defined]
    )
    return DegradationReporter(
        telegram_surface=telegram,
        health_state=HealthState(),
        dedup_window_seconds=config.observability.degradation_dedup_window_seconds,  # type: ignore[attr-defined]
    )


def _render_smoke_test_summary(summary: SmokeTestSummary, elapsed_s: float, *, width: int) -> None:
    rows: list[dict[str, object]] = []
    for outcome in summary.outcomes:
        rows.append(_smoke_test_row(outcome))

    columns: list[ColumnSpec] = [
        {"key": "Fixture"},
        {"key": "Parsed Price", "align": "right"},
        {"key": "Expected Price", "align": "right"},
        {"key": "Delta", "align": "right"},
        {"key": "Result"},
    ]
    print_table(render_table(rows, columns, width=width), width=width)
    overall = "fail" if summary.any_failed else "pass"
    render_prose(
        f"Overall: {overall} · Smoke test completed in {elapsed_s:.1f}s",
        style="info",
    )


def _smoke_test_row(outcome: FixtureOutcome) -> dict[str, object]:
    parsed = (
        _format_es(outcome.parsed_price_eur)
        if outcome.parsed_price_eur is not None
        else (outcome.parser_error_class or "—")
    )
    delta = _format_es(outcome.result.delta_eur) if outcome.result is not None else "—"
    return {
        "Fixture": outcome.fixture.name,
        "Parsed Price": parsed,
        "Expected Price": _format_es(outcome.fixture.expected_price_eur),
        "Delta": delta,
        "Result": "PASS" if outcome.passed else "FAIL",
    }


# ─────────────────────────────────────────────────────────────────────────
# `phase2 reconcile <receipt-id>` — Story 5.13 read-only re-verification
# ─────────────────────────────────────────────────────────────────────────


def run_reconcile(
    *,
    receipt_or_audit_id: str,
    config_path: Path,
    data_dir: Path,
    output_format: str = "human",
) -> int:
    """Re-run receipt-vs-alert reconciliation on a past transaction.

    Read-only by contract — the AC explicitly forbids mutating state
    from this command (no auto-disable). Exit 0 if reconciled, 5 if a
    mismatch is detected, 1 if the receipt id wasn't found.
    """
    if output_format not in ("human", "json"):
        render_prose(
            f"unknown --format value: {output_format!r}",
            style="error",
            hint="use --format human or --format json",
        )
        return _USAGE_EXIT

    config = load_config(config_path)
    db_path = db_path_under(data_dir)
    if not db_path.exists():
        render_prose(
            f"audit DB not found at {db_path}",
            style="error",
            hint="the daemon hasn't recorded any transactions yet",
        )
        return _USER_CANCELLED_EXIT

    transaction_row, alert_row = _lookup_reconcile_rows(db_path, receipt_or_audit_id)
    if transaction_row is None or alert_row is None:
        render_prose(
            f"receipt id {receipt_or_audit_id!r} not found in audit log",
            style="error",
        )
        return _USER_CANCELLED_EXIT

    listing = Listing.model_validate_json(str(alert_row["listing_json"]))
    evaluation = ListingEvaluation.model_validate_json(str(alert_row["evaluation_json"]))
    snapshot = AlertSnapshot(
        alert_id=str(alert_row["alert_id"]),  # type: ignore[arg-type]
        entry_key=(
            str(alert_row["entry_manufacturer"]),
            str(alert_row["entry_model"]),
            str(alert_row["entry_ref"]),
        ),
        entry_display_name=str(alert_row["entry_display_name"]),
        listing=listing,
        evaluation=evaluation,
        phase=str(alert_row["phase"]),  # type: ignore[arg-type]
        phase2_max_price_eur=(
            Decimal(str(alert_row["phase2_max_price_eur"]))
            if alert_row["phase2_max_price_eur"] is not None
            else None
        ),
        rendered_at=_iso_to_dt(str(alert_row["rendered_at"])),
    )
    transaction = TransactionRecord(
        alert_id=str(transaction_row["alert_id"]),  # type: ignore[arg-type]
        price_paid_eur=Decimal(str(transaction_row["price_paid_eur"])),
        payment_method=str(transaction_row["payment_method"]),  # type: ignore[arg-type]
        receipt_id=str(transaction_row["receipt_id"]),
        screenshot_path=str(transaction_row["screenshot_path"]),
        total_seconds=int(transaction_row["total_seconds"]),
        committed_at=_iso_to_dt(str(transaction_row["committed_at"])),
    )

    result = compute_tolerance(
        snapshot.listing.price_eur,
        transaction.price_paid_eur,
        tolerance_eur=config.phase2.reconciliation_tolerance_eur,
        tolerance_pct=config.phase2.reconciliation_tolerance_pct,
    )

    if output_format == "json":
        payload = {
            "receipt_id": transaction.receipt_id,
            "alert_id": str(snapshot.alert_id),
            "alert_price_eur": str(snapshot.listing.price_eur),
            "receipt_price_eur": str(transaction.price_paid_eur),
            "passed": result.passed,
            "delta_eur": str(result.delta_eur),
            "delta_pct": str(result.delta_pct),
            "tolerance_used": result.tolerance_used,
            "tolerance_value_eur": str(result.tolerance_value),
        }
        print(json.dumps(payload, indent=2))
    else:
        _render_reconcile_human(snapshot, transaction, result)

    return 0 if result.passed else 5


def _lookup_reconcile_rows(
    db_path: Path, identifier: str
) -> tuple[sqlite3.Row | None, sqlite3.Row | None]:
    """Find a transaction by receipt_id (fall back to audit_id if numeric)
    and its matching alert_snapshots row."""
    connection = open_connection(db_path)
    try:
        transaction_row = connection.execute(
            "SELECT * FROM transactions WHERE receipt_id = ?", (identifier,)
        ).fetchone()
        if transaction_row is None and identifier.isdigit():
            transaction_row = connection.execute(
                "SELECT * FROM transactions WHERE audit_id = ?", (int(identifier),)
            ).fetchone()
        if transaction_row is None:
            return None, None
        alert_row = connection.execute(
            "SELECT * FROM alert_snapshots WHERE alert_id = ?",
            (str(transaction_row["alert_id"]),),
        ).fetchone()
        return transaction_row, alert_row
    except sqlite3.Error:
        return None, None
    finally:
        connection.close()


def _render_reconcile_human(
    snapshot: AlertSnapshot,
    transaction: TransactionRecord,
    result: ReconciliationResult,
) -> None:
    if result.passed:
        render_prose(
            f"Reconciliation PASSED for receipt {transaction.receipt_id}",
            style="success",
        )
    else:
        render_prose(
            f"Reconciliation FAILED for receipt {transaction.receipt_id}",
            style="error",
        )
    rows: list[dict[str, object]] = [
        {"Field": "Alert price", "Value": _format_es(snapshot.listing.price_eur)},
        {"Field": "Receipt price", "Value": _format_es(transaction.price_paid_eur)},
        {"Field": "Delta", "Value": _format_es(result.delta_eur)},
        {
            "Field": "Tolerance used",
            "Value": f"{result.tolerance_used} ({_format_es(result.tolerance_value)})",
        },
    ]
    print_table(
        render_table(
            rows,
            [{"key": "Field"}, {"key": "Value", "align": "right"}],
            width=60,
        ),
        width=60,
    )


def _iso_to_dt(value: str) -> datetime:
    """Decode an ISO 8601 stamp, accepting the daemon's trailing ``Z``."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
