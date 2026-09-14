#!/usr/bin/env python3
from __future__ import annotations

import argparse
import py_compile
import sqlite3
import tempfile
from pathlib import Path

PATCH_MARKER = "from hermes_cli.devkit_session_affinity import choose_worker_session"
CONTEXT_MARKER = 'env["HERMES_KANBAN_CONTEXT_VERSION"] = "1"'
SINGLE_WORKER_HELPER_MARKER = "def _devkit_find_live_task_process("
SINGLE_WORKER_CALL_MARKER = 'result.respawn_guarded.append((task_id, "live_task_process"))'

LEGACY_ANCHOR = '''    worker_toolsets = _resolve_worker_cli_toolsets(env.get("HERMES_HOME"))
    if worker_toolsets:
        cmd.extend(["--toolsets", ",".join(worker_toolsets)])
    cmd.extend([
        "chat",
        "-q", prompt,
    ])
'''
LEGACY_REPLACEMENT = '''    worker_toolsets = _resolve_worker_cli_toolsets(env.get("HERMES_HOME"))
    if worker_toolsets:
        cmd.extend(["--toolsets", ",".join(worker_toolsets)])
    from hermes_cli.devkit_session_affinity import choose_worker_session
    env["HERMES_KANBAN_CONTEXT_VERSION"] = "1"
    _devkit_session = choose_worker_session(
        task=task, workspace=workspace, profile=profile_arg,
        profile_home=env.get("HERMES_HOME"),
        kanban_db_path=str(kanban_db_path(board=board)),
        worker_toolsets=worker_toolsets or (),
    )
    env["HERMES_KANBAN_SESSION_MODE"] = _devkit_session.mode
    if _devkit_session.session_id:
        env["HERMES_KANBAN_AFFINITY_SESSION_ID"] = _devkit_session.session_id
        cmd.extend(["--resume", _devkit_session.session_id])
    else:
        env.pop("HERMES_KANBAN_AFFINITY_SESSION_ID", None)
    cmd.extend([
        "chat",
        "-q", prompt,
    ])
'''
LEGACY_CONTEXT = (
    'prompt = f"work kanban task {task.id}"',
    "_resolve_worker_cli_toolsets",
    "profile_arg",
    "kanban_db_path",
)

CURRENT_ANCHOR = '''    cmd = _worker_argv(task, profile_arg, env.get("HERMES_HOME"))
'''
CURRENT_REPLACEMENT = '''    cmd = _worker_argv(task, profile_arg, env.get("HERMES_HOME"))
    from hermes_cli.devkit_session_affinity import choose_worker_session
    env["HERMES_KANBAN_CONTEXT_VERSION"] = "1"
    _devkit_worker_toolsets = _resolve_worker_cli_toolsets(env.get("HERMES_HOME"))
    _devkit_session = choose_worker_session(
        task=task, workspace=workspace, profile=profile_arg,
        profile_home=env.get("HERMES_HOME"),
        kanban_db_path=env["HERMES_KANBAN_DB"],
        worker_toolsets=_devkit_worker_toolsets or (),
    )
    env["HERMES_KANBAN_SESSION_MODE"] = _devkit_session.mode
    if _devkit_session.session_id:
        env["HERMES_KANBAN_AFFINITY_SESSION_ID"] = _devkit_session.session_id
        try:
            _devkit_chat_index = cmd.index("chat")
        except ValueError as exc:
            raise RuntimeError("Hermes Kanban worker argv has no chat command") from exc
        cmd[_devkit_chat_index:_devkit_chat_index] = [
            "--resume", _devkit_session.session_id,
        ]
    else:
        env.pop("HERMES_KANBAN_AFFINITY_SESSION_ID", None)
'''
CURRENT_CONTEXT = (
    "def _worker_argv(",
    "def _default_spawn(",
    'env["HERMES_KANBAN_DB"]',
    'env["HERMES_KANBAN_TASK"]',
    'env["HERMES_KANBAN_WORKSPACE"]',
    'env["HERMES_KANBAN_BOARD"]',
    'env["HERMES_PROFILE"]',
    "_resolve_worker_cli_toolsets",
    "profile_arg",
)

