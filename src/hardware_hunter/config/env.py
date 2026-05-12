"""``.env`` loader — FR49 (.env read once at start) + NFR-S1 (no credential
values in logs) + Story 2.6 contract.

This is the single seam through which credentials enter the process. Every
field is :class:`pydantic.SecretStr` so ``repr()`` and ``str()`` mask
values to ``**********``; a structured-log helper :func:`log_env_loaded`
emits only the *names* of loaded vars, never their contents.

Singleton + no hot-reload
-------------------------
:func:`get_env_settings` memoizes the first successful load (FR49 — no
hot-reload). Re-reading ``.env`` requires a process restart. Tests use
:func:`reset_env_cache` to scrub the singleton between cases.

Daemon entry point
------------------
:func:`load_env_or_exit` is the helper the daemon and CLI commands call
when they need credentials. On ``ValidationError`` (a required var was
missing) it renders the locked error template and exits ``4`` per the
Story 2.6 AC.
"""

from __future__ import annotations

import sys
from functools import cache
from pathlib import Path

from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from hardware_hunter.observability.logging import get_logger
from hardware_hunter.observability.styling import render_prose

# Exit code for "missing or unusable credentials" per Story 2.6 AC.
ENV_AUTH_EXIT_CODE = 4


class EnvSettings(BaseSettings):
    """Credentials loaded from ``.env`` exactly once per process.

    Every field is ``SecretStr`` so the underlying value never appears in
    ``repr()``, ``str()``, or naive ``model_dump_json()``. Pulling the
    cleartext requires an explicit ``.get_secret_value()`` call — code
    review rejects any use of that method outside an adapter.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Telegram — bot delivery + chat-ID allowlist (AR20).
    TELEGRAM_BOT_TOKEN: SecretStr
    TELEGRAM_CHAT_ID: int

    # LLM provider — default Gemini Flash; swappable via NFR-I3.
    GEMINI_API_KEY: SecretStr

    # eBay developer credentials — OAuth bootstrapping via `login ebay`.
    EBAY_APP_ID: SecretStr
    EBAY_CERT_ID: SecretStr
    EBAY_DEV_ID: SecretStr

    # TinyFish — proxied through Hermes MCP, but the daemon still loads
    # the raw key to support local-direct testing in `hardware-hunter
    # test-search` (Epic 4) when Hermes is unreachable.
    TINYFISH_API_KEY: SecretStr

    # Hermes is a remote service (Proxmox VM) — not embedded as a Python
    # library. These two are optional because some test environments
    # stub the adapter; the Hermes-backed scheduler in Story 3.8 requires
    # at least HERMES_URL.
    HERMES_URL: str | None = None
    HERMES_API_KEY: SecretStr | None = None


@cache
def _load(env_file: str) -> EnvSettings:
    """Cached load keyed by the env-file path string."""
    return EnvSettings(_env_file=env_file)  # type: ignore[call-arg]


def get_env_settings(env_file: str | Path = ".env") -> EnvSettings:
    """Return the cached :class:`EnvSettings` instance.

    The first call hydrates from ``env_file`` (default ``.env`` in the
    current working directory). Subsequent calls with the same path
    return the same instance — FR49 "once at start" semantics.

    Tests that need a fresh load with different values must call
    :func:`reset_env_cache` first.
    """
    return _load(str(env_file))


def reset_env_cache() -> None:
    """Drop the memoized :class:`EnvSettings` (test affordance only)."""
    _load.cache_clear()


def log_env_loaded(settings: EnvSettings) -> None:
    """Structured-log line confirming credentials loaded — names only.

    The shape is deliberate: we want operators to be able to grep for
    ``"event":"env_loaded"`` and see exactly which credentials were
    picked up without ever surfacing a value. NFR-S1 enforced by
    construction here — there's no codepath that includes a secret.
    """
    log = get_logger("config.env")
    log.info(
        "env_loaded",
        extra={
            "vars_loaded": sorted(
                name
                for name, value in {
                    "TELEGRAM_BOT_TOKEN": settings.TELEGRAM_BOT_TOKEN,
                    "TELEGRAM_CHAT_ID": settings.TELEGRAM_CHAT_ID,
                    "GEMINI_API_KEY": settings.GEMINI_API_KEY,
                    "EBAY_APP_ID": settings.EBAY_APP_ID,
                    "EBAY_CERT_ID": settings.EBAY_CERT_ID,
                    "EBAY_DEV_ID": settings.EBAY_DEV_ID,
                    "TINYFISH_API_KEY": settings.TINYFISH_API_KEY,
                    "HERMES_URL": settings.HERMES_URL,
                    "HERMES_API_KEY": settings.HERMES_API_KEY,
                }.items()
                if value is not None
            ),
        },
    )


def load_env_or_exit(env_file: str | Path = ".env") -> EnvSettings:
    """Load env or render the locked error template and exit 4.

    Used by the daemon and any CLI command that requires credentials
    (e.g. ``validate-config``, ``test-search``, the bare-invocation
    poll loop). On missing var: stderr gets the Story 2.6 error
    template, the process exits with code :data:`ENV_AUTH_EXIT_CODE`.
    """
    try:
        return get_env_settings(env_file)
    except ValidationError as exc:
        missing = _first_missing_field(exc)
        message = (
            f"missing required env var: {missing}" if missing else "invalid .env configuration"
        )
        render_prose(message, style="error", hint="see .env.example")
        sys.exit(ENV_AUTH_EXIT_CODE)


def _first_missing_field(exc: ValidationError) -> str | None:
    """Find the first ``missing`` error in a ValidationError and return
    the env-var name. Returns None when the error isn't a missing-field
    case (e.g. type-coercion failure on an existing var)."""
    for err in exc.errors():
        if err.get("type") == "missing" and err.get("loc"):
            return str(err["loc"][0])
    return None
