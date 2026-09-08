#!/usr/bin/env python3
"""Patch Hermes Kanban worker spawning with task/profile session affinity."""
from __future__ import annotations

import argparse
import py_compile
import tempfile
from pathlib import Path

PATCH_MARKER = "from hermes_cli.devkit_session_affinity import choose_worker_session"
ANCHOR = '''    worker_toolsets = _resolve_worker_cli_toolsets(env.get("HERMES_HOME"))
    if worker_toolsets:
        cmd.extend(["--toolsets", ",".join(worker_toolsets)])
    cmd.extend([
        "chat",
        "-q", prompt,
    ])
'''
REPLACEMENT = '''    worker_toolsets = _resolve_worker_cli_toolsets(env.get("HERMES_HOME"))
    if worker_toolsets:
        cmd.extend(["--toolsets", ",".join(worker_toolsets)])

    # DevKit session affinity: one durable session per Kanban task/profile while
    # the execution fingerprint (workspace/branch/Base SHA/model/config/skills)
    # remains unchanged. Any ambiguity falls back to a fresh session.
    from hermes_cli.devkit_session_affinity import choose_worker_session
    _devkit_session = choose_worker_session(
        task=task,
        workspace=workspace,
        profile=profile_arg,
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


def strict_compile(path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="hermes-kanban-session-affinity-") as temp_dir:
        py_compile.compile(str(path), cfile=str(Path(temp_dir) / "kanban_db.pyc"), doraise=True)


def patch_source(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if PATCH_MARKER in source:
        strict_compile(path)
        return "already-patched"
    if "def _default_spawn(" not in source:
        raise RuntimeError(f"{path}: Hermes _default_spawn was not found")
    if source.count(ANCHOR) != 1:
        raise RuntimeError(
            f"{path}: expected exactly one Kanban worker command anchor; "
            f"found {source.count(ANCHOR)}"
        )
    source = source.replace(ANCHOR, REPLACEMENT, 1)
    path.write_text(source, encoding="utf-8")
    strict_compile(path)
    return "patched"


def self_test() -> None:
    sample = '''from __future__ import annotations\n\n\ndef _resolve_worker_cli_toolsets(home):\n    return ["terminal"]\n\ndef kanban_db_path(board=None):\n    return "/tmp/kanban.db"\n\ndef _default_spawn(task, workspace, *, board=None):\n    profile_arg = task.assignee\n    prompt = f"work kanban task {task.id}"\n    env = {"HERMES_HOME": "/tmp/profile"}\n    cmd = ["hermes", "-p", profile_arg, "--cli", "--accept-hooks"]\n    worker_toolsets = _resolve_worker_cli_toolsets(env.get("HERMES_HOME"))\n    if worker_toolsets:\n        cmd.extend(["--toolsets", ",".join(worker_toolsets)])\n    cmd.extend([\n        "chat",\n        "-q", prompt,\n    ])\n    return cmd\n'''
    with tempfile.TemporaryDirectory(prefix="hermes-kanban-session-affinity-selftest-") as temp_dir:
        path = Path(temp_dir) / "kanban_db.py"
        path.write_text(sample, encoding="utf-8")
        if patch_source(path) != "patched":
            raise RuntimeError("self-test: source was not patched")
        if patch_source(path) != "already-patched":
            raise RuntimeError("self-test: patch is not idempotent")
        text = path.read_text(encoding="utf-8")
        required = (
            PATCH_MARKER,
            'env["HERMES_KANBAN_SESSION_MODE"]',
            'env["HERMES_KANBAN_AFFINITY_SESSION_ID"]',
            'cmd.extend(["--resume", _devkit_session.session_id])',
            'kanban_db_path=str(kanban_db_path(board=board))',
            'worker_toolsets=worker_toolsets or ()',
        )
        missing = [term for term in required if term not in text]
        if missing:
            raise RuntimeError(f"self-test: missing patched terms: {missing}")
        if text.index('cmd.extend(["--resume"') > text.index('    cmd.extend([\n        "chat"'):
            raise RuntimeError("self-test: --resume must be a top-level flag before the chat subcommand")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("Hermes Kanban session-affinity patch self-test passed")
        return
    if args.path is None:
        parser.error("path is required unless --self-test is used")
    print(f"Hermes Kanban session-affinity source state={patch_source(args.path)}: {args.path}")


if __name__ == "__main__":
    main()
