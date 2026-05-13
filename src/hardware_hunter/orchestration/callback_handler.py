"""Phase 1 Telegram callback handler — Story 3.13.

Wires inbound :class:`CallbackEvent` taps to the three Phase 1 effects:

  1. Append a row to the ``callbacks`` audit table (NFR-S4 append-only).
  2. For ``snooze``, mutate ``wishlist_runtime_state.snooze_until`` so
     the poll loop's snooze filter suppresses further alerts for that
     ``entry_key`` until the window expires (default 24h).
  3. Replace the inline keyboard with the locked acknowledgment row
     ``[✓ visto] / [✓ saltado] / [✓ pospuesto 24h]`` (UX-DR12).

The handler is intentionally inert on unknown verbs — including
``buy`` at v0.x — and on malformed ``callback_data``: it logs the
event at ``warn`` and returns without editing the keyboard, so the
operator can retry on a real handler in Phase 2.

The handler is the **orchestration seam**: it depends only on the
:class:`Store` and :class:`TelegramSurface` ports, never on a
specific adapter. The poll-loop orchestrator (Story 3.14) will
register an instance of :class:`CallbackDispatcher` with the live
:class:`TelegramSurface` via ``listen_callbacks``.
"""

from __future__ import annotations

import uuid as uuid_module
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

from hardware_hunter.domain.alert import CallbackEvent, InlineButton
from hardware_hunter.domain.audit import CallbackAudit
from hardware_hunter.interfaces.store import Store
from hardware_hunter.interfaces.telegram_surface import TelegramSurface
from hardware_hunter.observability.logging import get_logger

#: Phase 1 verbs this handler dispatches. ``buy`` is intentionally
#: absent — Phase 2 callbacks landing in v0.x are logged as unknown
#: and ignored (AR24 guardrail at the surface layer too).
HANDLED_VERBS: Final[frozenset[str]] = frozenset({"view", "skip", "snooze"})

#: Acknowledgment-row labels per UX-DR12. Spanish past-participles
#: match BUTTON_LABELS' present-tense verbs (Ver → visto, Saltar →
#: saltado, Posponer → pospuesto).
ACK_LABELS: Final[dict[str, str]] = {
    "view": "✓ visto",
    "skip": "✓ saltado",
    "snooze": "✓ pospuesto 24h",
}

#: Default snooze window. The orchestrator can override via
#: ``snooze_hours`` to wire ``config.yaml > snooze.default_hours``.
DEFAULT_SNOOZE_HOURS: Final[int] = 24


def _utc_now() -> datetime:
    return datetime.now(UTC)


class CallbackDispatcher:
    """Routes Phase 1 callbacks to audit + state + ack-row edit.

    The dispatcher is owned by orchestration and stateless across
    callbacks; multiple in-flight taps are safe to interleave because
    every effect is serialized inside the :class:`Store`
    implementation's write lock.
    """

    def __init__(
        self,
        *,
        store: Store,
        surface: TelegramSurface,
        snooze_hours: int = DEFAULT_SNOOZE_HOURS,
        clock: Callable[[], datetime] = _utc_now,
        new_audit_id: Callable[[], UUID] = uuid_module.uuid4,
    ) -> None:
        self._store = store
        self._surface = surface
        self._snooze_hours = snooze_hours
        self._clock = clock
        self._new_audit_id = new_audit_id
        self._log = get_logger("orchestration.callback_handler")

    async def handle(self, event: CallbackEvent) -> None:
        """Process a single callback tap end-to-end.

        Ordering: audit row first, then state mutation (snooze only),
        then keyboard edit. The keyboard edit is last so a delivery
        failure there doesn't lose the audit trail — the operator
        sees the tap landed in ``audit show`` even if the visual
        acknowledgment doesn't arrive.
        """
        if event.verb not in HANDLED_VERBS:
            self._log.warning(
                "callback_unknown_verb",
                extra={
                    "verb": event.verb,
                    "callback_data": event.callback_data,
                },
            )
            return

        try:
            alert_id = _alert_id_from_callback_data(event.callback_data)
        except ValueError:
            self._log.warning(
                "callback_malformed_callback_data",
                extra={"callback_data": event.callback_data},
            )
            return

        now = self._clock()
        await self._store.record_callback(
            CallbackAudit(
                audit_id=self._new_audit_id(),
                alert_id=alert_id,
                telegram_message_id=event.message_id,
                callback_data=event.callback_data,
                verb=event.verb,
                chat_id=event.chat_id,
                occurred_at=now,
            )
        )

        if event.verb == "snooze":
            await self._apply_snooze(alert_id, now)

        await self._surface.edit_keyboard(
            event.message_id,
            _acknowledgment_keyboard(event.verb, alert_id),
        )

    async def _apply_snooze(self, alert_id: UUID, now: datetime) -> None:
        snapshot = await self._store.get_alert_snapshot_by_alert_id(alert_id)
        if snapshot is None:
            # The alert pre-dates the current DB (operator tapped an
            # old message after a wipe/restore). Audit still records
            # the tap; the visual ack still shows. Just no state.
            self._log.warning(
                "callback_snapshot_missing",
                extra={"alert_id": str(alert_id)},
            )
            return

        until = now + timedelta(hours=self._snooze_hours)
        await self._store.set_snooze(snapshot.entry_key, until)
        self._log.info(
            "entry_snoozed",
            extra={
                "entry_manufacturer": snapshot.entry_key[0],
                "entry_model": snapshot.entry_key[1],
                "entry_ref": snapshot.entry_key[2],
                "snooze_until": until.isoformat(),
                "snooze_hours": self._snooze_hours,
            },
        )


def _alert_id_from_callback_data(callback_data: str) -> UUID:
    """Extract the UUID from a ``<surface>:<verb>:<id>`` callback_data.

    Raises :class:`ValueError` when the shape is wrong or the id
    segment is not a valid UUID. The Telegram surface
    (``TelegramBotSurface.parse_callback``) already drops malformed
    data — this is defense in depth so a faulty caller can't crash
    the dispatcher.
    """
    parts = callback_data.split(":")
    if len(parts) != 3:
        raise ValueError(f"expected 3 segments, got {len(parts)}")
    return UUID(parts[2])


def _acknowledgment_keyboard(verb: str, alert_id: UUID) -> list[list[InlineButton]]:
    """Build the single-row acknowledgment keyboard (UX-DR12).

    ``callback_data`` uses the surface-locked ``listing:ack:<id>``
    form. ``ack`` is deliberately outside the
    :class:`TelegramBotSurface` known-verb set, so any stray future
    tap is dropped silently at the surface layer — the row is
    visually a status badge, not a button.
    """
    return [
        [
            InlineButton(
                text=ACK_LABELS[verb],
                callback_data=f"listing:ack:{alert_id}",
            )
        ]
    ]


__all__ = [
    "ACK_LABELS",
    "DEFAULT_SNOOZE_HOURS",
    "HANDLED_VERBS",
    "CallbackDispatcher",
]