# Hermes already serializes ready->running with an atomic claim. The remaining
# overlap window is a terminal/reclaim handoff: the task can become runnable
# again while the old host process is still alive. Scan the host process table
# for the dispatcher's task+board-DB environment before taking a new claim.
# Session affinity then decides RESUME vs NEW only after that process is gone.
SINGLE_WORKER_FUNCTION_ANCHOR = "def _dispatch_lane_task("
SINGLE_WORKER_CLAIM_ANCHOR = '''    claim = _kb.claim_review_task if lane == "review" else _kb.claim_task
'''
SINGLE_WORKER_HELPER_SOURCE = '''def _devkit_find_live_task_process(conn, task_id, *, proc_root="/proc", current_pid=None):
    import os as _devkit_os

    _task_id = str(task_id or "").strip()
    if not _task_id:
        return None
    try:
        _db_rows = conn.execute("PRAGMA database_list").fetchall()
        _db_path = ""
        for _db_row in _db_rows:
            if str(_db_row[1]) == "main":
                _db_path = str(_db_row[2] or "").strip()
                break
        if _db_path:
            _db_path = _devkit_os.path.realpath(_db_path)
    except Exception:
        _db_path = ""

    _expected_task = f"HERMES_KANBAN_TASK={_task_id}".encode()
    _expected_db = f"HERMES_KANBAN_DB={_db_path}".encode() if _db_path else None
    _self_pid = _devkit_os.getpid() if current_pid is None else int(current_pid)
    try:
        _entries = list(_devkit_os.scandir(proc_root))
    except (FileNotFoundError, PermissionError, OSError):
        return None

    for _entry in _entries:
        if not _entry.name.isdigit():
            continue
        _pid = int(_entry.name)
        if _pid <= 0 or _pid == _self_pid:
            continue
        try:
            with open(_devkit_os.path.join(proc_root, _entry.name, "environ"), "rb") as _env_file:
                _env_parts = _env_file.read().split(b"\\0")
        except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
            continue
        if _expected_task not in _env_parts:
            continue
        if _expected_db is not None:
            _db_values = [
                _part.split(b"=", 1)[1]
                for _part in _env_parts
                if _part.startswith(b"HERMES_KANBAN_DB=")
            ]
            if not _db_values:
                continue
            try:
                _process_db = _devkit_os.path.realpath(_db_values[-1].decode())
            except (UnicodeDecodeError, OSError):
                continue
            if _process_db != _db_path:
                continue
        return _pid
    return None
'''
SINGLE_WORKER_CLAIM_REPLACEMENT = '''    _devkit_live_pid = _devkit_find_live_task_process(conn, task_id)
    if _devkit_live_pid is not None:
        # The Kanban row is runnable, but an older process still owns this exact
        # task/board workspace. Do not create a second worker beside it.
        result.respawn_guarded.append((task_id, "live_task_process"))
        return False
    claim = _kb.claim_review_task if lane == "review" else _kb.claim_task
'''


def strict_compile(path: Path) -> None:
    with tempfile.TemporaryDirectory() as directory:
        py_compile.compile(str(path), cfile=str(Path(directory) / "x.pyc"), doraise=True)


def _matches_legacy(source: str) -> bool:
    return source.count(LEGACY_ANCHOR) == 1 and all(item in source for item in LEGACY_CONTEXT)


def _matches_current(source: str) -> bool:
    return source.count(CURRENT_ANCHOR) == 1 and all(item in source for item in CURRENT_CONTEXT)


def candidate(path: Path) -> bool:
    try:
        source = path.read_text(encoding="utf-8")
    except Exception:
        return False
    return PATCH_MARKER in source or _matches_legacy(source) or _matches_current(source)


def find_target(root: Path) -> Path:
    found = [path for path in root.rglob("*.py") if candidate(path)]
    if len(found) != 1:
        raise RuntimeError(
            "expected exactly one Hermes Kanban worker patch target under "
            f"{root}; found {len(found)}: {found[:10]}"
        )
    return found[0]


