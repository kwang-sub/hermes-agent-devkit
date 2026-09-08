#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enqueue one DevKit Kanban registration event after notification subscription."
    )
    parser.add_argument("--board", required=True)
    parser.add_argument("--task-id", required=True)
    return parser.parse_args()


def fail(reason: str) -> int:
    print("REGISTRATION_EVENT_STATUS=failed")
    print(f"REGISTRATION_EVENT_ERROR={reason}")
    return 1


def main() -> int:
    args = parse_args()
    board = args.board.strip()
    task_id = args.task_id.strip()
    if not board or not task_id:
        return fail("board and task-id are required")

    try:
        from hermes_cli import kanban_db as kb
        from hermes_cli import kanban_db_connect as kbc
    except Exception as exc:
        return fail(f"Hermes Kanban modules unavailable: {type(exc).__name__}")

    conn = None
    try:
        conn = kbc.connect(board=board)
        task = kb.get_task(conn, task_id)
        if task is None:
            return fail(f"task not found on board '{board}': {task_id}")

        # Idempotent by task: dispatch may resume after a transient subscription
        # failure, but the user should receive at most one first-registration event.
        exists = conn.execute(
            "SELECT 1 FROM task_events WHERE task_id = ? AND kind = 'registered' LIMIT 1",
            (task_id,),
        ).fetchone()
        if exists:
            print("REGISTRATION_EVENT_STATUS=existing")
            print(f"REGISTRATION_EVENT_BOARD={board}")
            print(f"REGISTRATION_EVENT_TASK={task_id}")
            return 0

        payload = json.dumps(
            {
                "source": "devkit-standard-flow",
                "status": str(getattr(task, "status", "blocked") or "blocked"),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        with kb.write_txn(conn):
            conn.execute(
                "INSERT INTO task_events (task_id, run_id, kind, payload, created_at) "
                "VALUES (?, NULL, 'registered', ?, ?)",
                (task_id, payload, int(time.time())),
            )

        print("REGISTRATION_EVENT_STATUS=queued")
        print(f"REGISTRATION_EVENT_BOARD={board}")
        print(f"REGISTRATION_EVENT_TASK={task_id}")
        return 0
    except Exception as exc:
        return fail(f"{type(exc).__name__}: {exc}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
