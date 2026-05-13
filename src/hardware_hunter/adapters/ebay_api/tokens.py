"""OAuth-token persistence for the eBay adapter — Story 3.7 / NFR-S2.

Tokens are stored at ``data_dir/auth/oauth_tokens.json``. Writes are
atomic (temp file in the same directory → fsync → rename) so a crash
mid-write can't leave a half-written token file behind. The destination
mode is enforced at ``0o600`` on every write — losing that bit is the
exact failure the credential-permission gate (Story 2.11) refuses to
tolerate.

Why pydantic for the on-disk shape
----------------------------------
Tokens are a small JSON envelope but they're the file the daemon's
authentication pivots on. Strict typing + ``extra="forbid"`` means a
hand-edited file with a stray key fails loud, not silent.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict

OAUTH_TOKEN_FILE_MODE = 0o600

#: Refresh access tokens this far ahead of expiry.
REFRESH_LEAD_TIME = timedelta(minutes=5)


class OAuthTokens(BaseModel):
    """The JSON shape stored on disk and used in memory."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    expires_at: datetime  # UTC absolute expiry of the access token
    token_type: str = "Bearer"
    scope: str | None = None

    def needs_refresh(self, *, now: datetime | None = None) -> bool:
        """True if the access token is within :data:`REFRESH_LEAD_TIME` of
        expiry (or already expired). 5-minute window matches the AC."""
        moment = now if now is not None else datetime.now(UTC)
        return moment + REFRESH_LEAD_TIME >= self.expires_at


class OAuthTokenStore:
    """Disk-backed token persistence with atomic write + mode 0600."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> OAuthTokens:
        """Read and parse the token file. Caller catches and decides."""
        raw = self._path.read_text(encoding="utf-8")
        return OAuthTokens.model_validate_json(raw)

    def save(self, tokens: OAuthTokens) -> None:
        """Atomic write: temp file in the same dir → fsync → rename.

        Same-directory placement is critical: ``rename`` is atomic on
        POSIX only when source and destination are on the same
        filesystem. Putting the temp file alongside the target file
        guarantees that.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = tokens.model_dump_json()

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self._path.parent,
            prefix=".oauth_tokens.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)

        try:
            tmp_path.chmod(OAUTH_TOKEN_FILE_MODE)
            tmp_path.replace(self._path)
        except Exception:
            # Best-effort cleanup if something between chmod and rename fails.
            with contextlib.suppress(OSError):
                tmp_path.unlink()
            raise

        # Belt and braces: ensure the final destination is 0600 even if a
        # prior copy of the file at the target path had a different mode
        # (replace doesn't change permissions on some platforms).
        self._path.chmod(OAUTH_TOKEN_FILE_MODE)


def parse_expires_in(expires_in_seconds: int, *, now: datetime | None = None) -> datetime:
    """Convert eBay's ``expires_in`` (seconds-relative) to UTC absolute."""
    moment = now if now is not None else datetime.now(UTC)
    return moment + timedelta(seconds=int(expires_in_seconds))
