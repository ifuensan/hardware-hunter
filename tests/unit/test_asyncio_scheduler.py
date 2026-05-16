"""Tests for :class:`AsyncioScheduler` — Story 3.8 (alpha pivot).

Speed seam
----------
The scheduler treats ``cadence_minutes`` as a unit count, multiplied
by ``seconds_per_cadence_unit`` (default 60) to get sleep length.
Tests override ``seconds_per_cadence_unit`` to a sub-second value so a
cadence of "1 minute" elapses in ~10 ms — enough wall-clock to let
the asyncio scheduler interleave but fast enough to keep the suite
under a second.
"""

from __future__ import annotations

import asyncio

import pytest

from salvager.adapters.asyncio_scheduler import AsyncioScheduler
from salvager.interfaces.scheduler import SchedulerTask

# 100 µs per "cadence minute" — fast cycles, deterministic ordering.
_FAST_UNIT_S = 0.0001


def _make_scheduler(*, shutdown_timeout_s: float = 1.0) -> AsyncioScheduler:
    return AsyncioScheduler(
        shutdown_timeout_s=shutdown_timeout_s,
        seconds_per_cadence_unit=_FAST_UNIT_S,
    )


def _counting_task(counter: list[int]) -> SchedulerTask:
    """Return a task that appends ``1`` to ``counter`` each time it's awaited."""

    async def _run() -> None:
        counter.append(1)

    return _run


async def _wait_for_at_least(counter: list[int], threshold: int, *, timeout_s: float) -> None:
    """Spin-wait (with asyncio yields) until ``len(counter) >= threshold``."""
    deadline = asyncio.get_event_loop().time() + timeout_s
    while len(counter) < threshold:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(
                f"counter only reached {len(counter)}/{threshold} within {timeout_s}s"
            )
        await asyncio.sleep(_FAST_UNIT_S)


# ─────────────────────────────────────────────────────────────────────────
# register — happy path
# ─────────────────────────────────────────────────────────────────────────


async def test_register_starts_a_loop_that_fires_repeatedly() -> None:
    scheduler = _make_scheduler()
    calls: list[int] = []
    try:
        await scheduler.register("wallapop_poll", cadence_minutes=1, task=_counting_task(calls))
        await _wait_for_at_least(calls, 3, timeout_s=1.0)
        assert len(calls) >= 3
    finally:
        await scheduler.shutdown()


async def test_register_validates_positive_cadence() -> None:
    scheduler = _make_scheduler()
    calls: list[int] = []
    try:
        with pytest.raises(ValueError, match="cadence_minutes must be positive"):
            await scheduler.register("bad", cadence_minutes=0, task=_counting_task(calls))
        with pytest.raises(ValueError):
            await scheduler.register("bad", cadence_minutes=-1, task=_counting_task(calls))
    finally:
        await scheduler.shutdown()


async def test_two_jobs_register_with_independent_cadences() -> None:
    scheduler = _make_scheduler()
    a_calls: list[int] = []
    b_calls: list[int] = []
    try:
        await scheduler.register("wallapop_poll", cadence_minutes=1, task=_counting_task(a_calls))
        await scheduler.register("ebay_poll", cadence_minutes=2, task=_counting_task(b_calls))
        await _wait_for_at_least(a_calls, 4, timeout_s=1.0)
        # b should have fired at least twice in the time a fired four times
        # (cadence is half; allow some scheduling slack).
        assert len(b_calls) >= 2
        # a's fire rate is higher than b's.
        assert len(a_calls) >= len(b_calls)
    finally:
        await scheduler.shutdown()


# ─────────────────────────────────────────────────────────────────────────
# Re-registration (config-rescan path)
# ─────────────────────────────────────────────────────────────────────────


