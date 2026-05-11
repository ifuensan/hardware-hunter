"""Tests for ``scripts/adapter_discipline_lint.py`` — NFR-M1 enforcement.

Verifies the lint:

- Passes on a clean source tree (the actual project state).
- Fails when a synthetic violation is introduced in a non-adapter package.
- Allows the same import inside ``adapters/``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LINT_SCRIPT = REPO_ROOT / "scripts" / "adapter_discipline_lint.py"


def _run_lint() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LINT_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_lint_passes_on_clean_tree() -> None:
    result = _run_lint()
    assert result.returncode == 0, (
        f"Expected clean exit; got {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "OK adapter discipline lint passed" in result.stdout


def test_lint_fails_on_httpx_import_in_domain(tmp_path: Path) -> None:
    """Synthetic violation: ``import httpx`` inside ``domain/listing.py``."""
    violating = REPO_ROOT / "src" / "hardware_hunter" / "domain" / "_test_violation.py"
    try:
        violating.write_text("import httpx  # pragma: violation\n", encoding="utf-8")
        result = _run_lint()
        assert result.returncode == 1, (
            "Expected lint to fail with exit 1 when a deny-listed import "
            f"appears in domain/. Got exit {result.returncode}.\nstderr:\n{result.stderr}"
        )
        assert "_test_violation.py" in result.stderr
        assert "httpx" in result.stderr
        assert "NFR-M1" in result.stderr
    finally:
        if violating.exists():
            violating.unlink()


def test_lint_allows_denied_import_inside_adapters(tmp_path: Path) -> None:
    """Same import is allowed inside ``adapters/``."""
    target_dir = REPO_ROOT / "src" / "hardware_hunter" / "adapters" / "_test_allowed"
    target_file = target_dir / "ok.py"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "__init__.py").write_text("", encoding="utf-8")
        target_file.write_text("import httpx  # adapter-allowed\n", encoding="utf-8")
        result = _run_lint()
        assert result.returncode == 0, (
            f"Expected clean exit when deny-listed import is inside adapters/. "
            f"stderr:\n{result.stderr}"
        )
    finally:
        if target_file.exists():
            target_file.unlink()
        if (target_dir / "__init__.py").exists():
            (target_dir / "__init__.py").unlink()
        if target_dir.exists():
            target_dir.rmdir()


def test_lint_detects_from_import() -> None:
    """``from telegram import Bot`` form is also caught."""
    violating = REPO_ROOT / "src" / "hardware_hunter" / "cli" / "_test_violation.py"
    try:
        violating.write_text("from telegram import Bot\n", encoding="utf-8")
        result = _run_lint()
        assert result.returncode == 1
        assert "_test_violation.py" in result.stderr
        assert "telegram" in result.stderr
    finally:
        if violating.exists():
            violating.unlink()
