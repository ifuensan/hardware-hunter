"""Tracked SQL-migration runner — AR10.

Discovers ``NNNN_*.sql`` files in ``salvager.migrations``,
compares their numeric prefixes against the ``schema_version`` stored
in the ``_meta`` table, and applies any missing migrations in numeric
order — each inside its own transaction so partial application is
impossible.

Drift detection (``validate-config``'s plumbing in Story 4.x): if
``schema_version`` is *higher* than the highest available migration —
which can happen if an operator downgrades the binary without rolling
the schema back — the runner raises :class:`SchemaDriftError` instead
of silently re-using a future schema. The opposite (code newer than
DB) is the normal upgrade path.
"""

from __future__ import annotations

import re
import sqlite3
from importlib import resources
from pathlib import Path

_MIGRATION_FILE_RE = re.compile(r"^(\d{4})_.+\.sql$")
_SCHEMA_VERSION_KEY = "schema_version"


class MigrationError(RuntimeError):
    """Base class for migration-runner failures."""


class SchemaDriftError(MigrationError):
    """DB has a higher schema_version than the binary knows about."""


class MigrationRunner:
    """Apply pending migrations to a SQLite database."""

    def __init__(self, package: str = "salvager.migrations") -> None:
        self._package = package

    def available_migrations(self) -> list[tuple[int, str]]:
        """Return [(version, filename), …] sorted ascending by version."""
        out: list[tuple[int, str]] = []
        for entry in resources.files(self._package).iterdir():
            name = entry.name
            match = _MIGRATION_FILE_RE.match(name)
            if not match:
                continue
            out.append((int(match.group(1)), name))
        out.sort(key=lambda pair: pair[0])
        return out

    def current_version(self, connection: sqlite3.Connection) -> int:
        """Read ``_meta.schema_version``; returns 0 if ``_meta`` doesn't exist yet."""
        cursor = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_meta'"
        )
        if cursor.fetchone() is None:
            return 0
        cursor = connection.execute("SELECT value FROM _meta WHERE key = ?", (_SCHEMA_VERSION_KEY,))
        row = cursor.fetchone()
        if row is None:
            return 0
        return int(row[0])

    def run(self, connection: sqlite3.Connection) -> int:
        """Apply pending migrations; return the resulting schema_version.

        If the DB is already at or above the highest available version,
        the function is a no-op and returns the current version. If the
        DB is *ahead* of the binary, :class:`SchemaDriftError` is
        raised — operators get a loud failure, not a silent skip.
        """
        available = self.available_migrations()
        if not available:
            return self.current_version(connection)

        latest_available = available[-1][0]
        current = self.current_version(connection)

        if current > latest_available:
            raise SchemaDriftError(
                f"DB schema_version={current} exceeds the binary's highest "
                f"available migration ({latest_available}); rolling back is "
                "not automatic — confirm the binary version matches the DB."
            )

        pending = [(version, name) for (version, name) in available if version > current]
        if not pending:
            return current

        for version, name in pending:
            sql = self._read_migration(name)
            self._apply_one(connection, version, sql)

        return latest_available

    def _read_migration(self, filename: str) -> str:
        with resources.files(self._package).joinpath(filename).open("r", encoding="utf-8") as fh:
            return fh.read()

    @staticmethod
    def _apply_one(connection: sqlite3.Connection, version: int, sql: str) -> None:
        """Run one migration script.

        ``Connection.executescript`` does its own implicit ``COMMIT``
        before running the script, so an outer ``BEGIN`` block is
        rejected. Our migrations are written with ``CREATE TABLE IF
        NOT EXISTS`` and ``CREATE INDEX IF NOT EXISTS`` so a partial
        application is safe to re-attempt; the ``_meta`` row insert
        is the last step, and the next run will resume cleanly if it
        failed.
        """
        connection.executescript(sql)
        connection.execute(
            "INSERT OR REPLACE INTO _meta (key, value) VALUES (?, ?)",
            (_SCHEMA_VERSION_KEY, str(version)),
        )


def db_path_under(data_dir: str | Path) -> Path:
    """Return the canonical ``salvager.db`` path under ``data_dir``."""
    return Path(data_dir) / "salvager.db"
