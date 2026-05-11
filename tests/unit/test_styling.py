"""Tests for the CLI rendering helpers — UX-DR16 / UX-DR17 / UX-DR22 / UX-DR31."""

from __future__ import annotations

import io
from collections.abc import Iterator

import pytest
from rich.console import Console
from syrupy.assertion import SnapshotAssertion

from hardware_hunter.observability.styling import (
    THEME,
    ColumnSpec,
    render_prose,
    render_table,
)

# ─────────────────────────────────────────────────────────────────────────
# Test fixtures
# ─────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _force_no_color(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Default: tests run with color disabled so output is deterministic.

    Tests that need to assert color-on behavior override this explicitly
    by deleting the env var and faking ``isatty()``.
    """
    monkeypatch.setenv("NO_COLOR", "1")
    yield


def _render_table_to_text(
    rows: list[dict[str, object]],
    columns: list[ColumnSpec],
    *,
    width: int,
) -> str:
    """Render a table at a specific width to a deterministic text buffer."""
    table = render_table(rows, columns, width=width)
    buf = io.StringIO()
    Console(file=buf, width=width, force_terminal=False, no_color=True).print(table)
    return buf.getvalue()


SAMPLE_ROWS: list[dict[str, object]] = [
    {"event": "poll_started", "marketplace": "wallapop", "latency_ms": 842},
    {"event": "listing_seen", "marketplace": "wallapop", "latency_ms": 1207},
    {"event": "listing_seen", "marketplace": "ebay", "latency_ms": 391},
    {"event": "alert_sent", "marketplace": "wallapop", "latency_ms": None},
    {"event": "poll_finished", "marketplace": "ebay", "latency_ms": 28},
]

SAMPLE_COLUMNS: list[ColumnSpec] = [
    {"key": "event", "header": "event"},
    {"key": "marketplace", "header": "marketplace"},
    {"key": "latency_ms", "header": "latency_ms", "align": "right"},
]


# ─────────────────────────────────────────────────────────────────────────
# THEME contract — UX-DR16
# ─────────────────────────────────────────────────────────────────────────


def test_theme_has_exactly_seven_locked_tokens() -> None:
    assert set(THEME.keys()) == {
        "error",
        "warn",
        "success",
        "info",
        "emphasis",
        "secondary",
        "code",
    }
    assert THEME["error"] == "bold red"
    assert THEME["warn"] == "bold yellow"
    assert THEME["success"] == "bold green"
    assert THEME["info"] == "bold blue"
    assert THEME["emphasis"] == "bold"
    assert THEME["secondary"] == "dim"
    assert THEME["code"] == "cyan"


def test_progress_and_status_not_imported() -> None:
    """UX-DR17: ``rich.progress.Progress`` and ``rich.status.Status`` are
    forbidden at v1. The check inspects the AST of the styling module so
    docstrings naming the forbidden surfaces don't trip the assertion."""
    import ast
    import inspect

    from hardware_hunter.observability import styling

    tree = ast.parse(inspect.getsource(styling))
    forbidden_modules = {"rich.progress", "rich.status"}
    forbidden_names = {"Progress", "Status"}

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden_modules, f"forbidden import: from {node.module}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in forbidden_modules, f"forbidden import: {alias.name}"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_names, f"forbidden call: {node.func.id}(…)"


# ─────────────────────────────────────────────────────────────────────────
# render_table — UX-DR16 contract
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("width", [60, 80, 100, 120])
def test_render_table_renders_5x3_at_locked_widths(
    width: int, snapshot: SnapshotAssertion
) -> None:
    """UX-DR31 golden-file regression: rendered text is stable per width."""
    output = _render_table_to_text(SAMPLE_ROWS, SAMPLE_COLUMNS, width=width)
    # syrupy compares against tracked snapshot files in __snapshots__/.
    assert output == snapshot


def test_render_table_uses_minimal_box() -> None:
    table = render_table(SAMPLE_ROWS, SAMPLE_COLUMNS)
    from rich.box import MINIMAL

    assert table.box is MINIMAL
    assert table.show_lines is False
    assert table.header_style == "bold"


def test_render_table_handles_empty_rows() -> None:
    """Empty rows: returns a header-only table; the calling command is
    responsible for the 'no results' message via render_prose."""
    output = _render_table_to_text([], SAMPLE_COLUMNS, width=80)
    assert "event" in output  # header still rendered
    assert "poll_started" not in output


def test_render_table_renders_none_as_em_dash() -> None:
    output = _render_table_to_text(
        [{"event": "alert_sent", "marketplace": "wallapop", "latency_ms": None}],
        SAMPLE_COLUMNS,
        width=80,
    )
    assert "—" in output  # em dash, not the ASCII hyphen


# ─────────────────────────────────────────────────────────────────────────
# render_prose — color independence (UX-DR22)
# ─────────────────────────────────────────────────────────────────────────


def test_render_prose_success_prefix_to_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    render_prose("config validated", style="success")
    captured = capsys.readouterr()
    assert "✓ config validated" in captured.out
    assert captured.err == ""


def test_render_prose_error_prefix_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    render_prose("missing token", style="error")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error: missing token" in captured.err


def test_render_prose_error_hint_renders_on_second_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    render_prose(
        "missing token",
        style="error",
        hint="set TELEGRAM_BOT_TOKEN in .env",
    )
    captured = capsys.readouterr()
    assert "error: missing token" in captured.err
    assert "hint: set TELEGRAM_BOT_TOKEN in .env" in captured.err


def test_render_prose_warn_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    render_prose("rate limit nearing", style="warn")
    captured = capsys.readouterr()
    assert "warn: rate limit nearing" in captured.err


def test_render_prose_info_no_prefix(capsys: pytest.CaptureFixture[str]) -> None:
    render_prose("daemon starting", style="info")
    captured = capsys.readouterr()
    assert captured.out.rstrip() == "daemon starting"


def test_render_prose_no_color_strips_ansi(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """NO_COLOR=1 (set by autouse fixture) must produce zero ANSI escapes."""
    render_prose("missing token", style="error", hint="check .env")
    captured = capsys.readouterr()
    assert "\x1b[" not in captured.err  # no ESC sequences


def test_render_prose_preserves_prefix_when_color_disabled(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The prefix glyph carries semantics independently of color (UX-DR22)."""
    render_prose("ok", style="success")
    render_prose("bad", style="error")
    render_prose("careful", style="warn")
    captured = capsys.readouterr()
    assert "✓ ok" in captured.out
    assert "error: bad" in captured.err
    assert "warn: careful" in captured.err
