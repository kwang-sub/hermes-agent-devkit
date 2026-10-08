#!/usr/bin/env python3
"""Read-only styling for user-visible Hermes Recovery Plan responses.

Only the exact Markdown heading (H2, tool emoji, Korean plan) is highlighted.
No Kanban comments, Recovery Revision markers, state or tool data is rewritten.
Reasoning text is not styled: the agent must emit the plan as ordinary response
text before the Clarify approval control.
"""
from __future__ import annotations

from typing import NamedTuple

HEADING = "## 🛠 복구 계획"
ACCENT = "#FFB347"
ACCENT_ANSI = "\033[1;38;2;255;179;71m"
BAR_ANSI = "\033[38;2;255;179;71m"
RESET_ANSI = "\033[0m"


class RecoveryParts(NamedTuple):
    before: str
    plan: str
    after: str


def split_recovery_response(text: str) -> RecoveryParts | None:
    """Recognize only a real Recovery heading outside Markdown code fences."""
    lines = text.splitlines(keepends=True)
    fence = None
    start = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(chr(96) * 3) or stripped.startswith("~~~"):
            token = stripped[:3]
            if fence is None:
                fence = token
            elif fence == token:
                fence = None
            continue
        if fence is None and stripped == HEADING:
            start = index
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped == "---" or stripped.startswith("## ") or stripped.startswith("### "):
            end = index
            break
    plan = []
    for line in lines[start + 1:end]:
        if line.lstrip().startswith(">"):
            indent = line[:len(line) - len(line.lstrip())]
            rest = line.lstrip()[1:]
            if rest.startswith(" "):
                rest = rest[1:]
            plan.append(indent + rest)
        else:
            plan.append(line)
    if not "".join(plan).strip():
        return None
    return RecoveryParts("".join(lines[:start]), "".join(plan), "".join(lines[end:]))


def style_recovery_response(text: str):
    """Return a Rich renderable for a Recovery Plan, or None for ordinary text."""
    parts = split_recovery_response(text)
    if parts is None:
        return None
    from rich.console import Group
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.text import Text

    return Group(
        Markdown(parts.before),
        Panel(
            Markdown(parts.plan),
            title=Text("🛠 복구 계획", style=f"bold {ACCENT}"),
            title_align="left",
            border_style=ACCENT,
            padding=(0, 1),
        ),
        Markdown(parts.after),
    )


def style_stream_line(line: str, in_recovery_plan: bool, *, body_color: str = "") -> tuple[str, bool]:
    """Style plan heading and left rule in stream mode; do not mutate source text."""
    normalized = line.strip()
    if normalized == HEADING:
        return f"{ACCENT_ANSI}━━ 🛠 복구 계획 ━━{RESET_ANSI}", True
    if in_recovery_plan and (
        normalized == "---" or normalized.startswith("## ") or normalized.startswith("### ")
    ):
        return line, False
    if in_recovery_plan and normalized.startswith(">"):
        tail = normalized[1:].lstrip()
        return f"{BAR_ANSI}┃{RESET_ANSI}{body_color} {tail}", True
    return line, in_recovery_plan
