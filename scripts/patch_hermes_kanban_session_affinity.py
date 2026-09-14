#!/usr/bin/env python3
from __future__ import annotations

import argparse
import py_compile
import sqlite3
import tempfile
from pathlib import Path

PATCH_MARKER = "from hermes_cli.devkit_session_affinity import choose_worker_session"
CONTEXT_MARKER = 'env["HERMES_KANBAN_CONTEXT_VERSION"] = "1"'
SINGLE_WORKER_HELPER_MARKER = "def _devkit_live_prior_worker("
SINGLE_WORKER_CALL_MARKER = 'result.respawn_guarded.append((task_id, "live_prior_worker"))'

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

# The kernel already serializes ready->running claims. This guard handles the
# narrower handoff window where an older run has been terminally closed or
# explicitly reclaimed while its host-local process is still alive. The next
# run stays queued until that exact task process exits, so two workers can never
# edit the same task workspace concurrently.
SINGLE_WORKER_FUNCTION_ANCHOR = "def _dispatch_lane_task("
SINGLE_WORKER_CLAIM_ANCHOR = '''    claim = _kb.claim_review_task if lane == "review" else _kb.claim_task
'''
SINGLE_WORKER_HELPER_SOURCE = '''def _devkit_live_prior_worker(
    conn, task_id, *, pid_alive, host_prefix, process_task_match=None,
    now=None, unknown_grace_seconds=120,
):
    import sqlite3 as _devkit_sqlite3
    import time as _devkit_time

    _task_id = str(task_id or "").strip()
    _host_prefix_value = str(host_prefix or "").strip()
    if not _task_id or not _host_prefix_value:
        return None
    _now = int(_devkit_time.time()) if now is None else int(now)
    try:
        _rows = conn.execute(
            """
            SELECT id, worker_pid, claim_lock, ended_at
              FROM task_runs
             WHERE task_id = ?
               AND worker_pid IS NOT NULL
               AND ended_at IS NOT NULL
             ORDER BY id DESC
             LIMIT 8
            """,
            (_task_id,),
        ).fetchall()
    except _devkit_sqlite3.Error:
        # Older upstream schemas must remain bootable; claim CAS still protects
        # the normal ready->running race when run history is unavailable.
        return None

    for _row in _rows:
        try:
            _run_id = int(_row["id"])
            _pid = int(_row["worker_pid"])
            _ended_at = int(_row["ended_at"])
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        _claim_lock = str(_row["claim_lock"] or "")
        if _pid <= 0 or not _claim_lock.startswith(_host_prefix_value):
            continue
        try:
            if not pid_alive(_pid):
                continue
        except Exception:
            continue

        if process_task_match is not None:
            try:
                _identity = process_task_match(_pid, _task_id)
            except Exception:
                _identity = None
        else:
            try:
                with open(f"/proc/{_pid}/environ", "rb") as _env_file:
                    _env = _env_file.read()
                _expected = f"HERMES_KANBAN_TASK={_task_id}".encode()
                _identity = _expected in _env.split(b"\\0")
            except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
                _identity = None

        if _identity is False:
            # The PID is alive but no longer belongs to this task: PID reuse.
            continue
        if _identity is None and _now - _ended_at > max(0, int(unknown_grace_seconds)):
            # When process identity cannot be inspected, be conservative only
            # during the short process-shutdown handoff window.
            continue
        return (_run_id, _pid)
    return None
'''
SINGLE_WORKER_CLAIM_REPLACEMENT = '''    _devkit_prior_worker = _devkit_live_prior_worker(
        conn,
        task_id,
        pid_alive=_kb._pid_alive,
        host_prefix=_kb._host_prefix(),
    )
    if _devkit_prior_worker is not None:
        # A previous run is terminal in Kanban but its process still owns the
        # workspace. Keep this card queued until that process is really gone.
        result.respawn_guarded.append((task_id, "live_prior_worker"))
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
    return '''\nclass _KB:\n    @staticmethod\n    def claim_review_task(*a, **k): return "review"\n    @staticmethod\n    def claim_task(*a, **k): return "worker"\n    @staticmethod\n    def _pid_alive(pid): return True\n    @staticmethod\n    def _host_prefix(): return "host-a:"\n_kb = _KB()\nclass _Result:\n    def __init__(self): self.respawn_guarded = []\ndef _dispatch_lane_task(conn, task_id, lane, result, ttl_seconds=60):\n    claim = _kb.claim_review_task if lane == "review" else _kb.claim_task\n    claimed = claim(conn, task_id, ttl_seconds=ttl_seconds)\n    if claimed is None:\n        return False\n    return True\n'''


def _legacy_sample() -> str:
    return '''def _resolve_worker_cli_toolsets(home): return []\ndef kanban_db_path(board=None): return "/tmp/k"\ndef spawn_worker(task, workspace, *, board=None):\n    profile_arg=task.assignee\n    prompt = f"work kanban task {task.id}"\n    env={"HERMES_HOME":"/tmp/p"}\n    cmd=["hermes"]\n    worker_toolsets = _resolve_worker_cli_toolsets(env.get("HERMES_HOME"))\n    if worker_toolsets:\n        cmd.extend(["--toolsets", ",".join(worker_toolsets)])\n    cmd.extend([\n        "chat",\n        "-q", prompt,\n    ])\n''' + _dispatch_sample()


def _current_sample() -> str:
    return '''def _resolve_worker_cli_toolsets(home): return []\ndef _worker_argv(task, profile_arg, hermes_home):\n    return ["hermes", "-p", profile_arg, "chat", "-q", f"work kanban task {task.id}"]\ndef _default_spawn(task, workspace, *, board=None):\n    profile_arg = task.assignee\n    env = {"HERMES_HOME": "/tmp/p"}\n    env["HERMES_KANBAN_TASK"] = task.id\n    env["HERMES_KANBAN_WORKSPACE"] = workspace\n    env["HERMES_KANBAN_DB"] = "/tmp/kanban.db"\n    env["HERMES_KANBAN_BOARD"] = "demo"\n    env["HERMES_PROFILE"] = profile_arg\n    cmd = _worker_argv(task, profile_arg, env.get("HERMES_HOME"))\n    return cmd\n''' + _dispatch_sample()


def _assert_single_worker_runtime() -> None:
    namespace: dict[str, object] = {}
    exec(SINGLE_WORKER_HELPER_SOURCE, namespace)
    guard = namespace["_devkit_live_prior_worker"]

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE task_runs(id INTEGER PRIMARY KEY, task_id TEXT, worker_pid INTEGER, claim_lock TEXT, ended_at INTEGER)"
    )
    conn.executemany(
        "INSERT INTO task_runs VALUES (?, ?, ?, ?, ?)",
        [
            (1, "t_demo", 101, "host-a:old", 100),
            (2, "t_demo", 102, "host-b:other", 995),
            (3, "t_demo", 103, "host-a:latest", 997),
        ],
    )

    found = guard(
        conn,
        "t_demo",
        pid_alive=lambda pid: pid in {101, 102, 103},
        host_prefix="host-a:",
        process_task_match=lambda pid, task: pid == 103 and task == "t_demo",
        now=1000,
    )
    assert found == (3, 103)

    # PID reuse must not block a new run.
    assert guard(
        conn,
        "t_demo",
        pid_alive=lambda _pid: True,
        host_prefix="host-a:",
        process_task_match=lambda _pid, _task: False,
        now=1000,
    ) is None

    # Unknown process identity is held only in the immediate shutdown window.
    assert guard(
        conn,
        "t_demo",
        pid_alive=lambda pid: pid == 103,
        host_prefix="host-a:",
        process_task_match=lambda _pid, _task: None,
        now=1000,
        unknown_grace_seconds=10,
    ) == (3, 103)
    assert guard(
        conn,
        "t_demo",
        pid_alive=lambda pid: pid == 101,
        host_prefix="host-a:",
        process_task_match=lambda _pid, _task: None,
        now=1000,
        unknown_grace_seconds=10,
    ) is None
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
