"""Tests for ``salvager phase2 enable/disable/status`` — Story 5.12.

The three ``run_*`` functions are exercised directly. Where TTY semantics
or ``input()`` matter, the test passes its own ``is_tty`` /``input_fn``
fakes — no real stdin is touched.

A tiny ``wishlist.yaml`` fixture is materialised in ``tmp_path`` so the
ruamel round-trip is genuine (load → modify → save → load again).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from salvager.adapters.sqlite_store import (
    MigrationRunner,
    Phase2AuditWriter,
    open_connection,
)
from salvager.adapters.sqlite_store.migrations import db_path_under
from salvager.adapters.sqlite_store.phase2_state_reader import (
    SqlitePhase2StateReader,
)
from salvager.cli.commands import phase2_cmd
from salvager.config.wishlist_yaml import load_wishlist

_WISHLIST_YAML = """\
entries:
  - manufacturer: Western Digital
    model: WD Red Plus 4TB
    ref: WD40EFPX
    type: hdd
    keywords:
      - wd red plus 4tb
    max_price_solo: 70.00
    confidence_threshold: medium
    phase2:
      enabled: false
      max_price_eur: 60.00

  - manufacturer: Crucial
    model: 16GB DDR4 3200
    ref: CT16G4DFD832A
    type: ram
    keywords:
      - crucial 16gb ddr4
    max_price_solo: 30.00
    confidence_threshold: high
    phase2:
      enabled: true
      max_price_eur: 25.00

  - manufacturer: Seagate
    model: IronWolf 8TB
    ref: ST8000VN004
    type: hdd
    keywords:
      - seagate ironwolf 8tb
    max_price_solo: 120.00
    confidence_threshold: medium
    phase2:
      enabled: false
      max_price_eur: null
