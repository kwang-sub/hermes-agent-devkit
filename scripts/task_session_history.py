#!/usr/bin/env python3
"""Capture durable Kanban task -> Hermes session history."""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
import math
from pathlib import Path
import sqlite3
import stat
import time

DEFAULT_HISTORY_DB = "/opt/data/devkit-task-session-history.db"
MAX_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 0.5
MAX_RETRY_DELAY = 1.0
STATE_QUERY_TIMEOUT = 0.5


@dataclass(frozen=True)
class CaptureResult:
    status: str
    reason: str
    attempts: int
    session_id: str | None = None
    is_new: bool = False
    comment_pending: bool = False
    error_type: str = ""


class SessionHistoryError(RuntimeError):
    def __init__(self, reason: str, cause: Exception):
        super().__init__(reason)
        self.reason = reason
        self.error_type = type(cause).__name__


def _validate_token(value: str, name: str) -> None:
    if not _text(value) or any(char.isspace() for char in value) or value == "UNAVAILABLE":
        raise ValueError(f"invalid {name}")


def _validate_context(*, task_id: str, profile: str, profile_home: str,
                      workspace: str, history_db: str, session_mode: str) -> None:
    _validate_token(task_id, "task-id")
    if profile not in ("coder", "reviewer") or session_mode not in ("NEW", "RESUME", "UNKNOWN"):
        raise ValueError("invalid profile or session mode")
    for name, value in (("profile-home", profile_home), ("workspace", workspace), ("history-db", history_db)):
        if not _text(value) or not Path(value).is_absolute() or any(c in value for c in "\r\n\0"):
            raise ValueError(f"invalid {name}")
    if _history_db(history_db) == _profile_state_db(profile_home).resolve():
        raise ValueError("history DB must be separate from the Hermes state DB")


def _text(value: object) -> str:
    return str(value or "").strip()


def _profile_state_db(profile_home: str) -> Path:
    return Path(profile_home) / "state.db"


def _history_db(history_db: str) -> Path:
    return Path(history_db).resolve()


def _find_latest_session(*, profile_home: str, task_id: str, workspace: str, session_id: str | None = None) -> str | None:
    state = _profile_state_db(profile_home)
    try:
        state_info = state.stat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(state_info.st_mode):
        raise OSError("state database is not a regular file")
    conn = sqlite3.connect(state.resolve().as_uri() + "?mode=ro", uri=True, timeout=STATE_QUERY_TIMEOUT)
    conn.row_factory = sqlite3.Row
    deadline = time.monotonic() + STATE_QUERY_TIMEOUT
    conn.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    try:
        row = conn.execute(
            """
            SELECT s.id
              FROM sessions AS s
             WHERE s.source = 'kanban'
               AND s.cwd = ?
               AND (? IS NULL OR s.id = ?)
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
            (workspace, session_id, session_id, f"work kanban task {task_id}"),
        ).fetchone()
        return _text(row["id"]) if row else None
    finally:
        conn.close()


def _open_history(history_db: str) -> sqlite3.Connection:
    path = _history_db(history_db)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=1.0)
    conn.row_factory = sqlite3.Row
    try:
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
        # A captured DB row does not prove that kanban_comment succeeded.
        # A separate receipt table also supports existing history DBs without
        # rewriting their rows or assuming legacy comments were delivered.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_session_history_comments (
                task_id TEXT NOT NULL,
                profile TEXT NOT NULL,
                session_id TEXT NOT NULL,
                recorded_at REAL NOT NULL,
                PRIMARY KEY (task_id, profile, session_id)
            )
            """
        )
        conn.commit()
        return conn
    except Exception:
        conn.close()
        raise