def _patch_session_affinity(source: str) -> tuple[str, bool]:
    changed = False
    if PATCH_MARKER in source:
        if CONTEXT_MARKER not in source:
            source = source.replace(
                PATCH_MARKER,
                PATCH_MARKER + '\n    env["HERMES_KANBAN_CONTEXT_VERSION"] = "1"',
                1,
            )
            changed = True
        return source, changed
    if _matches_current(source):
        return source.replace(CURRENT_ANCHOR, CURRENT_REPLACEMENT, 1), True
    if _matches_legacy(source):
        return source.replace(LEGACY_ANCHOR, LEGACY_REPLACEMENT, 1), True
    raise RuntimeError("compatible Kanban worker command contract not found")


def _patch_single_worker_guard(source: str) -> tuple[str, bool]:
    changed = False
    if SINGLE_WORKER_HELPER_MARKER not in source:
        if source.count(SINGLE_WORKER_FUNCTION_ANCHOR) != 1:
            raise RuntimeError("compatible Kanban dispatch lane function not found")
        source = source.replace(
            SINGLE_WORKER_FUNCTION_ANCHOR,
            SINGLE_WORKER_HELPER_SOURCE + "\n\n" + SINGLE_WORKER_FUNCTION_ANCHOR,
            1,
        )
        changed = True
    if SINGLE_WORKER_CALL_MARKER not in source:
        if source.count(SINGLE_WORKER_CLAIM_ANCHOR) != 1:
            raise RuntimeError("compatible Kanban claim boundary not found")
        source = source.replace(
            SINGLE_WORKER_CLAIM_ANCHOR,
            SINGLE_WORKER_CLAIM_REPLACEMENT,
            1,
        )
        changed = True
    return source, changed