"""


@pytest.fixture
def workspace(tmp_path: Path) -> Iterator[tuple[Path, Path]]:
    """Provide (wishlist_path, data_dir) with a migrated SQLite DB."""
    wishlist_path = tmp_path / "wishlist.yaml"
    wishlist_path.write_text(_WISHLIST_YAML, encoding="utf-8")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    connection = open_connection(db_path_under(data_dir))
    try:
        MigrationRunner().run(connection)
    finally:
        connection.close()
    yield wishlist_path, data_dir


def _phase2_enabled(wishlist_path: Path, ref: str) -> bool:
    wishlist = load_wishlist(wishlist_path)
    return next(e.phase2.enabled for e in wishlist.entries if e.ref == ref)


# ─────────────────────────────────────────────────────────────────────────
# phase2 enable
# ─────────────────────────────────────────────────────────────────────────


def test_enable_flips_the_flag_and_keeps_max_price(
    workspace: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    wishlist_path, data_dir = workspace
    code = phase2_cmd.run_enable(
        query="WD40EFPX",
        wishlist_path=wishlist_path,
        data_dir=data_dir,
        is_tty=lambda: True,
    )
    assert code == 0
    assert _phase2_enabled(wishlist_path, "WD40EFPX") is True
    out = capsys.readouterr().out
    assert "Phase 2 enabled" in out
    assert "WD Red Plus 4TB" in out
    assert "60,00 €" in out
    assert "circuit reset" in out


def test_enable_prompts_for_missing_max_price_in_tty(
    workspace: tuple[Path, Path],
) -> None:
    wishlist_path, data_dir = workspace
    code = phase2_cmd.run_enable(
        query="ST8000VN004",
        wishlist_path=wishlist_path,
        data_dir=data_dir,
        is_tty=lambda: True,
        input_fn=lambda _prompt: "95,00",  # operator types a price
    )
    assert code == 0
    wishlist = load_wishlist(wishlist_path)
    entry = next(e for e in wishlist.entries if e.ref == "ST8000VN004")
    assert entry.phase2.enabled is True
    # The save/load round-trip drops trailing zeros (Decimal → float
    # via ruamel) but the numeric value survives.
    from decimal import Decimal

    assert entry.phase2.max_price_eur == Decimal("95.00")


def test_enable_aborts_when_no_max_price_and_non_tty(
    workspace: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    wishlist_path, data_dir = workspace
    code = phase2_cmd.run_enable(
        query="ST8000VN004",
        wishlist_path=wishlist_path,
        data_dir=data_dir,
        is_tty=lambda: False,
    )
    assert code == 2
    assert "no phase2.max_price_eur" in capsys.readouterr().err


def test_enable_clears_global_lockout_and_resets_counter(
    workspace: tuple[Path, Path],
) -> None:
    wishlist_path, data_dir = workspace

    # Seed the SQLite state with a locked-out, fail-counter-bumped Phase 2.
    async def _seed() -> None:
        writer = Phase2AuditWriter(db_path_under(data_dir))
        try:
            await writer.increment_failure_counter()
            await writer.increment_failure_counter()
            await writer.set_global_disable("circuit_breaker_open")
        finally:
            await writer.close()

    import asyncio

    asyncio.run(_seed())

    code = phase2_cmd.run_enable(
        query="WD40EFPX",
        wishlist_path=wishlist_path,
        data_dir=data_dir,
        is_tty=lambda: True,
    )
    assert code == 0

    async def _read() -> None:
        reader = SqlitePhase2StateReader(db_path_under(data_dir))
        try:
            state = await reader.read()
            assert state.globally_disabled is False
            assert state.consecutive_failures == 0
        finally:
            await reader.close()

    asyncio.run(_read())


def test_unknown_entry_exits_usage_error(
    workspace: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    wishlist_path, data_dir = workspace
    code = phase2_cmd.run_enable(
        query="nope-not-here",
        wishlist_path=wishlist_path,
        data_dir=data_dir,
        is_tty=lambda: True,
    )
    assert code == 2
    err = capsys.readouterr().err
    assert "not found in wishlist.yaml" in err
    assert "wishlist list" in err


# ─────────────────────────────────────────────────────────────────────────
# phase2 disable
# ─────────────────────────────────────────────────────────────────────────


def test_per_entry_disable_keeps_global_lockout_untouched(
    workspace: tuple[Path, Path],
) -> None:
    wishlist_path, data_dir = workspace
    code = phase2_cmd.run_disable(
        query="CT16G4DFD832A",
        all_entries=False,
        wishlist_path=wishlist_path,
        data_dir=data_dir,
        is_tty=lambda: True,
    )
    assert code == 0
    assert _phase2_enabled(wishlist_path, "CT16G4DFD832A") is False

    import asyncio

    async def _read() -> None:
        reader = SqlitePhase2StateReader(db_path_under(data_dir))
        try:
            state = await reader.read()
            assert state.globally_disabled is False
        finally:
            await reader.close()

    asyncio.run(_read())


def test_disable_all_requires_tty(
    workspace: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    wishlist_path, data_dir = workspace
    code = phase2_cmd.run_disable(
        query=None,
        all_entries=True,
        wishlist_path=wishlist_path,
        data_dir=data_dir,
        is_tty=lambda: False,
    )
    assert code == 1
    assert "interactive terminal" in capsys.readouterr().err


def test_disable_all_typing_wrong_number_aborts(
    workspace: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    wishlist_path, data_dir = workspace
    # Only the Crucial entry is enabled in the fixture (count == 1).
    code = phase2_cmd.run_disable(
        query=None,
        all_entries=True,
        wishlist_path=wishlist_path,
        data_dir=data_dir,
        is_tty=lambda: True,
        input_fn=lambda _prompt: "yes",  # wrong — must type the count
    )
    assert code == 1
    assert "aborted" in capsys.readouterr().out
    # Wishlist unchanged.
    assert _phase2_enabled(wishlist_path, "CT16G4DFD832A") is True


def test_disable_all_typing_count_disables_all_and_locks_globally(
    workspace: tuple[Path, Path],
) -> None:
    wishlist_path, data_dir = workspace
    code = phase2_cmd.run_disable(
        query=None,
        all_entries=True,
        wishlist_path=wishlist_path,
        data_dir=data_dir,
        is_tty=lambda: True,
        input_fn=lambda _prompt: "1",
    )
    assert code == 0
    assert _phase2_enabled(wishlist_path, "CT16G4DFD832A") is False

    import asyncio

    async def _read() -> None:
        reader = SqlitePhase2StateReader(db_path_under(data_dir))
        try:
            state = await reader.read()
            assert state.globally_disabled is True
            assert state.disabled_reason == "operator_disable_all"
        finally:
            await reader.close()

    asyncio.run(_read())


def test_disable_all_with_zero_enabled_is_a_noop(
    workspace: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    wishlist_path, data_dir = workspace
    # First disable the lone enabled entry.
    phase2_cmd.run_disable(
        query="CT16G4DFD832A",
        all_entries=False,
        wishlist_path=wishlist_path,
        data_dir=data_dir,
        is_tty=lambda: True,
    )
    capsys.readouterr()
    code = phase2_cmd.run_disable(
        query=None,
        all_entries=True,
        wishlist_path=wishlist_path,
        data_dir=data_dir,
        is_tty=lambda: True,
        input_fn=lambda _prompt: "0",
    )
    assert code == 0
    assert "no entries currently have Phase 2 enabled" in capsys.readouterr().out


# ─────────────────────────────────────────────────────────────────────────
# phase2 status
# ─────────────────────────────────────────────────────────────────────────


def test_status_human_shows_rows_and_footer(
    workspace: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    wishlist_path, data_dir = workspace
    code = phase2_cmd.run_status(
        wishlist_path=wishlist_path,
        data_dir=data_dir,
        output_format="human",
        width=200,
    )
    assert code == 0
    out = capsys.readouterr().out
    # Every entry appears in the rendered table.
    assert "WD Red Plus 4TB" in out
    assert "16GB DDR4 3200" in out
    assert "IronWolf 8TB" in out
    # The Crucial row reads yes (currently enabled in the fixture).
    assert "yes" in out
    # Footer carries the three pieces the AC names.
    assert "Globally disabled:" in out
    assert "Circuit: closed" in out
    assert "Last smoke:" in out


def test_status_json_emits_a_parseable_object(
    workspace: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    wishlist_path, data_dir = workspace
    code = phase2_cmd.run_status(
        wishlist_path=wishlist_path,
        data_dir=data_dir,
        output_format="json",
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    refs = [e["entry_key"][2] for e in payload["entries"]]
    assert refs == ["WD40EFPX", "CT16G4DFD832A", "ST8000VN004"]
    assert payload["globally_disabled"] is False
    assert payload["consecutive_failures"] == 0
    enabled_row = next(e for e in payload["entries"] if e["entry_key"][2] == "CT16G4DFD832A")
    assert enabled_row["phase2_enabled"] is True


def test_status_unknown_format_is_usage_error(
    workspace: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    wishlist_path, data_dir = workspace
    code = phase2_cmd.run_status(
        wishlist_path=wishlist_path,
        data_dir=data_dir,
        output_format="yaml",
    )
    assert code == 2
    assert "unknown --format" in capsys.readouterr().err
