"""Variant → :class:`RenderedAlert` registry — Story 5.17 release-audit.

One closed map: every release-gate variant name (37 entries at v1.0)
to a zero-arg builder that returns a :class:`RenderedAlert`. The
fixture data mirrors what the snapshot tests use, so the dispatched
Telegram message and the file under
``docs/release-audits/v1.0/reference-text/<variant>.txt`` are
byte-for-byte the same MarkdownV2 string.

Why a separate module:

  - keeps :mod:`cli.commands.dev_cmd` thin (CLI wiring only) so the
    rendering is testable without a Typer app + Telegram surface;
  - lets the property tests in ``tests/unit/test_dev_emit_alert.py``
    iterate the closed enumeration and verify every renderer runs
    cleanly + produces a non-empty MarkdownV2 body.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from hardware_hunter.domain.alert import (
    AlertSnapshot,
    EventName,
    RenderedAlert,
    Severity,
    render_operational_alert,
    render_phase1_listing_alert,
    render_phase2_buy_failure,
    render_phase2_buy_success,
    render_phase2_listing_alert,
)
from hardware_hunter.domain.errors import BuyFailureReason
from hardware_hunter.domain.evaluation import ListingEvaluation
from hardware_hunter.domain.listing import Listing
from hardware_hunter.domain.phase2_audit import TransactionRecord

_FIXED_ALERT_ID = UUID("12345678-1234-1234-1234-123456789abc")
_FIXED_TS = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_PHASE2_MAX = Decimal("60.00")
_ENTRY_KEY = ("Western Digital", "WD Red Plus 4TB", "WD40EFPX")
_ENTRY_DISPLAY = "WD Red Plus 4TB (WD40EFPX)"


# ─────────────────────────────────────────────────────────────────────────
# Listing fixtures (shared between Phase 1 + Phase 2)
# ─────────────────────────────────────────────────────────────────────────


def _listing(**overrides: Any) -> Listing:
    base: dict[str, Any] = {
        "listing_id": "abc123",
        "marketplace": "wallapop",
        "url": "https://es.wallapop.com/item/abc123",
        "title": "WD Red Plus 4TB",
        "description": "Como nuevo, en caja.",
        "price_eur": Decimal("55.00"),
        "location": "Madrid",
        "photo_urls": ["https://cdn/photo.jpg"],
        "fetched_at": _FIXED_TS,
    }
    base.update(overrides)
    return Listing(**base)


def _evaluation(**overrides: Any) -> ListingEvaluation:
    base: dict[str, Any] = {
        "listing_id": "abc123",
        "entry_key": _ENTRY_KEY,
        "confidence": "high",
        "one_line_take": "WD Red Plus 4TB at 55€ — strong match.",
        "is_container": False,
        "evaluated_at": _FIXED_TS,
    }
    base.update(overrides)
    return ListingEvaluation(**base)


def _snapshot(
    *,
    phase: str = "phase1",
    listing_overrides: dict[str, Any] | None = None,
    evaluation_overrides: dict[str, Any] | None = None,
) -> AlertSnapshot:
    return AlertSnapshot(
        alert_id=_FIXED_ALERT_ID,
        entry_key=_ENTRY_KEY,
        entry_display_name=_ENTRY_DISPLAY,
        listing=_listing(**(listing_overrides or {})),
        evaluation=_evaluation(**(evaluation_overrides or {})),
        phase=phase,  # type: ignore[arg-type]
        phase2_max_price_eur=_PHASE2_MAX if phase == "phase2" else None,
        rendered_at=_FIXED_TS,
    )


# ─────────────────────────────────────────────────────────────────────────
# Phase 1 + Phase 2 listing builders
# ─────────────────────────────────────────────────────────────────────────


def _phase1_direct() -> RenderedAlert:
    return render_phase1_listing_alert(_snapshot())


def _phase1_container() -> RenderedAlert:
    return render_phase1_listing_alert(
        _snapshot(
            evaluation_overrides={
                "is_container": True,
                "wrapper_text": "Pack 4x HDD",
                "extracted_text": "WD Red Plus 4TB inside",
            }
        )
    )


def _phase1_missing_photo() -> RenderedAlert:
    return render_phase1_listing_alert(_snapshot(listing_overrides={"photo_urls": []}))


def _phase2_direct() -> RenderedAlert:
    return render_phase2_listing_alert(_snapshot(phase="phase2"), _PHASE2_MAX)


def _phase2_container() -> RenderedAlert:
    return render_phase2_listing_alert(
        _snapshot(
            phase="phase2",
            evaluation_overrides={
                "is_container": True,
                "wrapper_text": "Pack 4x HDD",
                "extracted_text": "WD Red Plus 4TB inside",
            },
        ),
        _PHASE2_MAX,
    )


def _phase2_missing_photo() -> RenderedAlert:
    return render_phase2_listing_alert(
        _snapshot(phase="phase2", listing_overrides={"photo_urls": []}),
        _PHASE2_MAX,
    )


# ─────────────────────────────────────────────────────────────────────────
# Phase 2 buy success + failure builders
# ─────────────────────────────────────────────────────────────────────────


def _buy_success() -> RenderedAlert:
    return render_phase2_buy_success(
        TransactionRecord(
            alert_id=_FIXED_ALERT_ID,
            price_paid_eur=Decimal("55.00"),
            payment_method="wallapop_pay",
            receipt_id="WP-2026-0001",
            screenshot_path="/app/data/screenshots/WP-2026-0001.png",
            total_seconds=42,
            committed_at=_FIXED_TS,
        ),
        entry_display_name=_ENTRY_DISPLAY,
        audit_id=42,
    )


_GENERIC_FAILURE_CTX: Final[dict[str, Any]] = {
    "api_price": Decimal("53.00"),
    "html_price": Decimal("0.53"),
    "tolerance_eur": Decimal("1.00"),
    "consecutive_failures": 3,
    "threshold": 3,
    "missing": ["buy_button"],
    "error_class": "TinyFishUnavailable",
    "transaction_id": 42,
    "receipt_id": "WP-2026-0001",
}


def _make_buy_failure(reason: BuyFailureReason) -> Callable[[], RenderedAlert]:
    def _build() -> RenderedAlert:
        return render_phase2_buy_failure(
            reason, entry_display_name=_ENTRY_DISPLAY, ctx=_GENERIC_FAILURE_CTX
        )

    _build.__name__ = f"_buy_failure_{reason.value}"
    return _build


# ─────────────────────────────────────────────────────────────────────────
# Operational EventName builders
# ─────────────────────────────────────────────────────────────────────────


_OPERATIONAL_FIXTURES: Final[dict[EventName, tuple[Severity, dict[str, Any]]]] = {
    EventName.daemon_started: ("info", {"version": "0.1.0", "jobs": "wallapop_poll, ebay_poll"}),
    EventName.daemon_stopped: ("info", {"reason": "SIGTERM"}),
    EventName.wallapop_session_expired: ("info", {}),
    EventName.wallapop_session_renewed: ("info", {}),
    EventName.wallapop_api_degraded: ("info", {"error_class": "WallapopApiError"}),
    EventName.wallapop_both_paths_down: (
        "warn",
        {"consecutive_failures": 3, "last_error_class": "TinyFishUnavailable"},
    ),
    EventName.tinyfish_fallback_active: ("info", {}),
    EventName.tinyfish_fallback_recovered: ("info", {}),
    EventName.ebay_token_refresh_failed: ("warn", {}),
    EventName.ebay_quota_breach: ("info", {"used": 5000, "budget": 5000}),
    EventName.llm_provider_rate_limited: ("info", {"provider": "gemini-flash"}),
    EventName.entry_snoozed: (
        "info",
        {"entry_display_name": _ENTRY_DISPLAY, "snooze_until": "2026-05-17T12:00:00Z"},
    ),
    EventName.poll_cycle_error: (
        "warn",
        {"error_class": "RuntimeError", "marketplace": "wallapop"},
    ),
    EventName.circuit_open: (
        "warn",
        {"consecutive_failures": 3, "threshold": 3, "last_affected_entry": _ENTRY_DISPLAY},
    ),
    EventName.smoke_test_failed: (
        "warn",
        {
            "fixture_name": "wallapop_html_comma_vs_dot",
            "parsed_price": "0.53",
            "expected_price": "53.00",
            "delta_eur": "52.47",
            "parser_error_class": "—",
        },
    ),
    EventName.smoke_test_recovered: ("info", {}),
    EventName.phase2_disabled: (
        "warn",
        {"reason": "receipt_mismatch", "last_affected_entry": _ENTRY_DISPLAY},
    ),
    EventName.phase2_re_enabled: ("info", {"entry": _ENTRY_DISPLAY}),
    EventName.phase2_buy_callback_received: (
        "info",
        {"entry": _ENTRY_DISPLAY, "alert_id": str(_FIXED_ALERT_ID)},
    ),
    EventName.phase2_screenshot_missing: (
        "warn",
        {"receipt_id": "WP-2026-0001", "listing_id": "abc123"},
    ),
    EventName.phase2_buy_completion_slow: (
        "info",
        {"entry": _ENTRY_DISPLAY, "elapsed_seconds": 87, "budget_seconds": 60},
    ),
    EventName.buy_orchestrator_error: (
        "warn",
        {"error_class": "TinyFishSessionLost", "alert_id": str(_FIXED_ALERT_ID)},
    ),
}


def _make_operational(event: EventName) -> Callable[[], RenderedAlert]:
    severity, ctx = _OPERATIONAL_FIXTURES[event]

    def _build() -> RenderedAlert:
        return render_operational_alert(severity, event, ctx)

    _build.__name__ = f"_operational_{event.value}"
    return _build


# ─────────────────────────────────────────────────────────────────────────
# Closed registry — the audit catalog
# ─────────────────────────────────────────────────────────────────────────


def _build_registry() -> dict[str, Callable[[], RenderedAlert]]:
    registry: dict[str, Callable[[], RenderedAlert]] = {
        "phase1_listing_direct": _phase1_direct,
        "phase1_listing_container": _phase1_container,
        "phase1_listing_missing_photo": _phase1_missing_photo,
        "phase2_listing_direct": _phase2_direct,
        "phase2_listing_container": _phase2_container,
        "phase2_listing_missing_photo": _phase2_missing_photo,
        "buy_success": _buy_success,
    }
    for reason in BuyFailureReason:
        registry[f"buy_failure_{reason.value}"] = _make_buy_failure(reason)
    for event in _OPERATIONAL_FIXTURES:
        registry[event.value] = _make_operational(event)
    return registry


#: The audit catalog — name → zero-arg :class:`RenderedAlert` builder.
VARIANT_REGISTRY: Final[dict[str, Callable[[], RenderedAlert]]] = _build_registry()


def build_rendered_variant(name: str) -> RenderedAlert:
    """Resolve a variant name to its rendered alert. Raises
    :class:`KeyError` if the name is not in the registry — callers
    (the CLI) should pre-check membership and surface a friendly error."""
    return VARIANT_REGISTRY[name]()


__all__ = ["VARIANT_REGISTRY", "build_rendered_variant"]
