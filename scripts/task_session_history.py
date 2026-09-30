#!/usr/bin/env python3
"""Capture durable Kanban task -> Hermes session history."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sqlite3
import time

AFFINITY_DB_NAME = "devkit-session-affinity.db"


def _text(value: object) -> str:
    return str(value or "").strip()


def _profile_state_db(profile_home: str) -> Path:
    return Path(profile_home) / "state.db"


def _history_db(kanban_db: str) -> Path:
    return Path(kanban_db).resolve().parent / AFFINITY_DB_NAME


def _find_latest_session(*, profile_home: str, task_id: str, workspace: str) -> str | None:
    state = _profile_state_db(profile_home)
    if not state.is_file():
        return None
    conn = sqlite3.connect(f"file:{state.as_posix()}?mode=ro", uri=True, timeout=0.5)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT s.id
              FROM sessions AS s
             WHERE s.source = 'kanban'
               AND (? = '' OR s.cwd = ?)
               AND EXISTS (
                    SELECT 1
                      FROM messages AS m
                     WHERE m.session_id = s.id
                       AND m.role = 'user'
                       AND m.content = ?
               )
             ORDER BY s.started_at DESC
             LIMIT 1
            """,
            (workspace, workspace, f"work kanban task {task_id}"),
        ).fetchone()
        return _text(row["id"]) if row else None
    finally:
        conn.close()


def _open_history(kanban_db: str) -> sqlite3.Connection:
    path = _history_db(kanban_db)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=1.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 1000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS task_session_history (
            task_id TEXT NOT NULL,
            profile TEXT NOT NULL,
            session_id TEXT NOT NULL,
            session_mode TEXT NOT NULL,
            workspace TEXT NOT NULL,
            first_seen_at REAL NOT NULL,
            last_seen_at REAL NOT NULL,
            PRIMARY KEY (task_id, profile, session_id)
        )
        """
    )
    conn.commit()
    return conn


def capture(*, task_id: str, profile: str, profile_home: str, workspace: str, kanban_db: str, session_mode: str) -> tuple[str | None, bool]:
    session_id = _find_latest_session(
        profile_home=profile_home,
        task_id=task_id,
        workspace=workspace,
    )
    if not session_id:
        return None, False

    conn = _open_history(kanban_db)
    try:
        now = time.time()
        existing = conn.execute(
            "SELECT 1 FROM task_session_history WHERE task_id = ? AND profile = ? AND session_id = ?",
            (task_id, profile, session_id),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO task_session_history(
                task_id, profile, session_id, session_mode, workspace, first_seen_at, last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id, profile, session_id) DO UPDATE SET
                session_mode = excluded.session_mode,
                workspace = excluded.workspace,
                last_seen_at = excluded.last_seen_at
            """,
            (task_id, profile, session_id, session_mode, workspace, now, now),
        )
        conn.commit()
        return session_id, existing is None
    finally:
        conn.close()


def list_history(*, task_id: str, kanban_db: str) -> list[sqlite3.Row]:
    conn = _open_history(kanban_db)
    try:
        return conn.execute(
            """
            SELECT task_id, profile, session_id, session_mode, workspace, first_seen_at, last_seen_at
              FROM task_session_history
             WHERE task_id = ?
             ORDER BY first_seen_at ASC, profile ASC, session_id ASC
            """,
            (task_id,),
        ).fetchall()
    finally:
        conn.close()


