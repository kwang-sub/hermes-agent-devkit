#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Callable

RECOVERY_REASON = "DEVKIT_CONTAINER_RESTART"
UNVERIFIED_FINGERPRINT = "unverified"
PROFILE_ROOT = Path("/opt/data/profiles")


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return getattr(row, key, default)


def _fingerprint_epoch(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or value == UNVERIFIED_FINGERPRINT or "|" not in value:
        return None
    epoch, start = value.rsplit("|", 1)
    return epoch if epoch and start else None


def _profile_available(assignee: Any, profile_root: Path = PROFILE_ROOT) -> bool:
    name = str(assignee or "").strip()
    if not name:
        return False
    if name == "default":
        return True
    return (profile_root / name).is_dir()


def _workspace_available(workspace_path: Any) -> bool:
    value = str(workspace_path or "").strip()
    return bool(value) and Path(value).is_dir()


def classify_running_task(
    row: Any,
    *,
    current_epoch: str,
    worker_alive: Callable[[int, Any], bool],
    profile_available: Callable[[Any], bool] = _profile_available,
    workspace_available: Callable[[Any], bool] = _workspace_available,
) -> tuple[str, str, str | None]:
    """Return (action, reason, recorded_epoch).

    Only a worker fingerprint from a previous container/VM instantiation is
    auto-reclaimed. Everything ambiguous is preserved for upstream/manual
    recovery so boot never steals a possibly-live claim.
    """
    if _row_get(row, "status") != "running":
        return "preserve", "NOT_RUNNING", None

    current_epoch = str(current_epoch or "").strip()
    if not current_epoch:
        return "uncertain", "CURRENT_EPOCH_UNAVAILABLE", None

    if _row_get(row, "current_run_id") is None:
        return "uncertain", "CURRENT_RUN_MISSING", None

    pid = _row_get(row, "worker_pid")
    if not pid:
        return "uncertain", "WORKER_PID_MISSING", None

    fingerprint = _row_get(row, "worker_started_at")
    if fingerprint == UNVERIFIED_FINGERPRINT:
        return "uncertain", "WORKER_FINGERPRINT_UNVERIFIED", None

    recorded_epoch = _fingerprint_epoch(fingerprint)
    if not recorded_epoch:
        return "uncertain", "WORKER_FINGERPRINT_LEGACY", None

    try:
        alive = bool(worker_alive(int(pid), fingerprint))
    except Exception:
        return "uncertain", "WORKER_LIVENESS_CHECK_FAILED", recorded_epoch

    if alive:
        return "preserve", "WORKER_ALIVE", recorded_epoch

    if recorded_epoch == current_epoch:
        # A same-epoch dead worker is a normal crash/stale-worker concern owned
        # by the upstream dispatcher. Boot recovery only repairs restart orphans.
        return "uncertain", "DEAD_WORKER_CURRENT_EPOCH", recorded_epoch

    if not profile_available(_row_get(row, "assignee")):
        return "uncertain", "ASSIGNEE_PROFILE_UNAVAILABLE", recorded_epoch

    if not workspace_available(_row_get(row, "workspace_path")):
        return "uncertain", "WORKSPACE_UNAVAILABLE", recorded_epoch

    return "reclaim", "PREVIOUS_INSTANTIATION_DEAD_WORKER", recorded_epoch


def _load_runtime():
    from gateway.drain_control import current_instantiation_epoch
    from hermes_cli import kanban_db as kb
    from hermes_cli import kanban_db_connect as kbc
    from hermes_cli import kanban_db_dispatch as kbd

    return kb, kbc, kbd, current_instantiation_epoch


def recover(*, dry_run: bool = False) -> int:
    kb, kbc, kbd, current_instantiation_epoch = _load_runtime()
    current_epoch = str(current_instantiation_epoch() or "").strip()
    if not current_epoch:
        print("[BOOT-RECOVERY] current instantiation epoch unavailable; no tasks reclaimed")
        return 0

    scanned = reclaimed = preserved = uncertain = board_errors = 0
    seen_db_paths: set[str] = set()

    for board in kb.list_boards(include_archived=False):
        slug = str(board.get("slug") or "default")
        db_path = str(board.get("db_path") or kb.kanban_db_path(slug))
        resolved = str(Path(db_path).resolve())
        if resolved in seen_db_paths:
            continue
        seen_db_paths.add(resolved)

        try:
            with kbc.connect_closing(db_path=Path(db_path)) as conn:
                rows = conn.execute(
                    "SELECT id, status, assignee, workspace_kind, workspace_path, "
                    "current_run_id, worker_pid, worker_started_at, claim_lock "
                    "FROM tasks WHERE status = 'running'"
                ).fetchall()

                for row in rows:
                    scanned += 1
                    action, reason, recorded_epoch = classify_running_task(
                        row,
                        current_epoch=current_epoch,
                        worker_alive=kbd._worker_alive,
                    )
                    task_id = str(_row_get(row, "id"))
                    run_id = _row_get(row, "current_run_id")
                    pid = _row_get(row, "worker_pid")

                    if action == "preserve":
                        preserved += 1
                        continue

                    if action == "uncertain":
                        uncertain += 1
                        print(
                            f"[BOOT-RECOVERY] board={slug} task={task_id} run={run_id} "
                            f"pid={pid} action=PRESERVE reason={reason}"
                        )
                        continue

                    if dry_run:
                        reclaimed += 1
                        print(
                            f"[BOOT-RECOVERY] board={slug} task={task_id} run={run_id} "
                            f"pid={pid} action=WOULD_RECLAIM reason={RECOVERY_REASON} "
                            f"recorded_epoch={recorded_epoch} current_epoch={current_epoch}"
                        )
                        continue

                    if kb.reclaim_task(conn, task_id, reason=RECOVERY_REASON):
                        reclaimed += 1
                        after = kb.get_task(conn, task_id)
                        retry_status = getattr(after, "status", "unknown") if after else "unknown"
                        print(
                            f"[BOOT-RECOVERY] board={slug} task={task_id} run={run_id} "
                            f"pid={pid} action=RECLAIMED reason={RECOVERY_REASON} "
                            f"retry_status={retry_status}"
                        )
                    else:
                        uncertain += 1
                        print(
                            f"[BOOT-RECOVERY] board={slug} task={task_id} run={run_id} "
                            f"pid={pid} action=PRESERVE reason=RECLAIM_RACE_OR_STATE_CHANGED"
                        )
        except Exception as exc:
            board_errors += 1
            print(
                f"[BOOT-RECOVERY] board={slug} action=PRESERVE "
                f"reason=BOARD_RECOVERY_ERROR error={type(exc).__name__}"
            )

    mode = "dry-run" if dry_run else "active"
    print(
        f"[BOOT-RECOVERY] mode={mode} scanned={scanned} reclaimed={reclaimed} "
        f"preserved={preserved} uncertain={uncertain} board_errors={board_errors}"
    )
    # Boot recovery is deliberately fail-open. Uncertain state stays untouched
    # and the normal dispatcher/manual recovery path remains authoritative.
    return 0


def self_test() -> int:
    current = "boot-new:100"
    old = "boot-old:50"

    base = {
        "id": "t_demo",
        "status": "running",
        "assignee": "coder",
        "workspace_path": "/workspace/demo",
        "current_run_id": 12,
        "worker_pid": 123,
        "worker_started_at": f"{old}|999",
    }

    action, reason, epoch = classify_running_task(
        base,
        current_epoch=current,
        worker_alive=lambda _pid, _fp: False,
        profile_available=lambda _a: True,
        workspace_available=lambda _p: True,
    )
    assert (action, reason, epoch) == (
        "reclaim",
        "PREVIOUS_INSTANTIATION_DEAD_WORKER",
        old,
    )

    live = dict(base, worker_started_at=f"{current}|999")
    action, reason, _ = classify_running_task(
        live,
        current_epoch=current,
        worker_alive=lambda _pid, _fp: True,
        profile_available=lambda _a: True,
        workspace_available=lambda _p: True,
    )
    assert (action, reason) == ("preserve", "WORKER_ALIVE")

    same_epoch_dead = dict(base, worker_started_at=f"{current}|999")
    action, reason, _ = classify_running_task(
        same_epoch_dead,
        current_epoch=current,
        worker_alive=lambda _pid, _fp: False,
        profile_available=lambda _a: True,
        workspace_available=lambda _p: True,
    )
    assert (action, reason) == ("uncertain", "DEAD_WORKER_CURRENT_EPOCH")

    for fingerprint, expected in (
        (None, "WORKER_FINGERPRINT_LEGACY"),
        ("12345", "WORKER_FINGERPRINT_LEGACY"),
        (UNVERIFIED_FINGERPRINT, "WORKER_FINGERPRINT_UNVERIFIED"),
    ):
        row = dict(base, worker_started_at=fingerprint)
        action, reason, _ = classify_running_task(
            row,
            current_epoch=current,
            worker_alive=lambda _pid, _fp: False,
            profile_available=lambda _a: True,
            workspace_available=lambda _p: True,
        )
        assert (action, reason) == ("uncertain", expected)

    missing_workspace = dict(base)
    action, reason, _ = classify_running_task(
        missing_workspace,
        current_epoch=current,
        worker_alive=lambda _pid, _fp: False,
        profile_available=lambda _a: True,
        workspace_available=lambda _p: False,
    )
    assert (action, reason) == ("uncertain", "WORKSPACE_UNAVAILABLE")

    print("DevKit Kanban boot recovery self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reclaim orphaned running Kanban tasks left by a previous container instantiation."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    return recover(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