async def test_re_register_replaces_existing_loop() -> None:
    """Re-registering the same job_name cancels the old loop and runs
    the new callable at the new cadence."""
    scheduler = _make_scheduler()
    old_calls: list[int] = []
    new_calls: list[int] = []
    try:
        await scheduler.register("wallapop_poll", cadence_minutes=5, task=_counting_task(old_calls))
        # Let the slow loop start.
        await asyncio.sleep(_FAST_UNIT_S * 6)
        old_count_before_replace = len(old_calls)

        await scheduler.register("wallapop_poll", cadence_minutes=1, task=_counting_task(new_calls))
        await _wait_for_at_least(new_calls, 5, timeout_s=1.0)

        # The new (faster) callable fires at the new cadence.
        assert len(new_calls) >= 5
        # The old callable stops getting called once replaced (allow a couple
        # of in-flight calls; the key is that growth halts).
        snapshot = len(old_calls)
        await asyncio.sleep(_FAST_UNIT_S * 50)
        assert len(old_calls) <= snapshot + 1  # at most one in-flight finished
        _ = old_count_before_replace  # silence unused
    finally:
        await scheduler.shutdown()


async def test_re_register_logs_re_registered_with_old_and_new_cadence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import json

    scheduler = _make_scheduler()
    try:

        async def _noop() -> None:
            return None

        await scheduler.register("wallapop_poll", cadence_minutes=15, task=_noop)
        # Drain stdout from the first registration.
        capsys.readouterr()
        await scheduler.register("wallapop_poll", cadence_minutes=10, task=_noop)
        out = capsys.readouterr().out
    finally:
        await scheduler.shutdown()

    records = [json.loads(line) for line in out.splitlines() if line.strip()]
    re_reg = [r for r in records if r["event"] == "scheduler_job_re_registered"]
    assert re_reg, f"missing scheduler_job_re_registered in {records!r}"
    assert re_reg[0]["job_name"] == "wallapop_poll"
    assert re_reg[0]["old_cadence_minutes"] == 15
    assert re_reg[0]["new_cadence_minutes"] == 10


# ─────────────────────────────────────────────────────────────────────────
# Structured logging — scheduler_started fires once with both jobs
# ─────────────────────────────────────────────────────────────────────────


async def test_first_register_emits_scheduler_started_with_jobs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import json

    scheduler = _make_scheduler()
    try:

        async def _noop() -> None:
            return None

        await scheduler.register("wallapop_poll", cadence_minutes=15, task=_noop)
        await scheduler.register("ebay_poll", cadence_minutes=30, task=_noop)
        out = capsys.readouterr().out
    finally:
        await scheduler.shutdown()

    records = [json.loads(line) for line in out.splitlines() if line.strip()]
    started = [r for r in records if r["event"] == "scheduler_started"]
    # scheduler_started fires exactly once — on the FIRST register call.
    assert len(started) == 1, f"expected one scheduler_started, got {len(started)}"
    # That snapshot only contains the first job at the moment of firing.
    job_names = [job["name"] for job in started[0]["jobs"]]
    assert "wallapop_poll" in job_names


# ─────────────────────────────────────────────────────────────────────────
# Exception isolation — bad cycle does not kill the loop
# ─────────────────────────────────────────────────────────────────────────