def _record_session(*, task_id: str, profile: str, session_id: str,
                    workspace: str, history_db: str, session_mode: str) -> bool:
    conn = _open_history(history_db)
    try:
        now = time.time()
        cursor = conn.execute(
            """
            INSERT INTO task_session_history(
                task_id, profile, session_id, session_mode, workspace, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id, profile, session_id) DO NOTHING
            """,
            (task_id, profile, session_id, session_mode, workspace, now, now),
        )
        is_new = cursor.rowcount == 1
        row = conn.execute(
            "SELECT workspace FROM task_session_history WHERE task_id = ? AND profile = ? AND session_id = ?",
            (task_id, profile, session_id),
        ).fetchone()
        if row["workspace"] != workspace:
            raise ValueError("history workspace mismatch")
        conn.execute(
            """
            UPDATE task_session_history
               SET session_mode = CASE WHEN ? = 'UNKNOWN' THEN session_mode ELSE ? END,
                   last_seen_at = ?
             WHERE task_id = ? AND profile = ? AND session_id = ?
            """,
            (session_mode, session_mode, now, task_id, profile, session_id),
        )
        conn.commit()
        return is_new
    finally:
        conn.close()


def capture(*, task_id: str, profile: str, profile_home: str, workspace: str,
            history_db: str, session_mode: str, session_id: str | None = None) -> tuple[str | None, bool]:
    """One exact lookup; preserve the original import-level return contract."""
    _validate_context(task_id=task_id, profile=profile, profile_home=profile_home,
                      workspace=workspace, history_db=history_db, session_mode=session_mode)
    if session_id is not None:
        _validate_token(session_id, "session-id")
    try:
        found = _find_latest_session(profile_home=profile_home, task_id=task_id,
                                     workspace=workspace, session_id=session_id)
    except (OSError, sqlite3.Error) as exc:
        raise SessionHistoryError("STATE_DB_ERROR", exc) from exc
    if not found:
        return None, False
    _validate_token(found, "session-id")
    try:
        is_new = _record_session(task_id=task_id, profile=profile, session_id=found,
                                workspace=workspace, history_db=history_db, session_mode=session_mode)
        return found, is_new
    except (OSError, sqlite3.Error) as exc:
        raise SessionHistoryError("HISTORY_DB_ERROR", exc) from exc


def comment_pending(*, task_id: str, profile: str, session_id: str, history_db: str) -> bool:
    conn = _open_history(history_db)
    try:
        return conn.execute(
            "SELECT 1 FROM task_session_history_comments WHERE task_id = ? AND profile = ? AND session_id = ?",
            (task_id, profile, session_id),
        ).fetchone() is None
    finally:
        conn.close()


