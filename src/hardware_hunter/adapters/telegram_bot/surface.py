"""Telegram bot :class:`TelegramSurface` — Story 3.12.

Wraps ``python-telegram-bot`` with the retry semantics + chat-ID
allowlist this project requires.

Retry policy (NFR-I6)
---------------------
Transient failures (network errors, timeouts, HTTP 5xx, RetryAfter)
are retried with exponential backoff: 3 attempts total, default delays
of 5s and 15s between them. After the third failure the surface
raises :class:`TelegramDeliveryFailed`; the orchestration layer
swallows the error and continues — delivery failure must NOT block
polling.

Non-retryable failures (HTTP 4xx — invalid token, chat not found,
bot kicked) raise :class:`TelegramConfigError` immediately so the
operator gets a loud signal instead of silent retry-storms.

Chat-ID allowlist (AR20)
------------------------
``parse_callback_query`` drops anything arriving from a chat ID other
than the configured ``recipient_chat_id``. The drop is silent — no
visible reply, no log spam beyond a single ``debug`` line. The bot
talks to one operator; everything else is noise.

Test seam
---------
Both the bot and the ``sleep`` function are dependency-injected so
unit tests can run fast (sleep no-op) against a fake bot that
records calls and synthesizes failures.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, cast, runtime_checkable

from pydantic import SecretStr

from hardware_hunter.domain.alert import (
    CallbackEvent,
    CallbackVerb,
    InlineButton,
    RenderedAlert,
)
from hardware_hunter.domain.errors import (
    TelegramConfigError,
    TelegramDeliveryFailed,
)
from hardware_hunter.interfaces.telegram_surface import (
    CallbackHandler,
    TelegramSurface,
)
from hardware_hunter.observability.logging import get_logger

#: Pause-between-retries in seconds. Defaults give ~3 attempts in ~20s.
DEFAULT_RETRY_DELAYS: tuple[float, ...] = (5.0, 15.0)

_KNOWN_VERBS: frozenset[str] = frozenset({"view", "skip", "snooze", "buy"})


@runtime_checkable
class TelegramBotProtocol(Protocol):
    """The slice of ``telegram.Bot`` that this adapter actually calls.

    A Protocol so tests can pass an in-memory fake without dragging
    the real Bot class. The signatures match python-telegram-bot's
    async API.
    """

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        parse_mode: str | None = ...,
        reply_markup: Any = ...,
    ) -> Any: ...

    async def send_photo(
        self,
        chat_id: int,
        photo: str,
        *,
        caption: str | None = ...,
        parse_mode: str | None = ...,
        reply_markup: Any = ...,
    ) -> Any: ...

    async def edit_message_reply_markup(
        self,
        chat_id: int,
        message_id: int,
        *,
        reply_markup: Any = ...,
    ) -> Any: ...


class TelegramBotSurface(TelegramSurface):
    """``TelegramSurface`` backed by ``python-telegram-bot``."""

    def __init__(
        self,
        bot_token: SecretStr,
        recipient_chat_id: int,
        *,
        bot: TelegramBotProtocol | None = None,
        retry_delays: tuple[float, ...] = DEFAULT_RETRY_DELAYS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._bot_token = bot_token
        self._recipient_chat_id = recipient_chat_id
        self._bot: TelegramBotProtocol = bot if bot is not None else _build_default_bot(bot_token)
        self._retry_delays = retry_delays
        self._sleep = sleep
        self._log = get_logger("adapter.telegram_bot")

    # ─────────────────────────────────────────────────────────────────
    # TelegramSurface — send / edit_keyboard / listen_callbacks
    # ─────────────────────────────────────────────────────────────────

    async def send(self, rendered: RenderedAlert) -> int:
        """Send a rendered alert; return Telegram's ``message_id``.

        Retries transient failures with exponential backoff. 4xx
        (config) failures bail out immediately.
        """
        attempt = 0
        started = time.perf_counter()
        while True:
            try:
                message = await self._invoke_send(rendered)
            except _RetryableTelegramError as exc:
                if attempt >= len(self._retry_delays):
                    self._log.error(
                        "telegram_send_failed",
                        extra={
                            "error_class": exc.original.__class__.__name__,
                            "attempts": attempt + 1,
                        },
                    )
                    raise TelegramDeliveryFailed(
                        f"send failed after {attempt + 1} attempts: {exc.original}"
                    ) from exc.original
                delay = self._retry_delays[attempt]
                self._log.warning(
                    "telegram_send_retry",
                    extra={
                        "error_class": exc.original.__class__.__name__,
                        "attempt": attempt + 1,
                        "delay_s": delay,
                    },
                )
                await self._sleep(delay)
                attempt += 1
                continue
            except _NonRetryableTelegramError as exc:
                self._log.error(
                    "telegram_config_error",
                    extra={"error_class": exc.original.__class__.__name__},
                )
                raise TelegramConfigError(str(exc.original)) from exc.original

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            self._log.info(
                "telegram_alert_sent",
                extra={
                    "latency_ms": elapsed_ms,
                    "message_id": message.message_id,
                    "attempts": attempt + 1,
                },
            )
            return int(message.message_id)

    async def edit_keyboard(
        self,
        message_id: int,
        keyboard: list[list[InlineButton]] | None,
    ) -> None:
        try:
            await self._bot.edit_message_reply_markup(
                self._recipient_chat_id,
                message_id,
                reply_markup=_to_telegram_keyboard(keyboard),
            )
        except Exception as exc:
            if _is_retryable(exc):
                self._log.warning(
                    "telegram_edit_failed",
                    extra={"error_class": exc.__class__.__name__},
                )
                raise TelegramDeliveryFailed(str(exc)) from exc
            self._log.error(
                "telegram_edit_config_error",
                extra={"error_class": exc.__class__.__name__},
            )
            raise TelegramConfigError(str(exc)) from exc

    async def listen_callbacks(self, handler: CallbackHandler) -> None:
        """Production loop wiring lands when the orchestration story
        composes this with the daemon's main loop (Story 3.14). At v0.x
        of Story 3.12 the parser is exposed via :meth:`parse_callback`
        for unit testing; the application-level dispatcher will call
        it on each inbound ``telegram.CallbackQuery``."""
        _ = handler
        raise NotImplementedError(
            "listen_callbacks is wired in Story 3.14 (poll-loop orchestrator). "
            "Use parse_callback() to parse a single CallbackQuery in the meantime."
        )

    # ─────────────────────────────────────────────────────────────────
    # Test affordances + production helper for the future orchestrator
    # ─────────────────────────────────────────────────────────────────

    def parse_callback(
        self,
        *,
        chat_id: int,
        message_id: int,
        callback_query_id: str,
        callback_data: str,
    ) -> CallbackEvent | None:
        """Parse one inbound Telegram callback into a typed event.

        Returns None when the chat ID is not the configured operator
        (AR20 chat-ID allowlist). The drop is silent at the operator
        surface; a single ``debug`` log line records the event.

        Malformed callback_data (wrong shape, unknown verb) also
        returns None — the bot stays well-behaved when third parties
        guess at our format.
        """
        if chat_id != self._recipient_chat_id:
            self._log.debug(
                "telegram_inbound_unknown_chat",
                extra={"chat_id": chat_id, "expected": self._recipient_chat_id},
            )
            return None

        parts = callback_data.split(":")
        if len(parts) != 3:
            self._log.debug(
                "telegram_inbound_malformed_callback",
                extra={"callback_data": callback_data},
            )
            return None

        _surface, verb, _alert_id = parts
        if verb not in _KNOWN_VERBS:
            self._log.debug(
                "telegram_inbound_unknown_verb",
                extra={"verb": verb},
            )
            return None

        return CallbackEvent(
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            message_id=message_id,
            callback_data=callback_data,
            verb=cast(CallbackVerb, verb),
        )

    # ─────────────────────────────────────────────────────────────────
    # Internals
    # ─────────────────────────────────────────────────────────────────

    async def _invoke_send(self, rendered: RenderedAlert) -> Any:
        markup = _to_telegram_keyboard(rendered.inline_keyboard)
        try:
            if rendered.photo_url is not None:
                return await self._bot.send_photo(
                    self._recipient_chat_id,
                    photo=rendered.photo_url,
                    caption=rendered.text,
                    parse_mode=rendered.parse_mode,
                    reply_markup=markup,
                )
            return await self._bot.send_message(
                self._recipient_chat_id,
                text=rendered.text,
                parse_mode=rendered.parse_mode,
                reply_markup=markup,
            )
        except Exception as exc:
            if _is_retryable(exc):
                raise _RetryableTelegramError(exc) from exc
            raise _NonRetryableTelegramError(exc) from exc


# ─────────────────────────────────────────────────────────────────────────
# Error classification + keyboard conversion
# ─────────────────────────────────────────────────────────────────────────


class _RetryableTelegramError(Exception):
    """Internal wrapper marking a Telegram exception as retry-worthy."""

    def __init__(self, original: BaseException) -> None:
        self.original = original
        super().__init__(str(original))


class _NonRetryableTelegramError(Exception):
    """Internal wrapper marking a Telegram exception as a config failure."""

    def __init__(self, original: BaseException) -> None:
        self.original = original
        super().__init__(str(original))


_RETRYABLE_CLASS_NAMES: frozenset[str] = frozenset(
    {
        "NetworkError",
        "TimedOut",
        "RetryAfter",
    }
)


def _is_retryable(exc: BaseException) -> bool:
    """Decide whether an exception from ``telegram.error`` is retry-worthy.

    We inspect the class name (rather than catching specific types) so
    the adapter doesn't have to import ``telegram.error.*`` at module
    scope — keeps the import surface small and tests fast.
    """
    cls_name = exc.__class__.__name__
    return cls_name in _RETRYABLE_CLASS_NAMES


def _to_telegram_keyboard(
    keyboard: list[list[InlineButton]] | None,
) -> Any:
    """Convert our domain :class:`InlineButton` rows into the python-
    telegram-bot ``InlineKeyboardMarkup`` shape."""
    if keyboard is None:
        return None
    # Lazy import keeps telegram.* out of the module import graph for tests.
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text=btn.text, callback_data=btn.callback_data) for btn in row]
            for row in keyboard
        ]
    )


def _build_default_bot(bot_token: SecretStr) -> TelegramBotProtocol:
    """Construct the production ``telegram.Bot`` instance.

    The import is lazy so tests that inject a fake never pull
    python-telegram-bot, and so the adapter-discipline lint sees
    ``telegram.*`` used exclusively inside this adapter package.
    """
    from telegram import Bot

    return Bot(token=bot_token.get_secret_value())


# Re-export a stable name so the test suite can assert callback_data
# parsing without importing the private alias.
__all__ = [
    "DEFAULT_RETRY_DELAYS",
    "CallbackVerb",
    "TelegramBotProtocol",
    "TelegramBotSurface",
]
