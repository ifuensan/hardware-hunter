"""Tests for the Telegram bot adapter — Story 3.12."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import SecretStr

from salvager.adapters.telegram_bot.surface import (
    DEFAULT_RETRY_DELAYS,
    TelegramBotSurface,
)
from salvager.domain.alert import InlineButton, RenderedAlert
from salvager.domain.errors import (
    TelegramConfigError,
    TelegramDeliveryFailed,
)

# ─────────────────────────────────────────────────────────────────────────
# Fake bot + fixtures
# ─────────────────────────────────────────────────────────────────────────


class _FakeMessage:
    """Stand-in for ``telegram.Message`` carrying just ``message_id``."""

    def __init__(self, message_id: int) -> None:
        self.message_id = message_id


class _FakeBot:
    """Minimal fake satisfying :class:`TelegramBotProtocol`."""

    def __init__(
        self,
        *,
        send_message_id: int = 101,
        send_photo_id: int = 202,
        failures: list[Exception] | None = None,
    ) -> None:
        self.send_message_calls: list[dict[str, Any]] = []
        self.send_photo_calls: list[dict[str, Any]] = []
        self.edit_calls: list[dict[str, Any]] = []
        self._send_message_id = send_message_id
        self._send_photo_id = send_photo_id
        # If `failures` is non-empty, each call pops the next exception
        # until the list is empty, then returns a Message.
        self._failures = list(failures or [])

    def _maybe_raise(self) -> None:
        if self._failures:
            raise self._failures.pop(0)

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        parse_mode: str | None = None,
        reply_markup: Any = None,
    ) -> _FakeMessage:
        self.send_message_calls.append(
            {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "reply_markup": reply_markup,
            }
        )
        self._maybe_raise()
        return _FakeMessage(self._send_message_id)

    async def send_photo(
        self,
        chat_id: int,
        photo: str,
        *,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: Any = None,
    ) -> _FakeMessage:
        self.send_photo_calls.append(
            {
                "chat_id": chat_id,
                "photo": photo,
                "caption": caption,
                "parse_mode": parse_mode,
                "reply_markup": reply_markup,
            }
        )
        self._maybe_raise()
        return _FakeMessage(self._send_photo_id)

    async def edit_message_reply_markup(
        self,
        chat_id: int,
        message_id: int,
        *,
        reply_markup: Any = None,
    ) -> None:
        self.edit_calls.append(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "reply_markup": reply_markup,
            }
        )
        self._maybe_raise()


class _NetworkError(Exception):
    """Class name mirrors python-telegram-bot's NetworkError for routing."""

    pass


# Rename so the surface's class-name check sees it as retryable.
_NetworkError.__name__ = "NetworkError"


class _BadRequest(Exception):
    pass


_BadRequest.__name__ = "BadRequest"


def _record_sleeps() -> tuple[list[float], Any]:
    recorded: list[float] = []

    async def _sleep(delay: float) -> None:
        recorded.append(delay)

    return recorded, _sleep


def _build_surface(
    bot: _FakeBot,
    *,
    chat_id: int = 12345,
    retry_delays: tuple[float, ...] = (0.0, 0.0),
) -> tuple[TelegramBotSurface, list[float]]:
    sleeps, sleep_fn = _record_sleeps()
    surface = TelegramBotSurface(
        SecretStr("test-token"),
        chat_id,
        bot=bot,
        retry_delays=retry_delays,
        sleep=sleep_fn,
    )
    return surface, sleeps


def _rendered(*, with_photo: bool = True, with_keyboard: bool = True) -> RenderedAlert:
    keyboard = (
        [
            [
                InlineButton(text="👁 Ver", callback_data="listing:view:abc"),
                InlineButton(text="🙅 Saltar", callback_data="listing:skip:abc"),
            ]
        ]
        if with_keyboard
        else None
    )
    return RenderedAlert(
        text="📦 *Test* — *55,00 €*\n🔍 Confidence: high",
        photo_url="https://cdn/photo.jpg" if with_photo else None,
        inline_keyboard=keyboard,
    )


