"""Tests for the eBay OAuth adapter — Story 2.10.

Exercises the consent-URL builder (pure) and the code→token exchange
(httpx :class:`MockTransport`). No real eBay calls.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from pydantic import SecretStr

from hardware_hunter.adapters.ebay_api.oauth import (
    DEFAULT_SCOPE,
    build_consent_url,
    exchange_code_for_tokens,
)
from hardware_hunter.domain.errors import EbayOAuthExchangeFailed

_APP_ID = SecretStr("APP-1234")
_CERT_ID = SecretStr("CERT-5678")
_RU_NAME = "ifuensan-hardware-hunter-RUNAME"


# ─────────────────────────────────────────────────────────────────────────
# build_consent_url
# ─────────────────────────────────────────────────────────────────────────


def test_consent_url_carries_required_oauth_params() -> None:
    url = build_consent_url(app_id="APP-1234", ru_name=_RU_NAME)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.netloc == "auth.ebay.com"
    assert parsed.path == "/oauth2/authorize"
    assert query["client_id"] == ["APP-1234"]
    assert query["response_type"] == ["code"]
    assert query["redirect_uri"] == [_RU_NAME]
    assert query["scope"] == [DEFAULT_SCOPE]


def test_consent_url_honours_custom_scope() -> None:
    url = build_consent_url(
        app_id="APP-1234",
        ru_name=_RU_NAME,
        scope="https://api.ebay.com/oauth/api_scope/buy.item.feed",
    )
    query = parse_qs(urlparse(url).query)
    assert query["scope"] == ["https://api.ebay.com/oauth/api_scope/buy.item.feed"]


# ─────────────────────────────────────────────────────────────────────────
# exchange_code_for_tokens
# ─────────────────────────────────────────────────────────────────────────


async def test_exchange_success_returns_oauth_tokens() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={
                "access_token": "ACCESS-aaa",
                "refresh_token": "REFRESH-bbb",
                "expires_in": 7200,
                "token_type": "Bearer",
                "scope": DEFAULT_SCOPE,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tokens = await exchange_code_for_tokens(
        code="AUTH-CODE-xyz",
        app_id=_APP_ID,
        cert_id=_CERT_ID,
        ru_name=_RU_NAME,
        client=client,
    )

    assert tokens.access_token == "ACCESS-aaa"
    assert tokens.refresh_token == "REFRESH-bbb"
    assert tokens.token_type == "Bearer"
    # The POST hit the token endpoint with Basic auth + the code in the body.
    assert captured["url"] == "https://api.ebay.com/identity/v1/oauth2/token"
    assert str(captured["auth"]).startswith("Basic ")
    assert "grant_type=authorization_code" in str(captured["body"])
    assert "code=AUTH-CODE-xyz" in str(captured["body"])


async def test_exchange_http_400_raises_with_ebay_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": "invalid_grant",
                "error_description": "the provided authorization code is invalid",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(EbayOAuthExchangeFailed) as exc_info:
        await exchange_code_for_tokens(
            code="STALE-CODE",
            app_id=_APP_ID,
            cert_id=_CERT_ID,
            ru_name=_RU_NAME,
            client=client,
        )
    assert exc_info.value.status_code == 400
    assert "authorization code is invalid" in exc_info.value.ebay_message


async def test_exchange_non_json_error_body_falls_back_to_raw_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream unavailable")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(EbayOAuthExchangeFailed) as exc_info:
        await exchange_code_for_tokens(
            code="CODE",
            app_id=_APP_ID,
            cert_id=_CERT_ID,
            ru_name=_RU_NAME,
            client=client,
        )
    assert exc_info.value.status_code == 503
    assert "upstream unavailable" in exc_info.value.ebay_message


async def test_exchange_transport_error_raises_oauth_failed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(EbayOAuthExchangeFailed) as exc_info:
        await exchange_code_for_tokens(
            code="CODE",
            app_id=_APP_ID,
            cert_id=_CERT_ID,
            ru_name=_RU_NAME,
            client=client,
        )
    assert exc_info.value.status_code == 0