def _env(name: str) -> str:
    return _text(os.environ.get(name))


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)

    capture_cmd = sub.add_parser("capture")
    capture_cmd.add_argument("--task-id", default=_env("HERMES_KANBAN_TASK"))
    capture_cmd.add_argument("--profile", default=_env("HERMES_PROFILE"))
    capture_cmd.add_argument("--profile-home", default=_env("HERMES_HOME"))
    capture_cmd.add_argument("--workspace", default=_env("HERMES_KANBAN_WORKSPACE"))
    capture_cmd.add_argument("--kanban-db", default=_env("HERMES_KANBAN_DB"))
    capture_cmd.add_argument("--session-mode", default=_env("HERMES_KANBAN_SESSION_MODE") or "UNKNOWN")

    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--task-id", required=True)
    list_cmd.add_argument("--kanban-db", default=_env("HERMES_KANBAN_DB"))

    args = ap.parse_args()

    if args.command == "capture":
        required = {
            "task-id": args.task_id,
            "profile": args.profile,
            "profile-home": args.profile_home,
            "workspace": args.workspace,
            "kanban-db": args.kanban_db,
        }
        missing = [key for key, value in required.items() if not _text(value)]
        if missing:
            raise SystemExit("missing required session context: " + ", ".join(missing))
        session_id, is_new = capture(
            task_id=args.task_id,
            profile=args.profile,
            profile_home=args.profile_home,
            workspace=args.workspace,
            kanban_db=args.kanban_db,
            session_mode=args.session_mode,
        )
        if not session_id:
            print("SESSION_HISTORY_STATUS=unavailable")
            print("SESSION_ID=UNAVAILABLE")
            return 0
        print("SESSION_HISTORY_STATUS=captured")
        print(f"SESSION_HISTORY_NEW={str(is_new).lower()}")
        print(f"SESSION_ID={session_id}")
        print(f"SESSION_PROFILE={args.profile}")
        print(f"SESSION_MODE={args.session_mode}")
        print("SESSION_HISTORY_MARKER_BEGIN")
        print("TASK_SESSION_HISTORY")
        print(f"- Session ID: {session_id}")
        print(f"- Profile: {args.profile}")
        print(f"- Mode: {args.session_mode}")
        print("SESSION_HISTORY_MARKER_END")
        return 0

    if not args.kanban_db:
        raise SystemExit("missing required session context: kanban-db")
    rows = list_history(task_id=args.task_id, kanban_db=args.kanban_db)
    if not rows:
        print("SESSION_HISTORY_STATUS=empty")
        return 0
    print("SESSION_HISTORY_STATUS=ok")
    for row in rows:
        print(
            "SESSION "
            f"profile={row['profile']} "
            f"mode={row['session_mode']} "
            f"id={row['session_id']} "
            f"workspace={row['workspace']}"
        )
    return 0


def self_test() -> None:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="task-session-history-") as directory:
        root = Path(directory)
        profile = root / "profile"
        profile.mkdir()
        state = sqlite3.connect(str(profile / "state.db"))
        state.execute("CREATE TABLE sessions(id TEXT PRIMARY KEY, source TEXT, cwd TEXT, started_at REAL)")
        state.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT)")
        now = time.time()
        state.execute("INSERT INTO sessions VALUES (?, 'kanban', ?, ?)", ("s1", "/workspace/demo", now))
        state.execute("INSERT INTO messages VALUES (1, ?, 'user', ?)", ("s1", "work kanban task t1"))
        state.commit()
        state.close()

        kanban = root / "kanban.db"
        sqlite3.connect(str(kanban)).close()
        session_id, is_new = capture(
            task_id="t1", profile="coder", profile_home=str(profile),
            workspace="/workspace/demo", kanban_db=str(kanban), session_mode="NEW",
        )
        assert session_id == "s1" and is_new
        _, is_new_again = capture(
            task_id="t1", profile="coder", profile_home=str(profile),
            workspace="/workspace/demo", kanban_db=str(kanban), session_mode="RESUME",
        )
        assert not is_new_again
        rows = list_history(task_id="t1", kanban_db=str(kanban))
        assert len(rows) == 1
        assert rows[0]["session_id"] == "s1"
        assert rows[0]["session_mode"] == "RESUME"

    print("task session history self-test passed")


if __name__ == "__main__":
    if "--self-test" in os.sys.argv:
        self_test()
    else:
        raise SystemExit(main())
