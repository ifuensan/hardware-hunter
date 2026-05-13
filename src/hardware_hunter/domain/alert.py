"""Alert + render-output schema — Story 3.1.

Three types live here:

  - :class:`AlertSnapshot` — the immutable record of what was alerted
    (entry x listing x evaluation). Persisted to SQLite ``alert_snapshots``
    so the callback handler can look up the originating context when
    an operator taps a button hours later.
  - :class:`RenderedAlert` — the data shape every renderer produces
    and the :class:`TelegramSurface` adapter consumes.
  - :class:`InlineButton` — one button on a Telegram inline keyboard
    row. ``callback_data`` follows the locked
    ``<surface>:<verb>:<id>`` format with the 64-byte Telegram cap.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hardware_hunter.domain.evaluation import ListingEvaluation
from hardware_hunter.domain.listing import Listing

Phase = Literal["phase1", "phase2"]
ParseMode = Literal["MarkdownV2"]

# Telegram caps inline-button callback_data at 64 bytes. The locked format
# is `<surface>:<verb>:<id>` per CALLBACK_DATA_FORMAT in the UX spec.
_CALLBACK_DATA_MAX_BYTES = 64
_CALLBACK_DATA_RE = re.compile(r"^[a-z0-9_]+:[a-z0-9_]+:[A-Za-z0-9_\-]+$")

# ─────────────────────────────────────────────────────────────────────────
# Locked UX tokens (UX-DR3 / UX-DR4 / UX-DR5)
# ─────────────────────────────────────────────────────────────────────────

#: Per-surface severity emoji. PRD amendment to grow.
SEVERITY_TOKENS: Final[dict[str, str]] = {
    "operational_warn": "⚠️ ",
    "operational_info": "ℹ️ ",  # noqa: RUF001 — the info glyph is operator-facing
    "phase1_listing": "📦",
    "phase2_listing": "🟢",
    "phase2_buy_success": "✅",
    "phase2_buy_failure": "🚫",
}

#: Inline-keyboard button labels (Spanish per UX-DR27). PRD amendment to grow.
BUTTON_LABELS: Final[dict[str, str]] = {
    "view": "👁 Ver",
    "skip_phase1": "🙅 Saltar",
    "snooze": "😴 Posponer 24h",
    "buy": "✅ Comprar",
    "skip_phase2": "❌ Saltar",
}

#: Locked callback_data format. Max 64 bytes per Telegram.
CALLBACK_DATA_FORMAT: Final[str] = "<surface>:<verb>:<id>"

# Characters MarkdownV2 reserves and that user content must escape.
# Order matters for the regex — backslash MUST be first or it would
# double-escape itself.
_MD_V2_RESERVED = r"\_*[]()~`>#+-=|{}.!"
_MD_V2_RE = re.compile(r"([\\_*\[\]()~`>#+\-=|{}.!])")


class InlineButton(BaseModel):
    """One inline-keyboard button on a Telegram alert.

    ``callback_data`` is the value Telegram sends back to the bot when
    the operator taps the button. The format and byte cap are
    contract — :class:`TelegramSurface` does not re-validate.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    callback_data: str

    @field_validator("callback_data")
    @classmethod
    def _enforce_callback_format(cls, value: str) -> str:
        if len(value.encode("utf-8")) > _CALLBACK_DATA_MAX_BYTES:
            raise ValueError(
                f"callback_data exceeds Telegram's {_CALLBACK_DATA_MAX_BYTES}-byte limit"
            )
        if not _CALLBACK_DATA_RE.fullmatch(value):
            raise ValueError(
                "callback_data must match <surface>:<verb>:<id> "
                "(lowercase surface/verb, alphanumeric id)"
            )
        return value