# ─────────────────────────────────────────────────────────────────────────
# Sending — happy path
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_with_photo_uses_send_photo_and_returns_message_id() -> None:
    bot = _FakeBot()
    surface, _ = _build_surface(bot)
    message_id = await surface.send(_rendered(with_photo=True))
    assert message_id == 202  # _FakeBot.send_photo_id
    assert len(bot.send_photo_calls) == 1
    call = bot.send_photo_calls[0]
    assert call["photo"] == "https://cdn/photo.jpg"
    assert call["parse_mode"] == "MarkdownV2"
    assert call["caption"].startswith("📦")
    assert call["reply_markup"] is not None


@pytest.mark.asyncio
async def test_send_without_photo_uses_send_message() -> None:
    bot = _FakeBot()
    surface, _ = _build_surface(bot)
    message_id = await surface.send(_rendered(with_photo=False))
    assert message_id == 101  # _FakeBot.send_message_id
    assert len(bot.send_photo_calls) == 0
    assert len(bot.send_message_calls) == 1


@pytest.mark.asyncio
async def test_send_with_no_keyboard_passes_none_to_bot() -> None:
    bot = _FakeBot()
    surface, _ = _build_surface(bot)
    await surface.send(_rendered(with_photo=False, with_keyboard=False))
    assert bot.send_message_calls[0]["reply_markup"] is None


# ─────────────────────────────────────────────────────────────────────────
# Retry policy (NFR-I6)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transient_failure_retries_then_succeeds() -> None:
    bot = _FakeBot(failures=[_NetworkError("temporary"), _NetworkError("still temp")])
    surface, sleeps = _build_surface(bot, retry_delays=(0.01, 0.02))
    message_id = await surface.send(_rendered(with_photo=False))
    assert message_id == 101
    assert sleeps == [0.01, 0.02]
    assert len(bot.send_message_calls) == 3


@pytest.mark.asyncio
async def test_all_retries_exhausted_raises_delivery_failed() -> None:
    bot = _FakeBot(
        failures=[_NetworkError("a"), _NetworkError("b"), _NetworkError("c")],
    )
    surface, sleeps = _build_surface(bot, retry_delays=(0.0, 0.0))
    with pytest.raises(TelegramDeliveryFailed):
        await surface.send(_rendered(with_photo=False))
    # Three attempts, two delays in between.
    assert len(bot.send_message_calls) == 3
    assert sleeps == [0.0, 0.0]


@pytest.mark.asyncio
async def test_4xx_error_is_non_retryable() -> None:
    bot = _FakeBot(failures=[_BadRequest("chat not found")])
    surface, sleeps = _build_surface(bot)
    with pytest.raises(TelegramConfigError):
        await surface.send(_rendered(with_photo=False))
    # No retry — sleep never invoked, only one attempt.
    assert len(bot.send_message_calls) == 1
    assert sleeps == []


def test_default_retry_delays_match_documented_pattern() -> None:
    """Doc comment says ~3 attempts in ~20s — default delays are
    [5.0, 15.0]."""
    assert DEFAULT_RETRY_DELAYS == (5.0, 15.0)


# ─────────────────────────────────────────────────────────────────────────
# edit_keyboard
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_keyboard_round_trips() -> None:
    bot = _FakeBot()
    surface, _ = _build_surface(bot)
    keyboard = [[InlineButton(text="✓ visto", callback_data="listing:view:abc")]]
    await surface.edit_keyboard(message_id=42, keyboard=keyboard)
    assert len(bot.edit_calls) == 1
    call = bot.edit_calls[0]
    assert call["chat_id"] == 12345
    assert call["message_id"] == 42
    assert call["reply_markup"] is not None


@pytest.mark.asyncio
async def test_edit_keyboard_with_none_passes_none() -> None:
    """Clearing the keyboard — used by the Phase 2 in-flight ack flow."""
    bot = _FakeBot()
    surface, _ = _build_surface(bot)
    await surface.edit_keyboard(message_id=42, keyboard=None)
    assert bot.edit_calls[0]["reply_markup"] is None


