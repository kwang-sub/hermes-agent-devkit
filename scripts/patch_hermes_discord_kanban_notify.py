#!/usr/bin/env python3
from __future__ import annotations

import argparse
import py_compile
import tempfile
from pathlib import Path

FORMATTER_MARKER = "def _devkit_discord_kanban_message("
CLASS_MARKER = "\n\nclass GatewayKanbanWatchersMixin:"
SEND_NEEDLE = '''                            _send_res = await adapter.send(\n                                sub["chat_id"], msg, metadata=metadata,\n                            )'''
SEND_PATCH = '''                            if platform_str == "discord":\n                                msg = _devkit_discord_kanban_message(\n                                    kind=kind, task=task, sub=sub, board_slug=board_slug,\n                                    event=ev, fallback=msg,\n                                )\n                            _send_res = await adapter.send(\n                                sub["chat_id"], msg, metadata=metadata,\n                            )'''

FORMATTER = r'''

def _devkit_discord_kanban_message(*, kind, task, sub, board_slug, event, fallback):
    """Return the DevKit's compact Korean Discord Kanban notification."""
    task_id = str(sub.get("task_id") or getattr(task, "id", "") or "-")
    title = str(getattr(task, "title", "") or task_id)[:160]
    assignee = str(getattr(task, "assignee", "") or "-")
    project = str(board_slug or "-")
    payload = getattr(event, "payload", None) or {}

    labels = {
        "completed": ("✅", "작업 완료", "DONE"),
        "blocked": ("⛔", "작업 차단", "BLOCKED"),
        "gave_up": ("❌", "작업 실패", "GAVE_UP"),
        "crashed": ("💥", "작업 비정상 종료", "CRASHED"),
        "timed_out": ("⏱️", "작업 시간 초과", "TIMED_OUT"),
        "review_requested": ("🔎", "리뷰 요청", "REVIEW"),
        "changes_requested": ("🛠️", "수정 요청", "CHANGES_REQUESTED"),
        "block_loop_detected": ("⚠️", "반복 차단 감지", "TRIAGE"),
    }
    icon, heading, status = labels.get(kind, ("ℹ️", "작업 상태 변경", str(kind).upper()))

    detail = ""
    detail_label = "상세"
    if kind == "blocked":
        detail_label = "사유"
        detail = str(payload.get("reason") or "")
    elif kind in {"gave_up", "crashed", "timed_out"}:
        detail_label = "오류"
        detail = str(payload.get("error") or payload.get("reason") or "")
    elif kind in {"review_requested", "changes_requested", "block_loop_detected"}:
        detail_label = "내용"
        detail = str(payload.get("reason") or payload.get("summary") or "")
    elif kind == "completed":
        detail_label = "결과"
        detail = str(payload.get("result") or payload.get("summary") or "")

    if detail:
        try:
            detail = _safe_review_reason(detail, limit=500)
        except Exception:
            detail = " ".join(detail.split())[:500]

    lines = [
        f"{icon} {heading}",
        "",
        f"프로젝트  {project}",
        f"작업      {title}",
        f"Task      {task_id}",
        f"담당      {assignee}",
        f"상태      {status}",
    ]
    if detail:
        lines.extend(["", detail_label, detail])
    elif fallback and kind not in labels:
        lines.extend(["", "상세", str(fallback)[:500]])
    return "\n".join(lines)
'''


def strict_compile(path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="hermes-discord-kanban-notify-") as temp_dir:
        py_compile.compile(str(path), cfile=str(Path(temp_dir) / "notify.pyc"), doraise=True)


def patch_source(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    state = "already-patched"

    if FORMATTER_MARKER not in source:
        if CLASS_MARKER not in source:
            raise RuntimeError(f"{path}: GatewayKanbanWatchersMixin marker not found")
        source = source.replace(CLASS_MARKER, FORMATTER + CLASS_MARKER, 1)
        state = "patched"

    if SEND_PATCH not in source:
        count = source.count(SEND_NEEDLE)
        if count != 1:
            raise RuntimeError(f"{path}: expected one notifier send site, found {count}")
        source = source.replace(SEND_NEEDLE, SEND_PATCH, 1)
        state = "patched"

    path.write_text(source, encoding="utf-8")
    strict_compile(path)
    return state


def self_test() -> None:
    sample = '''from __future__ import annotations\n\ndef _safe_review_reason(value, limit=160):\n    return str(value)[:limit]\n\nclass GatewayKanbanWatchersMixin:\n    async def run(self, adapter, sub, metadata, platform_str, kind, task, board_slug, ev, msg):\n        try:\n                            _send_res = await adapter.send(\n                                sub["chat_id"], msg, metadata=metadata,\n                            )\n        except Exception:\n            pass\n'''
    with tempfile.TemporaryDirectory(prefix="hermes-discord-kanban-selftest-") as temp_dir:
        path = Path(temp_dir) / "kanban_watchers.py"
        path.write_text(sample, encoding="utf-8")
        if patch_source(path) != "patched":
            raise RuntimeError("self-test: source was not patched")
        if patch_source(path) != "already-patched":
            raise RuntimeError("self-test: patch is not idempotent")
        text = path.read_text(encoding="utf-8")
        for term in ("⛔", "프로젝트", "작업      {title}", "상태      {status}", "platform_str == \"discord\""):
            if term not in text:
                raise RuntimeError(f"self-test: missing {term}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("Hermes Discord Kanban notification patch self-test passed")
        return
    if args.path is None:
        parser.error("path is required unless --self-test is used")
    state = patch_source(args.path)
    print(f"Hermes Discord Kanban notification source state={state}: {args.path}")


if __name__ == "__main__":
    main()
