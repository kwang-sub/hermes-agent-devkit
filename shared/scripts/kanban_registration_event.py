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


def row_id(row: object) -> int:
    try:
        return int(row["id"])  # type: ignore[index]
    except (KeyError, TypeError):
        return int(row[0])  # type: ignore[index]


def print_success(*, status: str, board: str, task_id: str, event_id: int) -> int:
    print(f"REGISTRATION_EVENT_STATUS={status}")
    print(f"REGISTRATION_EVENT_ID={event_id}")
    print(f"REGISTRATION_EVENT_BOARD={board}")
    print(f"REGISTRATION_EVENT_TASK={task_id}")
    return 0


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
        # or delivery failure, but the user should receive at most one logical
        # first-registration event. Return the durable event id on every retry so
        # the caller can wait for the matching delivery acknowledgement.
        exists = conn.execute(
            "SELECT id FROM task_events "
            "WHERE task_id = ? AND kind = 'registered' ORDER BY id ASC LIMIT 1",
            (task_id,),
        ).fetchone()
        if exists:
            return print_success(
                status="existing",
                board=board,
                task_id=task_id,
                event_id=row_id(exists),
            )

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
            cursor = conn.execute(
                "INSERT INTO task_events (task_id, run_id, kind, payload, created_at) "
                "VALUES (?, NULL, 'registered', ?, ?)",
                (task_id, payload, int(time.time())),
            )
            event_id = int(cursor.lastrowid)

        return print_success(
            status="queued",
            board=board,
            task_id=task_id,
            event_id=event_id,
        )
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
