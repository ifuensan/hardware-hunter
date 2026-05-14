"""eBay OAuth authorization-code flow — Story 2.10 (FR42, NFR-I5).

The ``hardware-hunter login ebay`` CLI command composes against this
module: it builds the consent URL the operator visits, then exchanges
the authorization code they paste back for refresh + access tokens.

Why httpx lives here
--------------------
Adapter discipline (NFR-M1): every external HTTP call sits inside
``adapters/``. The token-exchange POST is no exception — the CLI
command owns the operator interaction, this adapter owns the wire.

eBay OAuth specifics
--------------------
- The consent URL points at ``auth.ebay.com/oauth2/authorize`` with
  ``response_type=code``.
- ``redirect_uri`` is the operator's **RuName** (a registered
  redirect-URL *name*, not a literal URL) — eBay's redirect quirk.
- The token POST hits ``api.ebay.com/identity/v1/oauth2/token`` with
  HTTP Basic auth (``app_id`` : ``cert_id``) and a form body.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx
from pydantic import SecretStr

from hardware_hunter.adapters.ebay_api.tokens import OAuthTokens, parse_expires_in
from hardware_hunter.domain.errors import EbayOAuthExchangeFailed

#: eBay's production OAuth endpoints.
_AUTHORIZE_URL = "https://auth.ebay.com/oauth2/authorize"
_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"

#: Default scope for the Browse API (public item search). The operator
#: can override it, but this is the only scope the v1 daemon needs.
DEFAULT_SCOPE = "https://api.ebay.com/oauth/api_scope"

_DEFAULT_TIMEOUT = httpx.Timeout(10.0)


def build_consent_url(
    *,
    app_id: str,
    ru_name: str,
    scope: str = DEFAULT_SCOPE,
) -> str:
    """Build the eBay OAuth consent URL the operator opens in a browser.

    ``ru_name`` is the operator's registered RuName; eBay redirects to
    the URL that RuName resolves to, with ``?code=...`` appended. The
    operator copies that ``code`` value and pastes it back into the CLI.
    """
    query = urlencode(
        {
            "client_id": app_id,
            "response_type": "code",
            "redirect_uri": ru_name,
            "scope": scope,
        }
    )
    return f"{_AUTHORIZE_URL}?{query}"


async def exchange_code_for_tokens(
    *,
    code: str,
    app_id: SecretStr,
    cert_id: SecretStr,
    ru_name: str,
    client: httpx.AsyncClient | None = None,
) -> OAuthTokens:
    """Swap an authorization ``code`` for refresh + access tokens.

    ``client`` is dependency-injected for tests — production calls
    leave it None and we construct one with ``verify=True`` (NFR-S3).
    Tests pass an :class:`httpx.AsyncClient` wired to a
    :class:`httpx.MockTransport`.

    Raises:
        EbayOAuthExchangeFailed: eBay rejected the code (HTTP 4xx) —
            usually a stale or mistyped code.
    """
    auth = httpx.BasicAuth(app_id.get_secret_value(), cert_id.get_secret_value())
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": ru_name,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    owned_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT, verify=True)

    try:
        try:
            response = await client.post(_TOKEN_URL, data=data, auth=auth, headers=headers)
        except httpx.HTTPError as exc:
            raise EbayOAuthExchangeFailed(0, str(exc)) from exc

        if response.status_code >= 400:
            raise EbayOAuthExchangeFailed(
                response.status_code,
                _extract_ebay_error(response),
            )

        payload = response.json()
        return OAuthTokens(
            access_token=payload["access_token"],
            refresh_token=payload["refresh_token"],
            expires_at=parse_expires_in(int(payload["expires_in"])),
            token_type=payload.get("token_type", "Bearer"),
            scope=payload.get("scope"),
        )
    finally:
        if owned_client:
            await client.aclose()


def _extract_ebay_error(response: httpx.Response) -> str:
    """Pull eBay's human-readable error text out of a 4xx body.

    eBay's OAuth errors come back as
    ``{"error": "...", "error_description": "..."}``. Falls back to a
    truncated raw body when the JSON shape is unexpected.
    """
    try:
        body = response.json()
    except ValueError:
        return response.text[:200] or f"HTTP {response.status_code}"
    description = body.get("error_description") or body.get("error")
    if description:
        return str(description)
    return response.text[:200] or f"HTTP {response.status_code}"


__all__ = [
    "DEFAULT_SCOPE",
    "build_consent_url",
    "exchange_code_for_tokens",
]
