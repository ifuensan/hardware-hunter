"""Tracked SQL migrations for ``hardware_hunter.db``.

Each migration is a numbered ``.sql`` file; the runner in
``adapters/sqlite_store/migrations.py`` applies them in order and tracks
the current version in the ``_meta`` table (``schema_version`` key).

Adding a migration: drop a new ``NNNN_description.sql`` next to the
existing ones. Migrations are run in zero-padded numeric order. Each
file is applied inside a single SQLite transaction; partial application
is impossible.
"""
