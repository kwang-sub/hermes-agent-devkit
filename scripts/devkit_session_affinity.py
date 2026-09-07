#!/usr/bin/env python3
"""DevKit runtime support for Kanban task/profile session affinity.

This module is copied into ``/opt/hermes/hermes_cli`` by the DevKit image.
It keeps session affinity state outside Hermes' upstream Kanban schema and
falls back to a fresh session whenever any lookup/storage step is uncertain.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Iterable, Optional

AFFINITY_DB_NAME = "devkit-session-affinity.db"
SESSION_MODE_NEW = "NEW"
SESSION_MODE_RESUME = "RESUME"


@dataclass(frozen=True)
class SessionChoice:
    mode: str
    session_id: Optional[str]
    fingerprint: str


def _text(value: Any) -> str:
    return str(value or "").strip()


def _profile_config_hash(profile_home: Optional[str]) -> str:
    if not profile_home:
        return ""
    path = Path(profile_home) / "config.yaml"
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
    except OSError:
        return ""


def _base_sha(body: Any) -> str:
    text = str(body or "")
    match = re.search(r"(?im)^\s*(?:[-*]\s*)?Base SHA\s*:\s*([0-9a-f]{7,64})\s*$", text)
    return match.group(1).lower() if match else ""


def _fingerprint(
    *,
    task: Any,
    workspace: str,
    profile: str,
    profile_home: Optional[str],
    worker_toolsets: Iterable[str],
) -> str:
    payload = {
        "profile": _text(profile),
        "workspace": _text(workspace),
        "branch": _text(getattr(task, "branch_name", "")),
        "base_sha": _base_sha(getattr(task, "body", "")),
        "model": _text(getattr(task, "model_override", "")),
        "provider": _text(getattr(task, "provider_override", "")),
        "reasoning": _text(getattr(task, "reasoning_effort", "")),
        "skills": sorted(_text(v) for v in (getattr(task, "skills", None) or []) if _text(v)),
        "toolsets": sorted(_text(v) for v in (worker_toolsets or []) if _text(v)),
        "goal_mode": bool(getattr(task, "goal_mode", False)),
        "goal_max_turns": getattr(task, "goal_max_turns", None),
        # Reviewer/default-model changes are not visible in task overrides.
        # Hash the profile config so any profile-level runtime change starts a
        # fresh session instead of letting --resume restore stale settings.
        "profile_config": _profile_config_hash(profile_home),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _affinity_db_path(kanban_db_path: str) -> Path:
    return Path(kanban_db_path).resolve().parent / AFFINITY_DB_NAME


def _open_affinity(kanban_db_path: str) -> sqlite3.Connection:
    path = _affinity_db_path(kanban_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=1.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 1000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_affinity (
            task_id TEXT NOT NULL,
            profile TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            session_id TEXT,
            workspace TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (task_id, profile)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_runs (
            run_id INTEGER PRIMARY KEY,
            task_id TEXT NOT NULL,
            profile TEXT NOT NULL,
            mode TEXT NOT NULL,
            session_id TEXT,
            workspace TEXT NOT NULL,
            started_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _profile_state_db(profile_home: Optional[str]) -> Optional[Path]:
    if not profile_home:
        return None
    path = Path(profile_home) / "state.db"
    return path if path.is_file() else None


def _open_state_readonly(profile_home: Optional[str]) -> Optional[sqlite3.Connection]:
    path = _profile_state_db(profile_home)
    if path is None:
        return None
    # URI read-only mode avoids accidentally creating/migrating a profile DB
    # from the dispatcher/notifier path.
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=0.5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def _session_exists(profile_home: Optional[str], session_id: Optional[str]) -> bool:
    if not session_id:
        return False
    conn = None
    try:
        conn = _open_state_readonly(profile_home)
        if conn is None:
            return False
        return conn.execute("SELECT 1 FROM sessions WHERE id = ? LIMIT 1", (session_id,)).fetchone() is not None
    except (OSError, sqlite3.Error):
        return False
    finally:
        if conn is not None:
            conn.close()


def _find_task_session(
    profile_home: Optional[str],
    task_id: str,
    workspace: str,
    *,
    min_started_at: Optional[float] = None,
) -> Optional[str]:
    """Return the latest profile-local Kanban session for exactly this task.

    The task prompt is dispatcher-owned and stable. Requiring the worker cwd
    prevents the same random task id on another board/workspace from becoming
    a cross-project resume candidate.
    """
    conn = None
    try:
        conn = _open_state_readonly(profile_home)
        if conn is None:
            return None
        prompt = f"work kanban task {task_id}"
        row = conn.execute(
            """
            SELECT s.id
              FROM sessions AS s
             WHERE s.source = 'kanban'
               AND (? = '' OR s.cwd = ?)
               AND (? IS NULL OR s.started_at >= ?)
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
            (workspace, workspace, min_started_at, min_started_at, prompt),
        ).fetchone()
        return _text(row["id"]) if row else None
    except (OSError, sqlite3.Error):
        return None
    finally:
        if conn is not None:
            conn.close()


