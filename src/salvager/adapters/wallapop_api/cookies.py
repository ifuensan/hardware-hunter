"""Netscape cookies.txt → ``httpx.Cookies`` helper.

The operator captures their Wallapop session cookies via
``salvager login wallapop`` (Story 2.9, lands in Epic 3 along
the marketplace adapter). The file is in the standard Netscape format
that ``curl`` and ``wget`` produce, so any cookie tooling on disk is
compatible.

Why not ``http.cookiejar.MozillaCookieJar`` directly?
Mozilla's reader is strict — a leading ``#HttpOnly_`` prefix (which
modern browsers add) makes it skip a row silently. We do the parse
ourselves, which keeps the rules explicit + lets us surface a clear
``WallapopCookiesError`` when the file is malformed.
"""

from __future__ import annotations

from pathlib import Path

import httpx


class WallapopCookiesError(RuntimeError):
    """The cookies.txt file is missing or unparseable."""


def load_cookies(path: str | Path) -> httpx.Cookies:
    """Parse a Netscape cookies.txt file and return an ``httpx.Cookies`` jar.

    Each non-comment, non-empty line is expected to have 7
    tab-separated fields:

      ``<domain>\\t<include_subdomains>\\t<path>\\t<secure>\\t<expiry>\\t<name>\\t<value>``

    Lines starting with ``#HttpOnly_`` are tolerated (the marker is
    stripped). Malformed lines raise :class:`WallapopCookiesError` with
    the line number — the operator has a typo'd file rather than a
    silent partial-load.
    """
    cookie_path = Path(path)
    if not cookie_path.exists():
        raise WallapopCookiesError(f"cookies file not found: {cookie_path}")

    jar = httpx.Cookies()
    lines = cookie_path.read_text(encoding="utf-8").splitlines()
    for line_number, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        # Allow `#HttpOnly_` prefix (Chrome/Firefox add this); reject true comments.
        if stripped.startswith("#HttpOnly_"):
            stripped = stripped.removeprefix("#HttpOnly_")
        elif stripped.startswith("#"):
            continue
        fields = stripped.split("\t")
        if len(fields) != 7:
            raise WallapopCookiesError(
                f"{cookie_path}:{line_number}: expected 7 tab-separated fields, got {len(fields)}"
            )
        domain, _include_subs, cookie_path_field, _secure, _expiry, name, value = fields
        jar.set(name, value, domain=domain, path=cookie_path_field)
    return jar