async def test_exception_in_task_logs_and_loop_continues(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import json

    scheduler = _make_scheduler()
    counter = {"calls": 0}

    async def _flaky() -> None:
        counter["calls"] += 1
        if counter["calls"] == 2:
            raise RuntimeError("boom")

    try:
        await scheduler.register("flaky", cadence_minutes=1, task=_flaky)
        # Wait for at least 4 cycles — the loop must keep ticking after the boom.
        deadline = asyncio.get_event_loop().time() + 1.0
        while counter["calls"] < 4:
            if asyncio.get_event_loop().time() > deadline:
                pytest.fail(f"loop stalled after exception (count={counter['calls']})")
            await asyncio.sleep(_FAST_UNIT_S)
        out = capsys.readouterr().out
    finally:
        await scheduler.shutdown()

    records = [json.loads(line) for line in out.splitlines() if line.strip()]
    exc = [r for r in records if r["event"] == "scheduler_job_exception"]
    assert exc, "scheduler_job_exception was not logged"
    assert exc[0]["error_class"] == "RuntimeError"
    assert exc[0]["job_name"] == "flaky"


# ─────────────────────────────────────────────────────────────────────────
# Shutdown — drain in-flight + cancel pending
# ─────────────────────────────────────────────────────────────────────────


async def test_shutdown_drains_in_flight_cycle() -> None:
    """A task that's mid-await when shutdown is called gets to finish."""
    scheduler = _make_scheduler(shutdown_timeout_s=1.0)
    finished = asyncio.Event()
    started = asyncio.Event()

    async def _slow() -> None:
        started.set()
        await asyncio.sleep(0.05)  # 50 ms — well under shutdown timeout
        finished.set()

    try:
        await scheduler.register("slow", cadence_minutes=1, task=_slow)
        await asyncio.wait_for(started.wait(), timeout=1.0)
        # Mid-flight: trigger shutdown.
        await scheduler.shutdown()
        # The in-flight task completed before shutdown returned.
        assert finished.is_set()
    finally:
        # second shutdown is a no-op; safe to call.
        await scheduler.shutdown()


async def test_shutdown_cancels_tasks_exceeding_timeout() -> None:
    """A task that overruns the shutdown budget gets force-cancelled."""
    scheduler = _make_scheduler(shutdown_timeout_s=0.05)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def _hung() -> None:
        started.set()
        try:
            await asyncio.sleep(10.0)  # would outlast the test
        except asyncio.CancelledError:
            cancelled.set()
            raise

    try:
        await scheduler.register("hung", cadence_minutes=1, task=_hung)
        await asyncio.wait_for(started.wait(), timeout=1.0)
        await scheduler.shutdown()
        assert cancelled.is_set()
    finally:
        pass  # already shut down


async def test_shutdown_emits_scheduler_stopped_event(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import json

    scheduler = _make_scheduler()

    async def _noop() -> None:
        return None

    await scheduler.register("wallapop_poll", cadence_minutes=1, task=_noop)
    capsys.readouterr()  # drain register output
    await scheduler.shutdown()
    out = capsys.readouterr().out

    records = [json.loads(line) for line in out.splitlines() if line.strip()]
    stopped = [r for r in records if r["event"] == "scheduler_stopped"]
    assert stopped, f"missing scheduler_stopped in {records!r}"
    assert "wallapop_poll" in stopped[0]["jobs"]


async def test_register_after_shutdown_is_a_noop_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import json

    scheduler = _make_scheduler()
    counter: list[int] = []

    async def _noop() -> None:
        counter.append(1)

    await scheduler.shutdown()
    capsys.readouterr()  # drain
    await scheduler.register("late", cadence_minutes=1, task=_noop)
    # Loop never spun up — counter stays empty even after a generous wait.
    await asyncio.sleep(_FAST_UNIT_S * 50)
    assert counter == []
    out = capsys.readouterr().out
    records = [json.loads(line) for line in out.splitlines() if line.strip()]
    warn = [r for r in records if r["event"] == "scheduler_register_after_shutdown"]
    assert warn, "missing scheduler_register_after_shutdown log"


# ─────────────────────────────────────────────────────────────────────────
# Adapter discipline — asyncio_scheduler stays pure (no Hermes deps)
# ─────────────────────────────────────────────────────────────────────────


def test_asyncio_scheduler_does_not_import_hermes_or_subprocess() -> None:
    """The alpha pivot: this adapter is in-process only. No `hermes`, no
    `subprocess`, no network libs. If a future refactor wants to add
    them, it should go in a NEW adapter, not muddy this one."""
    import ast
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "salvager"
        / "adapters"
        / "asyncio_scheduler"
        / "scheduler.py"
    )
    tree = ast.parse(source.read_text(encoding="utf-8"))
    forbidden = {"subprocess", "hermes_agent", "hermes", "httpx", "mcp"}
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in forbidden:
                    bad.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            if top in forbidden:
                bad.append(f"from {node.module} import ...")
    assert not bad, "asyncio_scheduler accidentally pulled in a non-pure dep: " + ", ".join(bad)
