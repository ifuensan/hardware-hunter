""":class:`AsyncioScheduler` — Story 3.8 (FR8 + NFR-I1 alpha pivot).

The poll-loop orchestrator (Story 3.14) registers per-marketplace
polling jobs against the :class:`Scheduler` ABC; this adapter is the
v0.x implementation backing that port with a pure :mod:`asyncio`
runtime.

Design pivot
------------
Hermes' built-in ``cron`` primitive fires subprocesses, while the
:class:`Scheduler.register` signature takes an async Python callable.
At v0.x we satisfy the ABC contract entirely in-process — see the
``project_scheduler_design_pivot`` memory note for the trade-off
analysis and the future-migration outline.

Re-registration semantics
-------------------------
:meth:`AsyncioScheduler.register` is idempotent on ``job_name``.
Calling it a second time with the same name CANCELS the previous
job-loop task and starts a fresh one with the new cadence. Story
3.8's config-rescan re-registration AC is satisfied by this shape:
the daemon detects ``config.yaml`` cadence changes on its 30-second
tick and re-issues :meth:`register` for the affected job.

Exception isolation
-------------------
A single bad cycle MUST NOT kill the loop (per the orchestration
design philosophy). Every ``await task()`` is wrapped — the
exception is recorded as ``scheduler_job_exception`` in the
structured log and the loop continues at the next cadence tick.

Shutdown contract
-----------------
:meth:`shutdown` sets an internal event, lets every in-flight cycle
complete (up to FR50's 30-second budget), then cancels any
still-running cycle. The event also short-circuits the inter-cycle
sleep so the loops wake immediately when the daemon is signalled.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import Final

from salvager.interfaces.scheduler import Scheduler, SchedulerTask
from salvager.observability.logging import get_logger

#: FR50: SIGTERM has 30 seconds to drain in-flight work before forced cancel.
DEFAULT_SHUTDOWN_TIMEOUT_S: Final[float] = 30.0

#: Number of seconds per ``cadence_minutes`` unit. The constant is the
#: test seam: tests override it to a sub-second value so a cadence of
#: "1 minute" elapses in milliseconds, letting the loop iterate many
#: times without slowing the suite.
_SECONDS_PER_CADENCE_UNIT_DEFAULT: Final[float] = 60.0


@dataclass
class _JobState:
    """Bookkeeping for one registered job."""

    cadence_minutes: int
    task: SchedulerTask
    loop_task: asyncio.Task[None]


class AsyncioScheduler(Scheduler):
    """In-process :class:`Scheduler` driven by ``asyncio.create_task``.

    The class is owned by the daemon entry point (Story 3.14 wiring).
    Construction is lightweight; calling :meth:`register` is what
    actually starts the work.
    """

    def __init__(
        self,
        *,
        shutdown_timeout_s: float = DEFAULT_SHUTDOWN_TIMEOUT_S,
        seconds_per_cadence_unit: float = _SECONDS_PER_CADENCE_UNIT_DEFAULT,
    ) -> None:
        self._jobs: dict[str, _JobState] = {}
        self._shutdown_event = asyncio.Event()
        self._shutdown_timeout_s = shutdown_timeout_s
        self._seconds_per_cadence_unit = seconds_per_cadence_unit
        self._started = False
        self._log = get_logger("adapter.asyncio_scheduler")

    # ─────────────────────────────────────────────────────────────────
    # Scheduler — register / shutdown
    # ─────────────────────────────────────────────────────────────────

    async def register(
        self,
        job_name: str,
        cadence_minutes: int,
        task: SchedulerTask,
    ) -> None:
        if cadence_minutes <= 0:
            raise ValueError(f"cadence_minutes must be positive; got {cadence_minutes}")
        if self._shutdown_event.is_set():
            # After shutdown register is a no-op (per ABC docstring
            # "may either no-op or raise" — we pick no-op so a late
            # config-rescan tick doesn't crash the daemon).
            self._log.warning(
                "scheduler_register_after_shutdown",
                extra={"job_name": job_name},
            )
            return

        existing = self._jobs.get(job_name)
        if existing is not None:
            await self._cancel_loop_task(existing.loop_task)
            self._log.info(
                "scheduler_job_re_registered",
                extra={
                    "job_name": job_name,
                    "old_cadence_minutes": existing.cadence_minutes,
                    "new_cadence_minutes": cadence_minutes,
                },
            )
        else:
            self._log.info(
                "scheduler_job_registered",
                extra={
                    "job_name": job_name,
                    "cadence_minutes": cadence_minutes,
                },
            )

        loop_task = asyncio.create_task(
            self._job_loop(job_name, cadence_minutes, task),
            name=f"scheduler:{job_name}",
        )
        self._jobs[job_name] = _JobState(
            cadence_minutes=cadence_minutes,
            task=task,
            loop_task=loop_task,
        )

        if not self._started:
            self._started = True
            self._log.info(
                "scheduler_started",
                extra={
                    "jobs": [
                        {"name": name, "cadence_minutes": state.cadence_minutes}
                        for name, state in self._jobs.items()
                    ],
                },
            )

    async def shutdown(self) -> None:
        """Stop accepting new work; let in-flight cycles drain.

        FR50 budget is bounded by ``shutdown_timeout_s``. Anything still
        running after the budget elapses gets a hard :meth:`asyncio.Task.cancel`.
        """
        self._shutdown_event.set()
        loop_tasks = [state.loop_task for state in self._jobs.values()]
        if loop_tasks:
            done, pending = await asyncio.wait(loop_tasks, timeout=self._shutdown_timeout_s)
            for late in pending:
                late.cancel()
            for late in pending:
                # We're shutting down — never propagate.
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await late
            self._log.info(
                "scheduler_stopped",
                extra={
                    "jobs": list(self._jobs),
                    "drained": len(done),
                    "cancelled": len(pending),
                },
            )
        else:
            self._log.info("scheduler_stopped", extra={"jobs": []})

    # ─────────────────────────────────────────────────────────────────
    # Internals
    # ─────────────────────────────────────────────────────────────────

    async def _job_loop(
        self,
        job_name: str,
        cadence_minutes: int,
        task: SchedulerTask,
    ) -> None:
        """Run ``task`` every ``cadence_minutes`` minutes until shutdown.

        Exception isolation: a raised :class:`Exception` is logged and
        the loop continues at the next cadence tick. Only
        :class:`asyncio.CancelledError` aborts the loop (via
        ``shutdown``'s timeout-pending-cancel path).
        """
        cadence_seconds = float(cadence_minutes) * self._seconds_per_cadence_unit
        while not self._shutdown_event.is_set():
            self._log.info("scheduler_job_started", extra={"job_name": job_name})
            try:
                await task()
            except Exception as exc:
                self._log.error(
                    "scheduler_job_exception",
                    extra={
                        "job_name": job_name,
                        "error_class": exc.__class__.__name__,
                    },
                )
            else:
                self._log.info("scheduler_job_finished", extra={"job_name": job_name})

            # Interruptible sleep: wakes on shutdown so the loop ends
            # promptly when the daemon is signalled.
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=cadence_seconds)
                return  # shutdown signalled mid-sleep
            except TimeoutError:
                continue  # cadence elapsed, run another cycle

    @staticmethod
    async def _cancel_loop_task(loop_task: asyncio.Task[None]) -> None:
        """Cancel a per-job loop task and await its termination."""
        loop_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await loop_task


__all__ = [
    "DEFAULT_SHUTDOWN_TIMEOUT_S",
    "AsyncioScheduler",
]