def choose_worker_session(
    *,
    task: Any,
    workspace: str,
    profile: str,
    profile_home: Optional[str],
    kanban_db_path: str,
    worker_toolsets: Iterable[str] = (),
) -> SessionChoice:
    """Choose NEW/RESUME for one dispatcher spawn.

    Affinity is keyed by ``task_id + profile``. A resume is allowed only when
    the saved execution fingerprint still matches. Any DB/read ambiguity is
    fail-safe: start NEW and do not make Kanban dispatch itself fail.
    """
    task_id = _text(getattr(task, "id", ""))
    profile = _text(profile)
    workspace = _text(workspace)
    fingerprint = _fingerprint(
        task=task,
        workspace=workspace,
        profile=profile,
        profile_home=profile_home,
        worker_toolsets=worker_toolsets,
    )
    if not task_id or not profile:
        return SessionChoice(SESSION_MODE_NEW, None, fingerprint)

    mode = SESSION_MODE_NEW
    session_id: Optional[str] = None
    conn = None
    try:
        conn = _open_affinity(kanban_db_path)
        row = conn.execute(
            "SELECT fingerprint, session_id, updated_at FROM session_affinity WHERE task_id = ? AND profile = ?",
            (task_id, profile),
        ).fetchone()
        if row is not None and _text(row["fingerprint"]) == fingerprint:
            stored = _text(row["session_id"]) or None
            if stored and _session_exists(profile_home, stored):
                session_id = stored
            else:
                # First retry after a NEW run: the worker session was created
                # after the dispatcher wrote the binding, so discover it now.
                session_id = _find_task_session(
                    profile_home,
                    task_id,
                    workspace,
                    min_started_at=float(row["updated_at"]),
                )
            if session_id:
                mode = SESSION_MODE_RESUME

        now = time.time()
        conn.execute(
            """
            INSERT INTO session_affinity(task_id, profile, fingerprint, session_id, workspace, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id, profile) DO UPDATE SET
                fingerprint = excluded.fingerprint,
                session_id = excluded.session_id,
                workspace = excluded.workspace,
                updated_at = excluded.updated_at
            """,
            (task_id, profile, fingerprint, session_id if mode == SESSION_MODE_RESUME else None, workspace, now),
        )
        run_id = getattr(task, "current_run_id", None)
        if run_id is not None:
            conn.execute(
                """
                INSERT OR REPLACE INTO session_runs(run_id, task_id, profile, mode, session_id, workspace, started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (int(run_id), task_id, profile, mode, session_id, workspace, now),
            )
        conn.commit()
    except (OSError, sqlite3.Error, TypeError, ValueError):
        mode = SESSION_MODE_NEW
        session_id = None
    finally:
        if conn is not None:
            conn.close()
    return SessionChoice(mode, session_id, fingerprint)


def _execution_profile(kind: str, task: Any, payload: dict[str, Any]) -> str:
    if kind == "review_requested":
        return _text(payload.get("implementer")) or _text(getattr(task, "assignee", ""))
    if kind == "changes_requested":
        return _text(payload.get("reviewer")) or _text(getattr(task, "assignee", ""))
    return _text(getattr(task, "assignee", ""))


def _resolve_profile_home(profile: str) -> Optional[str]:
    if not profile:
        return None
    try:
        from hermes_cli.profiles import resolve_profile_env

        return resolve_profile_env(profile)
    except Exception:
        return None


def notification_session_context(
    *,
    kind: str,
    task: Any,
    event: Any,
    kanban_db_path: str,
) -> tuple[str, str, str]:
    """Resolve ``(profile, session_id, mode)`` for a terminal notification."""
    payload = getattr(event, "payload", None) or {}
    if not isinstance(payload, dict):
        payload = {}
    task_id = _text(getattr(task, "id", ""))
    profile = _execution_profile(kind, task, payload)
    profile_home = _resolve_profile_home(profile)
    workspace = _text(getattr(task, "workspace_path", ""))
    event_run_id = getattr(event, "run_id", None) or payload.get("run_id")

    mode = "-"
    stored_session: Optional[str] = None
    run_started_at: Optional[float] = None
    conn = None
    try:
        conn = _open_affinity(kanban_db_path)
        row = None
        if event_run_id is not None:
            try:
                row = conn.execute(
                    "SELECT mode, session_id, workspace, started_at FROM session_runs WHERE run_id = ? AND task_id = ?",
                    (int(event_run_id), task_id),
                ).fetchone()
            except (TypeError, ValueError):
                row = None
        if row is None and task_id and profile:
            row = conn.execute(
                """
                SELECT mode, session_id, workspace, started_at
                  FROM session_runs
                 WHERE task_id = ? AND profile = ?
                 ORDER BY started_at DESC LIMIT 1
                """,
                (task_id, profile),
            ).fetchone()
        if row is not None:
            mode = _text(row["mode"]) or "-"
            stored_session = _text(row["session_id"]) or None
            workspace = _text(row["workspace"]) or workspace
            try:
                run_started_at = float(row["started_at"])
            except (TypeError, ValueError):
                run_started_at = None
    except (OSError, sqlite3.Error):
        pass
    finally:
        if conn is not None:
            conn.close()

    if task_id and profile:
        min_started_at = run_started_at if mode == SESSION_MODE_NEW and run_started_at else None
        current_session = _find_task_session(
            profile_home, task_id, workspace, min_started_at=min_started_at
        )
    else:
        current_session = None
    session_id = current_session or stored_session or "-"

    # Best-effort backfill so the next dispatcher spawn can resume even when
    # the terminal notification was the first place the fresh session id was
    # observable outside the worker process.
    if current_session and task_id and profile:
        conn = None
        try:
            conn = _open_affinity(kanban_db_path)
            conn.execute(
                "UPDATE session_affinity SET session_id = ?, updated_at = ? WHERE task_id = ? AND profile = ?",
                (current_session, time.time(), task_id, profile),
            )
            if event_run_id is not None:
                try:
                    conn.execute(
                        "UPDATE session_runs SET session_id = ? WHERE run_id = ? AND task_id = ?",
                        (current_session, int(event_run_id), task_id),
                    )
                except (TypeError, ValueError):
                    pass
            conn.commit()
        except (OSError, sqlite3.Error):
            pass
        finally:
            if conn is not None:
                conn.close()

    return profile or "-", session_id, mode


def self_test() -> None:
    import tempfile
    from types import SimpleNamespace

    with tempfile.TemporaryDirectory(prefix="hermes-kanban-session-affinity-selftest-") as temp_dir:
        root = Path(temp_dir)
        profile_home = root / "profile"
        profile_home.mkdir()
        (profile_home / "config.yaml").write_text("model: test\n", encoding="utf-8")
        state = sqlite3.connect(str(profile_home / "state.db"))
        state.execute(
            "CREATE TABLE sessions(id TEXT PRIMARY KEY, source TEXT, cwd TEXT, started_at REAL)"
        )
        state.execute(
            "CREATE TABLE messages(id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT)"
        )
        state.commit()
        state.close()
        kanban = root / "kanban.db"
        sqlite3.connect(str(kanban)).close()

        task = SimpleNamespace(
            id="t_affinity",
            body="- Base SHA: abcdef1",
            branch_name="dev",
            model_override="model-a",
            provider_override="provider-a",
            reasoning_effort="high",
            skills=["skill-a"],
            goal_mode=False,
            goal_max_turns=None,
            current_run_id=1,
            assignee="coder",
            workspace_path="/workspace/demo",
        )
        first = choose_worker_session(
            task=task,
            workspace=task.workspace_path,
            profile="coder",
            profile_home=str(profile_home),
            kanban_db_path=str(kanban),
            worker_toolsets=["terminal"],
        )
        assert first.mode == SESSION_MODE_NEW and first.session_id is None

        state = sqlite3.connect(str(profile_home / "state.db"))
        state.execute(
            "INSERT INTO sessions VALUES (?, 'kanban', ?, ?)",
            ("session-a", task.workspace_path, time.time()),
        )
        state.execute(
            "INSERT INTO messages VALUES (1, ?, 'user', ?)",
            ("session-a", f"work kanban task {task.id}"),
        )
        state.commit()
        state.close()

        task.current_run_id = 2
        second = choose_worker_session(
            task=task,
            workspace=task.workspace_path,
            profile="coder",
            profile_home=str(profile_home),
            kanban_db_path=str(kanban),
            worker_toolsets=["terminal"],
        )
        assert second.mode == SESSION_MODE_RESUME and second.session_id == "session-a"

        # The same card binds independently per profile. Reviewer starts with a
        # separate profile-local state DB/session and never inherits Coder.
        reviewer_home = root / "reviewer"
        reviewer_home.mkdir()
        (reviewer_home / "config.yaml").write_text("model: review\n", encoding="utf-8")
        reviewer_state = sqlite3.connect(str(reviewer_home / "state.db"))
        reviewer_state.execute(
            "CREATE TABLE sessions(id TEXT PRIMARY KEY, source TEXT, cwd TEXT, started_at REAL)"
        )
        reviewer_state.execute(
            "CREATE TABLE messages(id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT)"
        )
        reviewer_state.commit()
        reviewer_state.close()
        task.current_run_id = 20
        review_first = choose_worker_session(
            task=task, workspace=task.workspace_path, profile="reviewer",
            profile_home=str(reviewer_home), kanban_db_path=str(kanban),
            worker_toolsets=["terminal"],
        )
        assert review_first.mode == SESSION_MODE_NEW
        reviewer_state = sqlite3.connect(str(reviewer_home / "state.db"))
        reviewer_state.execute(
            "INSERT INTO sessions VALUES (?, 'kanban', ?, ?)",
            ("review-session", task.workspace_path, time.time()),
        )
        reviewer_state.execute(
            "INSERT INTO messages VALUES (1, ?, 'user', ?)",
            ("review-session", f"work kanban task {task.id}"),
        )
        reviewer_state.commit()
        reviewer_state.close()
        task.current_run_id = 21
        review_second = choose_worker_session(
            task=task, workspace=task.workspace_path, profile="reviewer",
            profile_home=str(reviewer_home), kanban_db_path=str(kanban),
            worker_toolsets=["terminal"],
        )
        assert review_second.mode == SESSION_MODE_RESUME
        assert review_second.session_id == "review-session"

        # Changing the execution contract must break affinity even on the same
        # task/profile pair.
        task.model_override = "model-b"
        task.current_run_id = 3
        third = choose_worker_session(
            task=task,
            workspace=task.workspace_path,
            profile="coder",
            profile_home=str(profile_home),
            kanban_db_path=str(kanban),
            worker_toolsets=["terminal"],
        )
        assert third.mode == SESSION_MODE_NEW and third.session_id is None

        # Restore the original contract and verify notification lookup exposes
        # both the executing profile and the durable session id/mode.
        task.model_override = "model-a"
        task.current_run_id = 4
        fourth = choose_worker_session(
            task=task,
            workspace=task.workspace_path,
            profile="coder",
            profile_home=str(profile_home),
            kanban_db_path=str(kanban),
            worker_toolsets=["terminal"],
        )
        # The immediately preceding contract was different, so this run is NEW.
        assert fourth.mode == SESSION_MODE_NEW
        globals()["_resolve_profile_home"] = lambda profile: str(profile_home)
        profile, session_id, mode = notification_session_context(
            kind="blocked",
            task=task,
            event=SimpleNamespace(payload={}, run_id=4),
            kanban_db_path=str(kanban),
        )
        assert profile == "coder"
        assert session_id == "-"
        assert mode == SESSION_MODE_NEW

    print("Hermes Kanban session-affinity runtime self-test passed")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if not args.self_test:
        parser.error("only --self-test is supported when executing this runtime module directly")
    self_test()
