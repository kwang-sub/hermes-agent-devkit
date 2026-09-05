#!/usr/bin/env python3
from __future__ import annotations

import argparse
import py_compile
import re
import tempfile
from pathlib import Path

FORMATTER_MARKER = "def _devkit_discord_kanban_message("
LEGACY_CLASS_MARKER = "\n\nclass GatewayKanbanWatchersMixin:"
NOTIFIER_CLASS_MARKER = "\n\nclass _KanbanNotification:"

LEGACY_SEND_RE = re.compile(
    r'(?P<indent>^[ \t]*)_send_res\s*=\s*await\s+adapter\.send\(\s*\n'
    r'(?P=indent)[ \t]+sub\["chat_id"\],\s*msg,\s*metadata=metadata,?\s*\n'
    r'(?P=indent)\)',
    re.MULTILINE,
)
NOTIFIER_SEND_RE = re.compile(
    r'(?P<indent>^[ \t]*)_send_res\s*=\s*await\s+adapter\.send\('
    r'sub\["chat_id"\],\s*msg,\s*metadata=metadata\)',
    re.MULTILINE,
)

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
        detail = str(
            payload.get("result")
            or payload.get("summary")
            or getattr(task, "result", "")
            or ""
        )

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


def _insert_formatter(source: str, class_marker: str, path: Path) -> tuple[str, bool]:
    if FORMATTER_MARKER in source:
        return source, False
    if class_marker not in source:
        raise RuntimeError(f"{path}: formatter insertion marker not found")
    return source.replace(class_marker, FORMATTER + class_marker, 1), True


def _patch_legacy(source: str, path: Path) -> tuple[str, bool]:
    source, changed = _insert_formatter(source, LEGACY_CLASS_MARKER, path)
    if 'platform_str == "discord"' in source:
        return source, changed

    matches = list(LEGACY_SEND_RE.finditer(source))
    if len(matches) != 1:
        raise RuntimeError(f"{path}: expected one legacy notifier send site, found {len(matches)}")

    match = matches[0]
    indent = match.group("indent")
    replacement = (
        f'{indent}if platform_str == "discord":\n'
        f'{indent}    msg = _devkit_discord_kanban_message(\n'
        f'{indent}        kind=kind, task=task, sub=sub, board_slug=board_slug,\n'
        f'{indent}        event=ev, fallback=msg,\n'
        f'{indent}    )\n'
        f'{match.group(0)}'
    )
    source = source[:match.start()] + replacement + source[match.end():]
    return source, True


def _patch_notifier(source: str, path: Path) -> tuple[str, bool]:
    source, changed = _insert_formatter(source, NOTIFIER_CLASS_MARKER, path)
    if 'self.platform_str == "discord"' in source:
        return source, changed

    matches = list(NOTIFIER_SEND_RE.finditer(source))
    if len(matches) != 1:
        raise RuntimeError(f"{path}: expected one notifier send site, found {len(matches)}")

    match = matches[0]
    indent = match.group("indent")
    replacement = (
        f'{indent}if self.platform_str == "discord":\n'
        f'{indent}    msg = _devkit_discord_kanban_message(\n'
        f'{indent}        kind=ev.kind, task=self.task, sub=sub, board_slug=self.board_slug,\n'
        f'{indent}        event=ev, fallback=msg,\n'
        f'{indent}    )\n'
        f'{match.group(0)}'
    )
    source = source[:match.start()] + replacement + source[match.end():]
    return source, True


def patch_source(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if "class _KanbanNotification:" in source:
        source, changed = _patch_notifier(source, path)
        mode = "notifier"
    elif "class GatewayKanbanWatchersMixin:" in source:
        source, changed = _patch_legacy(source, path)
        mode = "legacy"
    else:
        raise RuntimeError(f"{path}: unsupported Hermes Kanban notifier layout")

    path.write_text(source, encoding="utf-8")
    strict_compile(path)
    return f"patched-{mode}" if changed else f"already-patched-{mode}"


def _assert_terms(path: Path, terms: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    for term in terms:
        if term not in text:
            raise RuntimeError(f"self-test: missing {term}")


def self_test() -> None:
    legacy_sample = '''from __future__ import annotations\n\ndef _safe_review_reason(value, limit=160):\n    return str(value)[:limit]\n\nclass GatewayKanbanWatchersMixin:\n    async def run(self, adapter, sub, metadata, platform_str, kind, task, board_slug, ev, msg):\n        try:\n                            _send_res = await adapter.send(\n                                sub["chat_id"], msg, metadata=metadata,\n                            )\n        except Exception:\n            pass\n'''
    notifier_sample = '''from __future__ import annotations\n\ndef _safe_review_reason(value, limit=160):\n    return str(value)[:limit]\n\nclass _KanbanNotification:\n    def __init__(self):\n        self.platform_str = "discord"\n        self.task = None\n        self.board_slug = "board"\n        self.sub = {"task_id": "t_1", "chat_id": "c_1"}\n        self.adapter = None\n\n    async def _send_event(self, ev, msg):\n        sub, adapter = self.sub, self.adapter\n        metadata = {}\n        _send_res = await adapter.send(sub["chat_id"], msg, metadata=metadata)\n'''

    cases = (
        ("legacy", legacy_sample, "patched-legacy", "already-patched-legacy", 'platform_str == "discord"'),
        ("notifier", notifier_sample, "patched-notifier", "already-patched-notifier", 'self.platform_str == "discord"'),
    )
    with tempfile.TemporaryDirectory(prefix="hermes-discord-kanban-selftest-") as temp_dir:
        for name, sample, patched_state, idempotent_state, platform_term in cases:
            path = Path(temp_dir) / f"{name}.py"
            path.write_text(sample, encoding="utf-8")
            if patch_source(path) != patched_state:
                raise RuntimeError(f"self-test {name}: source was not patched")
            if patch_source(path) != idempotent_state:
                raise RuntimeError(f"self-test {name}: patch is not idempotent")
            _assert_terms(path, (
                "⛔",
                "프로젝트",
                "작업      {title}",
                "상태      {status}",
                platform_term,
                'getattr(task, "result", "")',
            ))


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
