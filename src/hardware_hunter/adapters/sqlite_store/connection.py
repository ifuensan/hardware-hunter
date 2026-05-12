"""SQLite connection factory — WAL mode + synchronous=NORMAL.

WAL (write-ahead logging) is what lets the CLI (``audit show``,
``health``) read concurrently while the daemon is writing — without it,
every CLI invocation would block on the daemon's write lock. The
``synchronous=NORMAL`` setting trades a tiny crash-recovery window
(milliseconds) for substantially less fsync overhead; combined with WAL
that crash window cannot corrupt the database, only lose the very last
transaction.

Per AC: ``hardware_hunter.db`` lives at ``data_dir/hardware_hunter.db``.
This module does not own ``data_dir`` resolution — callers (typically
the daemon entry point loading ``config.yaml``) pass the absolute path.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_FILENAME = "hardware_hunter.db"


def open_connection(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection in WAL mode.

    The connection is configured with ``check_same_thread=False`` so the
    async store can dispatch DB calls through ``asyncio.to_thread``
    without sqlite3 refusing the cross-thread access — the store's own
    ``asyncio.Lock`` serializes writes, so concurrent access is safe.

    Row factory is :class:`sqlite3.Row` so query results can be accessed
    both positionally and by column name without explicit unpacking.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        path,
        isolation_level=None,  # autocommit; transactions managed explicitly
        check_same_thread=False,
        timeout=30.0,
    )
    connection.row_factory = sqlite3.Row

    # WAL must be set per-database, persists across connections. NORMAL
    # journaling synchronicity is the documented WAL pairing — FULL
    # makes WAL fsync after every commit which defeats most of its perf
    # benefit.
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA foreign_keys=OFF")  # FK enforcement is application-side
    return connection
