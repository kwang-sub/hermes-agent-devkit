#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
from typing import Any

TRUE_VALUES = {"1", "true", "yes", "on"}
SUPPORTED_EVENTS = {
    "created",
    "review_requested",
    "changes_requested",
    "completed",
    "blocked",
    "gave_up",
    "crashed",
    "timed_out",
    "block_loop_detected",
}
DEFAULT_POLL_SECONDS = 1.0
DEFAULT_RETRY_MAX_SECONDS = 60.0
DEFAULT_BATCH_SIZE = 100
_STOP = False


def enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in TRUE_VALUES


def _float_env(name: str, default: float, minimum: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return max(minimum, float(raw))
    except ValueError:
        return default


def hermes_home() -> Path:
    return Path(os.getenv("HERMES_HOME") or os.getenv("HOME") or "/opt/data").expanduser().resolve()


def state_db_path(home: Path) -> Path:
    override = (os.getenv("DEVKIT_KANBAN_NOTIFIER_STATE_DB") or "").strip()
    return Path(override).expanduser().resolve() if override else home / "devkit-notifier" / "state.db"


def discover_boards(home: Path) -> list[tuple[str, Path]]:
    boards: list[tuple[str, Path]] = []
    default_db = home / "kanban.db"
    if default_db.is_file():
        boards.append(("default", default_db))
    named_root = home / "kanban" / "boards"
    if named_root.is_dir():
        for child in sorted(named_root.iterdir()):
            db = child / "kanban.db"
            if child.is_dir() and db.is_file():
                boards.append((child.name, db))
    return boards


def open_state(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=2.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=2000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS board_cursors (
            board TEXT PRIMARY KEY,
            db_path TEXT NOT NULL,
            last_event_id INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def board_max_event_id(db_path: Path) -> int:
    try:
        uri = f"file:{db_path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=1.0)
        try:
            row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM task_events").fetchone()
            return int(row[0] or 0)
        finally:
            conn.close()
    except (sqlite3.Error, OSError, ValueError):
        return 0


def initialize_state(state: sqlite3.Connection, boards: list[tuple[str, Path]]) -> None:
    initialized = state.execute("SELECT value FROM metadata WHERE key='initialized'").fetchone()
    now = int(time.time())
    if initialized is None:
        for board, db_path in boards:
            state.execute(
                """
                INSERT INTO board_cursors(board, db_path, last_event_id, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(board) DO UPDATE SET
                    db_path=excluded.db_path,
                    last_event_id=excluded.last_event_id,
                    updated_at=excluded.updated_at
                """,
                (board, str(db_path), board_max_event_id(db_path), now),
            )
        state.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES ('initialized', ?)", (str(now),))
        state.commit()


def cursor_for_board(state: sqlite3.Connection, board: str, db_path: Path) -> int:
    row = state.execute(
        "SELECT last_event_id FROM board_cursors WHERE board=?",
        (board,),
    ).fetchone()
    if row is not None:
        return int(row["last_event_id"] or 0)
    now = int(time.time())
    state.execute(
        "INSERT INTO board_cursors(board, db_path, last_event_id, updated_at) VALUES (?, ?, 0, ?)",
        (board, str(db_path), now),
    )
    state.commit()
    return 0


def advance_cursor(state: sqlite3.Connection, board: str, db_path: Path, event_id: int) -> None:
    state.execute(
        """
        INSERT INTO board_cursors(board, db_path, last_event_id, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(board) DO UPDATE SET
            db_path=excluded.db_path,
            last_event_id=excluded.last_event_id,
            updated_at=excluded.updated_at
        """,
        (board, str(db_path), int(event_id), int(time.time())),
    )
    state.commit()


def _read_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        value = json.loads(str(raw))
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def fetch_events(db_path: Path, after_id: int, limit: int = DEFAULT_BATCH_SIZE) -> list[dict[str, Any]]:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=1.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    try:
        rows = conn.execute(
            """
            SELECT
                e.id AS event_id,
                e.task_id,
                e.run_id,
                e.kind,
                e.payload,
                e.created_at,
                t.title,
                t.assignee,
                t.status,
                t.result,
                t.model_override,
                t.provider_override,
                t.created_by
            FROM task_events AS e
            LEFT JOIN tasks AS t ON t.id = e.task_id
            WHERE e.id > ?
            ORDER BY e.id ASC
            LIMIT ?
            """,
            (int(after_id), int(limit)),
        ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = _read_payload(item.get("payload"))
            profile = ""
            run_id = item.get("run_id")
            if run_id is not None:
                try:
                    run = conn.execute(
                        "SELECT profile FROM task_runs WHERE id = ? LIMIT 1",
                        (run_id,),
                    ).fetchone()
                    profile = str(run["profile"] or "") if run else ""
                except sqlite3.Error:
                    profile = ""
            item["run_profile"] = profile
            events.append(item)
        return events
    finally:
        conn.close()


def _clean(value: Any, limit: int = 500) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    if "Bearer " in text:
        start = text.find("Bearer ")
        end = text.find(" ", start + len("Bearer "))
        end = len(text) if end < 0 else end
        text = text[:start] + "Bearer [REDACTED]" + text[end:]
    for marker in ("ghp_", "github_pat_"):
        while marker in text:
            start = text.find(marker)
            end = start + len(marker)
            while end < len(text) and (text[end].isalnum() or text[end] in "_-"):
                end += 1
            text = text[:start] + "[REDACTED_GITHUB_TOKEN]" + text[end:]
    return text[:limit]


def should_notify(event: dict[str, Any]) -> bool:
    kind = str(event.get("kind") or "")
    if kind not in SUPPORTED_EVENTS:
        return False
    if kind == "blocked":
        payload = event.get("payload") or {}
        if str(payload.get("reason") or "") == "initial_status":
            return False
    return True


def event_profile(event: dict[str, Any]) -> str:
    payload = event.get("payload") or {}
    kind = str(event.get("kind") or "")
    if kind == "created":
        return str(event.get("created_by") or "")
    if kind == "review_requested":
        return str(payload.get("implementer") or event.get("run_profile") or "")
    if kind == "changes_requested":
        return str(payload.get("reviewer") or event.get("run_profile") or "")
    return str(event.get("run_profile") or "")


def model_label(event: dict[str, Any]) -> str:
    payload = event.get("payload") or {}
    if str(event.get("kind") or "") == "created":
        model = str(payload.get("model_override") or event.get("model_override") or "").strip()
        provider = str(payload.get("provider_override") or event.get("provider_override") or "").strip()
    else:
        model = str(event.get("model_override") or "").strip()
        provider = str(event.get("provider_override") or "").strip()
    if model:
        return f"{provider} / {model}" if provider else model
    return "DEFAULT (profile)"


def format_message(board: str, event: dict[str, Any]) -> str | None:
    if not should_notify(event):
        return None
    kind = str(event.get("kind") or "")
    payload = event.get("payload") or {}
    task_id = str(event.get("task_id") or "-")
    title = _clean(event.get("title") or task_id, 160)
    assignee_value = payload.get("assignee") if kind == "created" else event.get("assignee")
    assignee = _clean(assignee_value or "-", 80)
    profile = _clean(event_profile(event) or "-", 80)
    labels = {
        "created": ("🆕", "작업 등록", "REGISTERED"),
        "completed": ("✅", "작업 완료", "DONE"),
        "blocked": ("⛔", "작업 차단", "BLOCKED"),
        "gave_up": ("❌", "작업 실패", "GAVE_UP"),
        "crashed": ("💥", "작업 비정상 종료", "CRASHED"),
        "timed_out": ("⏱️", "작업 시간 초과", "TIMED_OUT"),
        "review_requested": ("🔎", "리뷰 요청", "REVIEW"),
        "changes_requested": ("🛠️", "수정 요청", "CHANGES_REQUESTED"),
        "block_loop_detected": ("⚠️", "반복 차단 감지", "TRIAGE"),
    }
    icon, heading, status = labels[kind]

    detail = ""
    detail_label = "상세"
    if kind == "created":
        detail_label = "등록"
        detail = "Coder 작업 대기열에 등록되었습니다."
    elif kind == "blocked":
        detail_label = "사유"
        detail = _clean(payload.get("reason") or "", 500)
    elif kind in {"gave_up", "crashed", "timed_out"}:
        detail_label = "오류"
        detail = _clean(payload.get("error") or payload.get("reason") or "", 500)
    elif kind in {"review_requested", "changes_requested", "block_loop_detected"}:
        detail_label = "내용"
        detail = _clean(payload.get("reason") or payload.get("summary") or "", 500)
    elif kind == "completed":
        detail_label = "결과"
        detail = _clean(
            payload.get("result") or payload.get("summary") or event.get("result") or "",
            500,
        )

    lines = [
        f"{icon} {heading}",
        "",
        f"프로젝트  {board}",
        f"작업      {title}",
        f"Task      {task_id}",
        f"담당      {assignee}",
        f"프로필    {profile}",
        f"모델      {model_label(event)}",
        f"상태      {status}",
    ]
    if detail:
        lines.extend(["", detail_label, detail])
    return "\n".join(lines)


def delivery_target(platform: str, target: str) -> str:
    platform = platform.strip()
    target = target.strip()
    if not target:
        return platform
    prefix = f"{platform}:"
    return target if target.startswith(prefix) else f"{prefix}{target}"


def send_message(message: str, *, platform: str, target: str, hermes_cli: str = "/usr/local/bin/hermes") -> tuple[bool, str]:
    cmd = [
        hermes_cli,
        "send",
        "--to",
        delivery_target(platform, target),
        "--file",
        "-",
        "--json",
    ]
    try:
        result = subprocess.run(cmd, input=message, text=True, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if result.returncode == 0:
        return True, (result.stdout or "").strip()
    detail = (result.stderr or result.stdout or "").strip().replace("\n", " | ")
    return False, detail[:500]


def process_board(
    state: sqlite3.Connection,
    board: str,
    db_path: Path,
    *,
    platform: str,
    target: str,
    hermes_cli: str,
    deliver_enabled: bool,
) -> tuple[int, bool, str]:
    cursor = cursor_for_board(state, board, db_path)
    try:
        events = fetch_events(db_path, cursor)
    except (sqlite3.Error, OSError) as exc:
        return 0, False, f"{board}: read failed: {exc}"
    processed = 0
    for event in events:
        event_id = int(event["event_id"])
        if deliver_enabled:
            message = format_message(board, event)
            if message is not None:
                ok, detail = send_message(message, platform=platform, target=target, hermes_cli=hermes_cli)
                if not ok:
                    return processed, False, f"{board}: delivery failed event={event_id} kind={event.get('kind')}: {detail}"
        advance_cursor(state, board, db_path, event_id)
        processed += 1
    return processed, True, ""


def _stop(_signum: int, _frame: Any) -> None:
    global _STOP
    _STOP = True


def initialize_persistent_state() -> Path:
    home = hermes_home()
    path = state_db_path(home)
    state = open_state(path)
    try:
        initialize_state(state, discover_boards(home))
    finally:
        state.close()
    return path


def run_forever() -> int:
    home = hermes_home()
    enabled_flag = enabled(os.getenv("HERMES_KANBAN_NOTIFY_ENABLED"))
    platform = (os.getenv("HERMES_KANBAN_NOTIFY_PLATFORM") or "discord").strip()
    target = (os.getenv("HERMES_KANBAN_NOTIFY_TARGET") or "").strip()
    hermes_cli = (os.getenv("HERMES_CLI") or "/usr/local/bin/hermes").strip()
    poll = _float_env("DEVKIT_KANBAN_NOTIFIER_POLL_SECONDS", DEFAULT_POLL_SECONDS, 0.2)
    retry_max = _float_env("DEVKIT_KANBAN_NOTIFIER_RETRY_MAX_SECONDS", DEFAULT_RETRY_MAX_SECONDS, 1.0)

    state_path = state_db_path(home)
    state = open_state(state_path)
    retry = 1.0
    try:
        initialize_state(state, discover_boards(home))
        if enabled_flag and (not platform or not target):
            print("[devkit-notifier] enabled but platform/target is missing", file=sys.stderr, flush=True)
            while not _STOP:
                time.sleep(60)
            return 0

        mode = "delivery" if enabled_flag else "cursor-only"
        print(
            f"[devkit-notifier] started mode={mode} platform={platform} target={target or '-'} state={state_path}",
            flush=True,
        )
        while not _STOP:
            any_failure = False
            for board, db_path in discover_boards(home):
                processed, ok, error = process_board(
                    state,
                    board,
                    db_path,
                    platform=platform,
                    target=target,
                    hermes_cli=hermes_cli,
                    deliver_enabled=enabled_flag,
                )
                if processed:
                    print(f"[devkit-notifier] board={board} processed={processed} mode={mode}", flush=True)
                if not ok:
                    any_failure = True
                    print(f"[devkit-notifier] {error}", file=sys.stderr, flush=True)
            if any_failure:
                time.sleep(retry)
                retry = min(retry_max, max(1.0, retry * 2))
            else:
                retry = 1.0
                time.sleep(poll)
    finally:
        state.close()
    return 0

def self_test() -> None:
    import tempfile
    with tempfile.TemporaryDirectory(prefix="devkit-notifier-selftest-") as tmp:
        root = Path(tmp)
        home = root / "home"
        home.mkdir()
        board_dir = home / "kanban" / "boards" / "demo"
        board_dir.mkdir(parents=True)
        board_db = board_dir / "kanban.db"
        conn = sqlite3.connect(board_db)
        conn.executescript(
            """
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                title TEXT,
                assignee TEXT,
                status TEXT,
                result TEXT,
                model_override TEXT,
                provider_override TEXT,
                created_by TEXT
            );
            CREATE TABLE task_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                run_id INTEGER,
                kind TEXT,
                payload TEXT,
                created_at INTEGER
            );
            CREATE TABLE task_runs (
                id INTEGER PRIMARY KEY,
                profile TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("t_1", "테스트 작업", "coder", "blocked", None, "gpt-test", "openai", "orchestrator"),
        )
        conn.execute("INSERT INTO task_runs VALUES (1, 'coder')")
        conn.execute(
            "INSERT INTO task_events(task_id, run_id, kind, payload, created_at) VALUES (?, ?, 'created', ?, 1)",
            ("t_1", None, json.dumps({"assignee": "coder"})),
        )
        conn.execute(
            "INSERT INTO task_events(task_id, run_id, kind, payload, created_at) VALUES (?, ?, 'blocked', ?, 2)",
            ("t_1", None, json.dumps({"reason": "initial_status"})),
        )
        conn.commit()
        conn.close()

        state = open_state(root / "state.db")
        initialize_state(state, [("demo", board_db)])
        assert cursor_for_board(state, "demo", board_db) == 2

        conn = sqlite3.connect(board_db)
        conn.execute(
            "INSERT INTO task_events(task_id, run_id, kind, payload, created_at) VALUES (?, ?, 'review_requested', ?, 3)",
            ("t_1", 1, json.dumps({"summary": "구현 완료", "implementer": "coder"})),
        )
        conn.commit()
        conn.close()

        events = fetch_events(board_db, 2)
        assert len(events) == 1
        msg = format_message("demo", events[0])
        assert msg is not None
        assert "리뷰 요청" in msg
        assert "프로젝트  demo" in msg
        assert "프로필    coder" in msg
        assert "openai / gpt-test" in msg

        processed, ok, error = process_board(
            state,
            "demo",
            board_db,
            platform="discord",
            target="unused",
            hermes_cli="/does/not/matter",
            deliver_enabled=False,
        )
        assert ok and not error and processed == 1
        assert cursor_for_board(state, "demo", board_db) == 3

        created = {
            "kind": "created",
            "task_id": "t_2",
            "title": "신규 작업",
            "assignee": "coder",
            "run_profile": "",
            "model_override": None,
            "provider_override": None,
            "payload": {"assignee": "coder", "model_override": "gpt-created", "provider_override": "openai"},
            "created_by": "orchestrator",
        }
        created_msg = format_message("demo", created)
        assert created_msg and "작업 등록" in created_msg and "REGISTERED" in created_msg
        assert "프로필    orchestrator" in created_msg
        assert "openai / gpt-created" in created_msg
        ignored = dict(created, kind="blocked", payload={"reason": "initial_status"})
        assert format_message("demo", ignored) is None
        assert delivery_target("discord", "123") == "discord:123"
        assert delivery_target("discord", "discord:123") == "discord:123"
        state.close()
    print("DevKit Kanban notifier self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser(description="DevKit Kanban event notification bridge.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--initialize-state", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.initialize_state:
        path = initialize_persistent_state()
        print(f"[devkit-notifier] state initialized: {path}")
        return 0
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    return run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
