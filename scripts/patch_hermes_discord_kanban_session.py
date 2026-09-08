#!/usr/bin/env python3
"""Augment the DevKit Discord Kanban formatter with worker session context."""
from __future__ import annotations

import argparse
import py_compile
import tempfile
from pathlib import Path

PATCH_MARKER = "notification_session_context("
PAYLOAD_ANCHOR = '''    payload = getattr(event, "payload", None) or {}

    labels = {
'''
PAYLOAD_REPLACEMENT = '''    payload = getattr(event, "payload", None) or {}

    session_profile = assignee
    session_id = "-"
    session_mode = "-"
    try:
        from hermes_cli import kanban_db as _devkit_kb
        from hermes_cli.devkit_session_affinity import notification_session_context

        session_profile, session_id, session_mode = notification_session_context(
            kind=str(kind),
            task=task,
            event=event,
            kanban_db_path=str(_devkit_kb.kanban_db_path(board=board_slug)),
        )
    except Exception:
        # Notifications must remain best-effort. Session-context lookup failure
        # must never suppress the terminal Kanban event itself.
        pass

    labels = {
'''
LINES_ANCHOR = '''        f"담당      {assignee}",
        f"모델      {model}",
        f"상태      {status}",
'''
LINES_REPLACEMENT = '''        f"담당      {assignee}",
        f"프로필    {session_profile}",
        f"모델      {model}",
        f"세션      {session_id}",
        f"세션 방식 {session_mode}",
        f"상태      {status}",
'''


def strict_compile(path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="hermes-discord-kanban-session-") as temp_dir:
        py_compile.compile(str(path), cfile=str(Path(temp_dir) / "notify.pyc"), doraise=True)


def patch_source(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if PATCH_MARKER in source and 'f"세션 방식 {session_mode}"' in source:
        strict_compile(path)
        return "already-patched"
    if "def _devkit_discord_kanban_message(" not in source:
        raise RuntimeError(
            f"{path}: base DevKit Discord formatter is missing; "
            "apply patch_hermes_discord_kanban_notify.py first"
        )
    if source.count(PAYLOAD_ANCHOR) != 1:
        raise RuntimeError(f"{path}: expected one formatter payload anchor")
    if source.count(LINES_ANCHOR) != 1:
        raise RuntimeError(f"{path}: expected one formatter lines anchor")
    source = source.replace(PAYLOAD_ANCHOR, PAYLOAD_REPLACEMENT, 1)
    source = source.replace(LINES_ANCHOR, LINES_REPLACEMENT, 1)
    path.write_text(source, encoding="utf-8")
    strict_compile(path)
    return "patched"


def self_test() -> None:
    sample = '''from __future__ import annotations\n\ndef _devkit_discord_kanban_message(*, kind, task, sub, board_slug, event, fallback):\n    task_id = str(sub.get("task_id") or getattr(task, "id", "") or "-")\n    title = str(getattr(task, "title", "") or task_id)[:160]\n    assignee = str(getattr(task, "assignee", "") or "-")\n    project = str(board_slug or "-")\n    model = "DEFAULT (profile)"\n    payload = getattr(event, "payload", None) or {}\n\n    labels = {\n        "completed": ("✅", "작업 완료", "DONE"),\n    }\n    icon, heading, status = labels.get(kind, ("ℹ️", "작업 상태 변경", str(kind).upper()))\n    lines = [\n        f"{icon} {heading}",\n        "",\n        f"프로젝트  {project}",\n        f"작업      {title}",\n        f"Task      {task_id}",\n        f"담당      {assignee}",\n        f"모델      {model}",\n        f"상태      {status}",\n    ]\n    return "\\n".join(lines)\n'''
    with tempfile.TemporaryDirectory(prefix="hermes-discord-kanban-session-selftest-") as temp_dir:
        path = Path(temp_dir) / "notify.py"
        path.write_text(sample, encoding="utf-8")
        if patch_source(path) != "patched":
            raise RuntimeError("self-test: source was not patched")
        if patch_source(path) != "already-patched":
            raise RuntimeError("self-test: patch is not idempotent")
        text = path.read_text(encoding="utf-8")
        required = (
            "notification_session_context(",
            'f"프로필    {session_profile}"',
            'f"세션      {session_id}"',
            'f"세션 방식 {session_mode}"',
            "kanban_db_path=str(_devkit_kb.kanban_db_path(board=board_slug))",
        )
        missing = [term for term in required if term not in text]
        if missing:
            raise RuntimeError(f"self-test: missing terms: {missing}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("Hermes Discord Kanban session-context patch self-test passed")
        return
    if args.path is None:
        parser.error("path is required unless --self-test is used")
    print(f"Hermes Discord Kanban session-context source state={patch_source(args.path)}: {args.path}")


if __name__ == "__main__":
    main()
