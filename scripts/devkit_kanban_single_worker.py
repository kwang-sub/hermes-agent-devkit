#!/usr/bin/env python3
"""Prevent a new Kanban worker from overlapping a still-live prior run.

Hermes already serializes ready->running claims. This guard closes a narrower
handoff gap: a run may have been terminally closed/reclaimed while its host-local
process is still alive. Re-queueing the task in that window must not spawn a
second worker into the same workspace.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
import time
from typing import Callable, Optional

UNKNOWN_PROCESS_GRACE_SECONDS = 120
RECENT_RUN_LIMIT = 8


@dataclass(frozen=True)
class PriorWorker:
    run_id: int
    pid: int
    ended_at: int


def _linux_process_task_match(pid: int, task_id: str) -> Optional[bool]:
    """Return whether ``pid`` still carries this Kanban task assignment.

    ``None`` means the process environment could not be inspected. The caller
    handles that case conservatively only for a short post-run grace period.
    """
    if os.name != "posix" or not sys_platform_linux():
        return None
    try:
        raw = (Path("/proc") / str(int(pid)) / "environ").read_bytes()
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return None
    expected = f"HERMES_KANBAN_TASK={task_id}".encode()
    return expected in raw.split(b"\0")


def sys_platform_linux() -> bool:
    # Isolated helper so the self-test can stay platform-independent.
    import sys

    return sys.platform == "linux"


def live_prior_worker(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    pid_alive: Callable[[int], bool],
    host_prefix: str,
    process_task_match: Optional[Callable[[int, str], Optional[bool]]] = None,
    now: Optional[int] = None,
    unknown_process_grace_seconds: int = UNKNOWN_PROCESS_GRACE_SECONDS,
) -> Optional[PriorWorker]:
    """Return a still-live host-local worker from a recently ended run.

    A positive process/task identity match has no age limit: if the old worker
    is demonstrably still executing this task, spawning another worker is never
    safe. When process identity cannot be inspected, only a short grace window
    is used to avoid false positives from PID reuse.
    """
    task_id = str(task_id or "").strip()
    prefix = str(host_prefix or "").strip()
    if not task_id or not prefix:
        return None

    matcher = process_task_match or _linux_process_task_match
    current_time = int(time.time()) if now is None else int(now)
    try:
        rows = conn.execute(
            """
            SELECT id, worker_pid, claim_lock, ended_at
              FROM task_runs
             WHERE task_id = ?
               AND worker_pid IS NOT NULL
               AND ended_at IS NOT NULL
             ORDER BY id DESC
             LIMIT ?
            """,
            (task_id, RECENT_RUN_LIMIT),
        ).fetchall()
    except sqlite3.Error:
        # Compatibility fail-open: an older upstream schema must still boot.
        return None

    for row in rows:
        try:
            run_id = int(row["id"])
            pid = int(row["worker_pid"])
            ended_at = int(row["ended_at"])
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        claim_lock = str(row["claim_lock"] or "")
        if pid <= 0 or not claim_lock.startswith(prefix):
            continue
        try:
            if not pid_alive(pid):
                continue
        except Exception:
            continue

        try:
            identity = matcher(pid, task_id)
        except Exception:
            identity = None
        if identity is False:
            # PID exists but belongs to a different process/task: PID reuse.
            continue
        if identity is None and current_time - ended_at > max(0, int(unknown_process_grace_seconds)):
            continue
        return PriorWorker(run_id=run_id, pid=pid, ended_at=ended_at)
    return None


def self_test() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE task_runs(
            id INTEGER PRIMARY KEY,
            task_id TEXT NOT NULL,
            worker_pid INTEGER,
            claim_lock TEXT,
            ended_at INTEGER
        )
        """
    )
    now = 1_000
    conn.executemany(
        "INSERT INTO task_runs(id, task_id, worker_pid, claim_lock, ended_at) VALUES (?, ?, ?, ?, ?)",
        [
            (1, "t_demo", 101, "host-a:lock", 100),
            (2, "t_demo", 102, "host-b:lock", 990),
            (3, "t_demo", 103, "host-a:lock", 995),
        ],
    )

    # Latest host-local worker is alive and positively identified.
    found = live_prior_worker(
        conn,
        "t_demo",
        pid_alive=lambda pid: pid in {101, 102, 103},
        host_prefix="host-a:",
        process_task_match=lambda pid, task: pid == 103 and task == "t_demo",
        now=now,
    )
    assert found == PriorWorker(run_id=3, pid=103, ended_at=995)

    # A live PID belonging to another process is PID reuse, not a task worker.
    assert live_prior_worker(
        conn,
        "t_demo",
        pid_alive=lambda _pid: True,
        host_prefix="host-a:",
        process_task_match=lambda _pid, _task: False,
        now=now,
    ) is None

    # Unknown identity is held only during the short post-run grace period.
    found = live_prior_worker(
        conn,
        "t_demo",
        pid_alive=lambda pid: pid == 103,
        host_prefix="host-a:",
        process_task_match=lambda _pid, _task: None,
        now=now,
        unknown_process_grace_seconds=10,
    )
    assert found == PriorWorker(run_id=3, pid=103, ended_at=995)
    assert live_prior_worker(
        conn,
        "t_demo",
        pid_alive=lambda pid: pid == 101,
        host_prefix="host-a:",
        process_task_match=lambda _pid, _task: None,
        now=now,
        unknown_process_grace_seconds=10,
    ) is None

    # Dead and non-host-local workers never block a new spawn.
    assert live_prior_worker(
        conn,
        "t_demo",
        pid_alive=lambda _pid: False,
        host_prefix="host-a:",
        process_task_match=lambda _pid, _task: True,
        now=now,
    ) is None
    assert live_prior_worker(
        conn,
        "t_demo",
        pid_alive=lambda pid: pid == 102,
        host_prefix="host-a:",
        process_task_match=lambda _pid, _task: True,
        now=now,
    ) is None
    conn.close()
    print("DevKit Kanban single-active-worker runtime self-test passed")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    parser.error("only --self-test is supported")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
