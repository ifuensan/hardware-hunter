"""Tests for ``salvager login ebay`` — Story 2.10.

The token exchange is mocked at the module boundary (the ``exchange``
parameter of :func:`run`). The :class:`OAuthTokenStore` write runs for
real against ``tmp_path``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import SecretStr

from salvager.adapters.ebay_api.tokens import OAuthTokens
from salvager.cli.commands.login_ebay import run
from salvager.domain.errors import EbayOAuthExchangeFailed

_APP_ID = SecretStr("APP-1234")
_CERT_ID = SecretStr("CERT-5678")
_RU_NAME = "ifuensan-salvager-RUNAME"


def _tokens() -> OAuthTokens:
    return OAuthTokens(
        access_token="ACCESS-aaa",
        refresh_token="REFRESH-bbb",
        expires_at=datetime(2026, 5, 14, 14, 0, 0, tzinfo=UTC),
        token_type="Bearer",
        scope="https://api.ebay.com/oauth/api_scope",
    )


def _run(
    tmp_path: Path,
    **overrides: object,
) -> int:
    """Invoke :func:`run` with sane interactive defaults, overridable per test."""
    kwargs: dict[str, object] = {
        "app_id": _APP_ID,
        "cert_id": _CERT_ID,
        "ru_name": _RU_NAME,
        "isatty": lambda: True,
        "open_browser": lambda url: True,
        "prompt_for_code": lambda: "AUTH-CODE-xyz",
    }
    kwargs.update(overrides)
    return run(tmp_path, **kwargs)  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────────────────


def test_run_writes_oauth_tokens_json_with_mode_0600(tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    async def fake_exchange(**kwargs: object) -> OAuthTokens:
        seen.update(kwargs)
        return _tokens()

    code = _run(tmp_path, exchange=fake_exchange)

    tokens_path = tmp_path / "auth" / "oauth_tokens.json"
    assert code == 0
    assert tokens_path.exists()
    assert (tokens_path.stat().st_mode & 0o777) == 0o600

    payload = json.loads(tokens_path.read_text(encoding="utf-8"))
    assert payload["access_token"] == "ACCESS-aaa"
    assert payload["refresh_token"] == "REFRESH-bbb"
    # The pasted code + creds reached the exchange.
    assert seen["code"] == "AUTH-CODE-xyz"
    assert seen["ru_name"] == _RU_NAME


def test_run_opens_browser_with_consent_url(tmp_path: Path) -> None:
    opened: list[str] = []

    async def fake_exchange(**kwargs: object) -> OAuthTokens:
        return _tokens()

    def record_open(url: str) -> bool:
        opened.append(url)
        return True

    code = _run(tmp_path, exchange=fake_exchange, open_browser=record_open)
    assert code == 0
    assert len(opened) == 1
    assert opened[0].startswith("https://auth.ebay.com/oauth2/authorize?")
    assert "ifuensan-salvager-RUNAME" in opened[0]


def test_run_survives_browser_open_failure(tmp_path: Path) -> None:
    """A headless box has no browser — that must not abort the flow."""

    async def fake_exchange(**kwargs: object) -> OAuthTokens:
        return _tokens()

    def boom(url: str) -> bool:
        raise OSError("no display")

    code = _run(tmp_path, exchange=fake_exchange, open_browser=boom)
    assert code == 0
    assert (tmp_path / "auth" / "oauth_tokens.json").exists()


# ─────────────────────────────────────────────────────────────────────────
# Failure paths
# ─────────────────────────────────────────────────────────────────────────


def test_run_refuses_in_non_tty(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def never_called(**kwargs: object) -> OAuthTokens:
        raise AssertionError("exchange must not run in non-TTY context")

    code = _run(tmp_path, isatty=lambda: False, exchange=never_called)
    assert code == 1
    assert "interactive terminal" in capsys.readouterr().err
    assert not (tmp_path / "auth" / "oauth_tokens.json").exists()


def test_run_empty_code_returns_exit_4(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def never_called(**kwargs: object) -> OAuthTokens:
        raise AssertionError("exchange must not run without a code")

    code = _run(tmp_path, prompt_for_code=lambda: "", exchange=never_called)
    assert code == 4
    assert "no authorization code" in capsys.readouterr().err
    assert not (tmp_path / "auth" / "oauth_tokens.json").exists()


def test_run_exchange_failure_returns_exit_4_with_ebay_message(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def failing_exchange(**kwargs: object) -> OAuthTokens:
        raise EbayOAuthExchangeFailed(400, "the provided authorization code is invalid")

    code = _run(tmp_path, exchange=failing_exchange)
    assert code == 4
    err = capsys.readouterr().err
    assert "OAuth exchange failed" in err
    assert "authorization code is invalid" in err
    assert "re-paste" in err  # hint
    assert not (tmp_path / "auth" / "oauth_tokens.json").exists()