class RenderedAlert(BaseModel):
    """Output of every renderer; input to :class:`TelegramSurface.send`.

    ``photo_url`` is None for non-listing alerts (operational warnings,
    smoke-test results). ``inline_keyboard`` is None when the alert is
    informational (no buttons).
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    parse_mode: ParseMode = "MarkdownV2"
    photo_url: str | None = None
    inline_keyboard: list[list[InlineButton]] | None = None


CallbackVerb = Literal["view", "skip", "snooze", "buy"]


class CallbackEvent(BaseModel):
    """One inline-button tap received from Telegram.

    The :class:`TelegramSurface` adapter parses Telegram's
    ``CallbackQuery`` into this typed shape and hands it to the poll
    loop's registered handler. ``callback_data`` is the raw
    ``<surface>:<verb>:<id>`` value; ``verb`` is the parsed verb for
    easy dispatch.
    """

    model_config = ConfigDict(extra="forbid")

    callback_query_id: str = Field(min_length=1)
    chat_id: int
    message_id: int
    callback_data: str
    verb: CallbackVerb


class AlertSnapshot(BaseModel):
    """The immutable record of one alert dispatched to the operator.

    Persisted to ``alert_snapshots`` so the callback handler can replay
    the originating context (which entry, which listing, which
    evaluation) when the operator taps a button. Phase 2 adds
    ``phase2_max_price_eur`` for the autonomous-buy gate.
    """

    model_config = ConfigDict(extra="forbid")

    alert_id: UUID
    entry_key: tuple[str, str, str]
    entry_display_name: str = Field(min_length=1)
    listing: Listing
    evaluation: ListingEvaluation
    phase: Phase
    phase2_max_price_eur: Decimal | None = None
    rendered_at: datetime


# ─────────────────────────────────────────────────────────────────────────
# Rendering helpers — Story 3.11
# ─────────────────────────────────────────────────────────────────────────


def escape_markdown_v2(text: str) -> str:
    """Escape every MarkdownV2-reserved character in ``text``.

    Telegram's MarkdownV2 reserves ``_*[]()~`>#+-=|{}.!`` (plus
    backslash). User-supplied content (titles, descriptions, LLM
    takes, locations) MUST pass through this before being interpolated
    into a template — otherwise a stray asterisk in a listing title
    could break the markup or open an injection vector.
    """
    return _MD_V2_RE.sub(r"\\\1", text)


def _format_price_es(amount: Decimal) -> str:
    """Format a EUR Decimal in es-ES style — ``1.234,56 €``."""
    quantized = amount.quantize(Decimal("0.01"))
    # Python's built-in locale module is process-global and unreliable
    # across environments; we hand-format to keep snapshot tests stable
    # regardless of the host's locale.
    integer_part, _, decimal_part = str(quantized).partition(".")
    sign = ""
    if integer_part.startswith("-"):
        sign = "-"
        integer_part = integer_part[1:]
    # Insert dot every three digits from the right.
    chunks: list[str] = []
    while len(integer_part) > 3:
        chunks.append(integer_part[-3:])
        integer_part = integer_part[:-3]
    chunks.append(integer_part)
    int_grouped = ".".join(reversed(chunks))
    return f"{sign}{int_grouped},{decimal_part} €"


def _phase1_button_row(alert_id: str) -> list[InlineButton]:
    """The Phase 1 button row: Ver · Saltar · Posponer 24h (UX-DR4).

    ``callback_data`` carries the AlertSnapshot's UUID (``alert_id``)
    rather than the raw ``listing_id`` because eBay listing IDs
    contain ``|`` characters that aren't valid callback_data and
    because the callbacks table indexes on ``alert_id`` regardless.
    The callback handler resolves the originating listing by reading
    the alert_snapshot row.
    """
    return [
        InlineButton(text=BUTTON_LABELS["view"], callback_data=f"listing:view:{alert_id}"),
        InlineButton(text=BUTTON_LABELS["skip_phase1"], callback_data=f"listing:skip:{alert_id}"),
        InlineButton(text=BUTTON_LABELS["snooze"], callback_data=f"listing:snooze:{alert_id}"),
    ]


def render_phase1_listing_alert(snapshot: AlertSnapshot) -> RenderedAlert:
    """Render a Phase 1 listing alert (Direction A + Direction E hybrid).

    Anatomy (direct listing):
      1. ``{📦} *<entry_display_name>* — *<price>*``
      2. ``📍 <location> · <marketplace>``
      3. ``_<one_line_take>_``
      4. ``🔍 Confidence: <low|medium|high>``

    When ``snapshot.evaluation.is_container == True``, two indented
    rows are inserted between row 2 and row 3:
      - ``  ↪︎ Wrapper: <wrapper_text>``
      - ``  ↪︎ Extracted: <extracted_text>``

    Every user-supplied substring passes through
    :func:`escape_markdown_v2` so a listing title with an asterisk
    can't break the markup or open an injection vector.

    The output is locked at v1 per FR22; snapshot tests in
    ``test_alert_renderer.py`` fail the build on any drift.
    """
    listing = snapshot.listing
    evaluation = snapshot.evaluation

    severity = SEVERITY_TOKENS["phase1_listing"]
    name = escape_markdown_v2(snapshot.entry_display_name)
    price = escape_markdown_v2(_format_price_es(listing.price_eur))
    location = escape_markdown_v2(listing.location or "—")
    marketplace = escape_markdown_v2(listing.marketplace.capitalize())
    take = escape_markdown_v2(evaluation.one_line_take)
    confidence = escape_markdown_v2(evaluation.confidence)

    rows: list[str] = [
        f"{severity} *{name}* — *{price}*",
        f"📍 {location} · {marketplace}",
    ]

    if evaluation.is_container:
        wrapper = escape_markdown_v2(evaluation.wrapper_text or "—")
        extracted = escape_markdown_v2(evaluation.extracted_text or "—")
        rows.append(f"  ↪︎ Wrapper: {wrapper}")
        rows.append(f"  ↪︎ Extracted: {extracted}")

    rows.append(f"_{take}_")
    rows.append(f"🔍 Confidence: {confidence}")

    photo_url = listing.photo_urls[0] if listing.photo_urls else None

    return RenderedAlert(
        text="\n".join(rows),
        parse_mode="MarkdownV2",
        photo_url=photo_url,
        inline_keyboard=[_phase1_button_row(str(snapshot.alert_id))],
    )