@pytest.mark.asyncio
async def test_edit_keyboard_translates_4xx_to_config_error() -> None:
    bot = _FakeBot(failures=[_BadRequest("message not found")])
    surface, _ = _build_surface(bot)
    with pytest.raises(TelegramConfigError):
        await surface.edit_keyboard(message_id=42, keyboard=None)


# ─────────────────────────────────────────────────────────────────────────
# Callback parsing (AR20 chat-ID allowlist)
# ─────────────────────────────────────────────────────────────────────────


def test_parse_callback_returns_typed_event_for_known_chat() -> None:
    surface, _ = _build_surface(_FakeBot(), chat_id=12345)
    event = surface.parse_callback(
        chat_id=12345,
        message_id=99,
        callback_query_id="cb-1",
        callback_data="listing:view:abc-uuid",
    )
    assert event is not None
    assert event.verb == "view"
    assert event.callback_data == "listing:view:abc-uuid"
    assert event.chat_id == 12345
    assert event.message_id == 99


def test_parse_callback_drops_unknown_chat_id_silently() -> None:
    """AR20: chat IDs outside the allowlist are silently dropped."""
    surface, _ = _build_surface(_FakeBot(), chat_id=12345)
    event = surface.parse_callback(
        chat_id=999_999_999,  # not the configured operator
        message_id=99,
        callback_query_id="cb-2",
        callback_data="listing:view:abc",
    )
    assert event is None


def test_parse_callback_drops_malformed_callback_data() -> None:
    surface, _ = _build_surface(_FakeBot(), chat_id=12345)
    event = surface.parse_callback(
        chat_id=12345,
        message_id=99,
        callback_query_id="cb-3",
        callback_data="bogus_data_without_separators",
    )
    assert event is None


def test_parse_callback_drops_unknown_verb() -> None:
    surface, _ = _build_surface(_FakeBot(), chat_id=12345)
    event = surface.parse_callback(
        chat_id=12345,
        message_id=99,
        callback_query_id="cb-4",
        callback_data="listing:dance:abc",  # 'dance' isn't a valid verb
    )
    assert event is None


@pytest.mark.parametrize("verb", ["view", "skip", "snooze", "buy"])
def test_parse_callback_accepts_every_documented_verb(verb: str) -> None:
    surface, _ = _build_surface(_FakeBot(), chat_id=12345)
    event = surface.parse_callback(
        chat_id=12345,
        message_id=99,
        callback_query_id="cb-x",
        callback_data=f"listing:{verb}:abc",
    )
    assert event is not None
    assert event.verb == verb


# ─────────────────────────────────────────────────────────────────────────
# Adapter discipline — only this package imports telegram.*
# ─────────────────────────────────────────────────────────────────────────


def test_no_other_package_imports_telegram() -> None:
    """NFR-M1: telegram.* allowed only in adapters/telegram_bot/."""
    import ast
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    src_dir = repo_root / "src" / "salvager"
    for path in src_dir.rglob("*.py"):
        if "telegram_bot" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("telegram"), (
                        f"{path.relative_to(repo_root)}: forbidden telegram import"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith("telegram"), (
                    f"{path.relative_to(repo_root)}: forbidden 'from {module} import …'"
                )


# ─────────────────────────────────────────────────────────────────────────
# listen_callbacks placeholder (full wiring lands in Story 3.14)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_listen_callbacks_raises_not_implemented_at_v0() -> None:
    """The dispatcher loop lives in the orchestrator (Story 3.14). At
    v0.x of Story 3.12 we ship parse_callback() so unit tests can
    exercise the parse path; the application-level glue lands next."""
    surface, _ = _build_surface(_FakeBot())

    async def _handler(_event: Any) -> None:
        pass

    with pytest.raises(NotImplementedError):
        await surface.listen_callbacks(_handler)