def patch_source(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source, session_changed = _patch_session_affinity(source)
    source, worker_changed = _patch_single_worker_guard(source)
    changed = session_changed or worker_changed
    if changed:
        path.write_text(source, encoding="utf-8")
    strict_compile(path)
    return "patched" if changed else "already-patched"


def _dispatch_sample() -> str:
    return '''\nclass _KB:\n    @staticmethod\n    def claim_review_task(*a, **k): return "review"\n    @staticmethod\n    def claim_task(*a, **k): return "worker"\n_kb = _KB()\nclass _Result:\n    def __init__(self): self.respawn_guarded = []\ndef _dispatch_lane_task(conn, task_id, lane, result, ttl_seconds=60):\n    claim = _kb.claim_review_task if lane == "review" else _kb.claim_task\n    claimed = claim(conn, task_id, ttl_seconds=ttl_seconds)\n    if claimed is None:\n        return False\n    return True\n'''


def _legacy_sample() -> str:
    return '''def _resolve_worker_cli_toolsets(home): return []\ndef kanban_db_path(board=None): return "/tmp/k"\ndef spawn_worker(task, workspace, *, board=None):\n    profile_arg=task.assignee\n    prompt = f"work kanban task {task.id}"\n    env={"HERMES_HOME":"/tmp/p"}\n    cmd=["hermes"]\n    worker_toolsets = _resolve_worker_cli_toolsets(env.get("HERMES_HOME"))\n    if worker_toolsets:\n        cmd.extend(["--toolsets", ",".join(worker_toolsets)])\n    cmd.extend([\n        "chat",\n        "-q", prompt,\n    ])\n''' + _dispatch_sample()


def _current_sample() -> str:
    return '''def _resolve_worker_cli_toolsets(home): return []\ndef _worker_argv(task, profile_arg, hermes_home):\n    return ["hermes", "-p", profile_arg, "chat", "-q", f"work kanban task {task.id}"]\ndef _default_spawn(task, workspace, *, board=None):\n    profile_arg = task.assignee\n    env = {"HERMES_HOME": "/tmp/p"}\n    env["HERMES_KANBAN_TASK"] = task.id\n    env["HERMES_KANBAN_WORKSPACE"] = workspace\n    env["HERMES_KANBAN_DB"] = "/tmp/kanban.db"\n    env["HERMES_KANBAN_BOARD"] = "demo"\n    env["HERMES_PROFILE"] = profile_arg\n    cmd = _worker_argv(task, profile_arg, env.get("HERMES_HOME"))\n    return cmd\n''' + _dispatch_sample()


def _assert_single_worker_runtime() -> None:
    namespace: dict[str, object] = {}
    exec(SINGLE_WORKER_HELPER_SOURCE, namespace)
    guard = namespace["_devkit_find_live_task_process"]

    with tempfile.TemporaryDirectory(prefix="hermes-kanban-proc-selftest-") as directory:
        root = Path(directory)
        db_path = root / "kanban.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        def proc(pid: int, *env: str) -> None:
            path = root / str(pid)
            path.mkdir()
            (path / "environ").write_bytes(b"\0".join(v.encode() for v in env) + b"\0")

        proc(
            101,
            "HERMES_KANBAN_TASK=t_demo",
            f"HERMES_KANBAN_DB={db_path}",
            "HERMES_PROFILE=coder",
        )
        proc(
            102,
            "HERMES_KANBAN_TASK=t_other",
            f"HERMES_KANBAN_DB={db_path}",
        )
        other_db = root / "other.db"
        proc(
            103,
            "HERMES_KANBAN_TASK=t_demo",
            f"HERMES_KANBAN_DB={other_db}",
        )

        assert guard(conn, "t_demo", proc_root=str(root), current_pid=999) == 101
        assert guard(conn, "t_other", proc_root=str(root), current_pid=999) == 102
        assert guard(conn, "t_missing", proc_root=str(root), current_pid=999) is None

        # A matching pid from another board DB must not block this board.
        (root / "101" / "environ").unlink()
        assert guard(conn, "t_demo", proc_root=str(root), current_pid=999) is None
        conn.close()


def self_test() -> None:
    _assert_single_worker_runtime()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)

        legacy_root = root / "legacy"
        legacy_root.mkdir()
        legacy = legacy_root / "kanban_dispatcher.py"
        legacy.write_text(_legacy_sample(), encoding="utf-8")
        assert find_target(legacy_root) == legacy
        assert patch_source(legacy) == "patched"
        assert patch_source(legacy) == "already-patched"
        legacy_text = legacy.read_text(encoding="utf-8")
        assert CONTEXT_MARKER in legacy_text
        assert 'cmd.extend(["--resume", _devkit_session.session_id])' in legacy_text
        assert SINGLE_WORKER_HELPER_MARKER in legacy_text
        assert SINGLE_WORKER_CALL_MARKER in legacy_text

        current_root = root / "current"
        current_root.mkdir()
        current = current_root / "kanban_db_dispatch.py"
        current.write_text(_current_sample(), encoding="utf-8")
        assert find_target(current_root) == current
        assert patch_source(current) == "patched"
        assert patch_source(current) == "already-patched"
        current_text = current.read_text(encoding="utf-8")
        assert CONTEXT_MARKER in current_text
        assert '_devkit_chat_index = cmd.index("chat")' in current_text
        assert 'cmd[_devkit_chat_index:_devkit_chat_index]' in current_text
        assert 'kanban_db_path=env["HERMES_KANBAN_DB"]' in current_text
        assert SINGLE_WORKER_HELPER_MARKER in current_text
        assert SINGLE_WORKER_CALL_MARKER in current_text
        assert current_text.index(SINGLE_WORKER_CALL_MARKER) < current_text.index(
            'claim = _kb.claim_review_task if lane == "review" else _kb.claim_task'
        )

    print("Hermes Kanban session-affinity/single-worker patch self-test passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--search-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return

    target = find_target(args.search_root) if args.search_root else args.path
    if target is None:
        parser.error("path or --search-root required")
    print(f"Hermes Kanban session-affinity source state={patch_source(target)}: {target}")


if __name__ == "__main__":
    main()
