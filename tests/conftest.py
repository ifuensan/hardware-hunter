"""Shared pytest configuration.

The ``slow`` marker (registered in ``pyproject.toml``) flags long-running
end-to-end tests — crash/restart consistency, multi-cycle drains. They
are opt-in: a plain ``pytest`` run skips them, ``pytest --runslow`` includes
them. CI runs both, day-to-day local runs stay fast.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="run slow end-to-end tests (marked @pytest.mark.slow)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    if config.getoption("--runslow"):
        return
    skip_slow = pytest.mark.skip(reason="needs --runslow to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