def acknowledge_comment(*, task_id: str, profile: str, session_id: str, history_db: str) -> None:
    """Call only after successful comment delivery or exact card read-back."""
    _validate_token(task_id, "task-id")
    _validate_token(session_id, "session-id")
    if profile not in ("coder", "reviewer") or not _text(history_db) or not Path(history_db).is_absolute():
        raise ValueError("invalid comment context")
    conn = _open_history(history_db)
    try:
        row = conn.execute(
            "SELECT 1 FROM task_session_history WHERE task_id = ? AND profile = ? AND session_id = ?",
            (task_id, profile, session_id),
        ).fetchone()
        if row is None:
            raise ValueError("cannot acknowledge an uncaptured session")
        conn.execute(
            "INSERT INTO task_session_history_comments VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
            (task_id, profile, session_id, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def capture_with_retry(*, phase: str = "start", attempts: int = MAX_ATTEMPTS,
                       retry_delay: float = DEFAULT_RETRY_DELAY, **context) -> CaptureResult:
    """Retry missing metadata only. Finalization never sleeps or loops."""
    if phase not in ("start", "finalize") or not isinstance(attempts, int) or not 1 <= attempts <= MAX_ATTEMPTS:
        return CaptureResult("invalid", "INVALID_RETRY_CONTEXT", 0)
    if not math.isfinite(retry_delay) or not 0 <= retry_delay <= MAX_RETRY_DELAY:
        return CaptureResult("invalid", "INVALID_RETRY_CONTEXT", 0)
    limit = 1 if phase == "finalize" else attempts
    reason = "SESSION_MATCH_NOT_FOUND"
    for attempt in range(1, limit + 1):
        try:
            found, is_new = capture(**context)
            if found:
                pending = comment_pending(task_id=context["task_id"], profile=context["profile"],
                                          session_id=found, history_db=context["history_db"])
                return CaptureResult("captured", "SESSION_MATCHED", attempt, found, is_new, pending)
            reason = "SESSION_MATCH_NOT_FOUND" if _profile_state_db(context["profile_home"]).is_file() else "STATE_DB_MISSING"
        except ValueError:
            return CaptureResult("invalid", "INVALID_SESSION_CONTEXT", attempt)
        except SessionHistoryError as exc:
            return CaptureResult("error", exc.reason, attempt, error_type=exc.error_type)
        except (OSError, sqlite3.Error) as exc:
            return CaptureResult("error", "HISTORY_DB_ERROR", attempt, error_type=type(exc).__name__)
        if attempt < limit:
            time.sleep(retry_delay)
    return CaptureResult("unavailable", reason, limit)


def list_history(*, task_id: str, history_db: str) -> list[sqlite3.Row]:
    conn = _open_history(history_db)
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


def _print_capture(result: CaptureResult, *, profile: str, session_mode: str, phase: str) -> int:
    print(f"SESSION_HISTORY_STATUS={result.status}")
    print(f"SESSION_HISTORY_REASON={result.reason}")
    print(f"SESSION_HISTORY_PHASE={phase}")
    print(f"SESSION_HISTORY_ATTEMPTS={result.attempts}")
    print(f"SESSION_ID={result.session_id or 'UNAVAILABLE'}")
    print(f"SESSION_HISTORY_RECHECK_REQUIRED={str(result.status != 'captured' or result.comment_pending).lower()}")
    if result.error_type:
        print(f"SESSION_HISTORY_ERROR_TYPE={result.error_type}")
    if result.status == "unavailable":
        print("SESSION_HISTORY_ACTION=CONTINUE_WITH_WARNING")
        return 0
    if result.status in ("invalid", "error"):
        print("SESSION_HISTORY_ACTION=" + ("BLOCK_CONTEXT" if result.status == "invalid" else "REPORT_TRACE_ERROR"))
        return 2 if result.status == "invalid" else 3
    print("SESSION_HISTORY_ACTION=CONTINUE")
    print(f"SESSION_HISTORY_NEW={str(result.is_new).lower()}")
    print(f"SESSION_HISTORY_COMMENT_PENDING={str(result.comment_pending).lower()}")
    print(f"SESSION_PROFILE={profile}")
    print(f"SESSION_MODE={session_mode}")
    print("SESSION_HISTORY_MARKER_BEGIN")
    print("TASK_SESSION_HISTORY")
    print(f"- Session ID: {result.session_id}")
    print(f"- Profile: {profile}")
    print(f"- Mode: {session_mode}")
    print("SESSION_HISTORY_MARKER_END")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    capture_cmd = sub.add_parser("capture")
    capture_cmd.add_argument("--task-id", required=True)
    capture_cmd.add_argument("--profile", choices=("coder", "reviewer"), required=True)
    capture_cmd.add_argument("--profile-home", required=True)
    capture_cmd.add_argument("--workspace", required=True)
    capture_cmd.add_argument("--history-db", default=DEFAULT_HISTORY_DB)
    capture_cmd.add_argument("--session-mode", choices=("NEW", "RESUME", "UNKNOWN"), default="UNKNOWN")
    capture_cmd.add_argument("--session-id", help="Pin an already verified ID; never use another role's ID.")
    capture_cmd.add_argument("--phase", choices=("start", "finalize"), default="start")
    capture_cmd.add_argument("--attempts", type=int, default=MAX_ATTEMPTS)
    capture_cmd.add_argument("--retry-delay", type=float, default=DEFAULT_RETRY_DELAY)
    ack_cmd = sub.add_parser("ack-comment")
    ack_cmd.add_argument("--task-id", required=True)
    ack_cmd.add_argument("--profile", choices=("coder", "reviewer"), required=True)
    ack_cmd.add_argument("--session-id", required=True)
    ack_cmd.add_argument("--history-db", default=DEFAULT_HISTORY_DB)
    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--task-id", required=True)
    list_cmd.add_argument("--history-db", default=DEFAULT_HISTORY_DB)
    args = ap.parse_args(argv)
    if args.command == "capture":
        result = capture_with_retry(
            task_id=args.task_id, profile=args.profile, profile_home=args.profile_home,
            workspace=args.workspace, history_db=args.history_db, session_mode=args.session_mode,
            session_id=args.session_id, phase=args.phase, attempts=args.attempts, retry_delay=args.retry_delay,
        )
        return _print_capture(result, profile=args.profile, session_mode=args.session_mode, phase=args.phase)
    try:
        if args.command == "ack-comment":
            acknowledge_comment(task_id=args.task_id, profile=args.profile,
                                session_id=args.session_id, history_db=args.history_db)
            print("SESSION_HISTORY_STATUS=acknowledged")
            print("SESSION_HISTORY_COMMENT_PENDING=false")
            print("SESSION_HISTORY_RECHECK_REQUIRED=false")
            return 0
        _validate_token(args.task_id, "task-id")
        if not _text(args.history_db) or not Path(args.history_db).is_absolute():
            raise ValueError("invalid history-db")
        rows = list_history(task_id=args.task_id, history_db=args.history_db)
    except ValueError:
        print("SESSION_HISTORY_STATUS=invalid")
        print("SESSION_HISTORY_REASON=INVALID_SESSION_CONTEXT")
        return 2
    except (OSError, sqlite3.Error) as exc:
        print("SESSION_HISTORY_STATUS=error")
        print("SESSION_HISTORY_REASON=HISTORY_DB_ERROR")
        print(f"SESSION_HISTORY_ERROR_TYPE={type(exc).__name__}")
        return 3
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

        history = root / "history.db"
        session_id, is_new = capture(
            task_id="t1", profile="coder", profile_home=str(profile),
            workspace="/workspace/demo", history_db=str(history), session_mode="NEW",
        )
        assert session_id == "s1" and is_new
        _, is_new_again = capture(
            task_id="t1", profile="coder", profile_home=str(profile),
            workspace="/workspace/demo", history_db=str(history), session_mode="RESUME",
        )
        assert not is_new_again
        rows = list_history(task_id="t1", history_db=str(history))
        assert len(rows) == 1
        assert rows[0]["session_id"] == "s1"
        assert rows[0]["session_mode"] == "RESUME"
        context = dict(task_id="t1", profile="coder", profile_home=str(profile),
                       workspace="/workspace/demo", history_db=str(history), session_mode="UNKNOWN")
        pending = capture_with_retry(**context)
        assert pending.status == "captured" and pending.comment_pending and pending.attempts == 1
        acknowledge_comment(task_id="t1", profile="coder", session_id="s1", history_db=str(history))
        resolved = capture_with_retry(**context, phase="finalize", session_id="s1")
        assert resolved.status == "captured" and not resolved.comment_pending
        assert list_history(task_id="t1", history_db=str(history))[0]["session_mode"] == "RESUME"
        missing = capture_with_retry(**{**context, "task_id": "missing"}, retry_delay=0)
        assert missing.status == "unavailable" and missing.attempts == MAX_ATTEMPTS
        final_missing = capture_with_retry(**{**context, "task_id": "missing"}, phase="finalize")
        assert final_missing.status == "unavailable" and final_missing.attempts == 1
        bad = capture_with_retry(**{**context, "task_id": "UNAVAILABLE"})
        assert bad.status == "invalid"

    print("task session history self-test passed")


if __name__ == "__main__":
    if "--self-test" in os.sys.argv:
        self_test()
    else:
        raise SystemExit(main())
