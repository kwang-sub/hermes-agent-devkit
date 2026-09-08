#!/usr/bin/env python3
from __future__ import annotations

import argparse
import py_compile
import tempfile
from pathlib import Path

PATCH_MARKER = "from hermes_cli.devkit_session_affinity import choose_worker_session"
CONTEXT_MARKER = 'env["HERMES_KANBAN_CONTEXT_VERSION"] = "1"'

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


def patch_source(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if PATCH_MARKER in source:
        if CONTEXT_MARKER not in source:
            source = source.replace(PATCH_MARKER, PATCH_MARKER + '\n    env["HERMES_KANBAN_CONTEXT_VERSION"] = "1"', 1)
            path.write_text(source, encoding="utf-8")
        strict_compile(path)
        return "already-patched"

    if _matches_current(source):
        updated = source.replace(CURRENT_ANCHOR, CURRENT_REPLACEMENT, 1)
    elif _matches_legacy(source):
        updated = source.replace(LEGACY_ANCHOR, LEGACY_REPLACEMENT, 1)
    else:
        raise RuntimeError(f"{path}: compatible Kanban worker command contract not found")

    path.write_text(updated, encoding="utf-8")
    strict_compile(path)
    return "patched"


def _legacy_sample() -> str:
    return '''def _resolve_worker_cli_toolsets(home): return []\ndef kanban_db_path(board=None): return "/tmp/k"\ndef spawn_worker(task, workspace, *, board=None):\n    profile_arg=task.assignee\n    prompt = f"work kanban task {task.id}"\n    env={"HERMES_HOME":"/tmp/p"}\n    cmd=["hermes"]\n    worker_toolsets = _resolve_worker_cli_toolsets(env.get("HERMES_HOME"))\n    if worker_toolsets:\n        cmd.extend(["--toolsets", ",".join(worker_toolsets)])\n    cmd.extend([\n        "chat",\n        "-q", prompt,\n    ])\n'''


def _current_sample() -> str:
    return '''def _resolve_worker_cli_toolsets(home): return []\ndef _worker_argv(task, profile_arg, hermes_home):\n    return ["hermes", "-p", profile_arg, "chat", "-q", f"work kanban task {task.id}"]\ndef _default_spawn(task, workspace, *, board=None):\n    profile_arg = task.assignee\n    env = {"HERMES_HOME": "/tmp/p"}\n    env["HERMES_KANBAN_TASK"] = task.id\n    env["HERMES_KANBAN_WORKSPACE"] = workspace\n    env["HERMES_KANBAN_DB"] = "/tmp/kanban.db"\n    env["HERMES_KANBAN_BOARD"] = "demo"\n    env["HERMES_PROFILE"] = profile_arg\n    cmd = _worker_argv(task, profile_arg, env.get("HERMES_HOME"))\n    return cmd\n'''


def self_test() -> None:
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

    print("Hermes Kanban session-affinity patch self-test passed")


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
