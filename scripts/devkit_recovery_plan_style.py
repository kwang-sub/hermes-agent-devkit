#!/usr/bin/env python3
"""Read-only styling for user-visible Hermes Recovery Plan responses.

Highlight recovery plan and change/preserve contracts in visible recovery output.
No Kanban comments, Recovery Revision markers, state or tool data is rewritten.
Reasoning preview styling is display-only and does not replace the required
ordinary assistant response before Clarify approval.
"""
from __future__ import annotations

from typing import NamedTuple
import re
import shutil
import unicodedata

HEADING = "## 🛠 복구 계획"
ACCENT = "#FFB347"
ACCENT_ANSI = "\033[1;38;2;255;179;71m"
BAR_ANSI = "\033[38;2;255;179;71m"
RESET_ANSI = "\033[0m"
PRESERVE_ACCENT = "#22C55E"
PRESERVE_ANSI = "\033[1;38;2;34;197;94m"
PRESERVE_BAR_ANSI = "\033[38;2;34;197;94m"
CHANGE_SECTION = "변경 계약"
PRESERVE_SECTION = "유지 계약"
PLAN_SECTION = "복구 계획"


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


def _render_contract_prefix(text: str):
    """Render contract sections as colored panels without changing stored text."""
    import re
    from rich.console import Group
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.text import Text

    lines = text.splitlines(keepends=True)
    rendered = []
    plain = []
    index = 0
    while index < len(lines):
        heading = lines[index].strip()
        match = re.fullmatch(r"###\s+(변경 계약|유지 계약)", heading)
        if not match:
            plain.append(lines[index])
            index += 1
            continue
        if plain:
            rendered.append(Markdown("".join(plain)))
            plain.clear()
        label = match.group(1)
        index += 1
        body = []
        while index < len(lines) and not (
            lines[index].strip() == "---"
            or re.match(r"^#{2,3}\s+", lines[index].strip())
        ):
            body.append(lines[index])
            index += 1
        accent = ACCENT if label == CHANGE_SECTION else PRESERVE_ACCENT
        rendered.append(Panel(
            Markdown("".join(body)) if "".join(body).strip() else Text(""),
            title=Text(label, style=f"bold {accent}"),
            title_align="left",
            border_style=accent,
            padding=(0, 1),
        ))
    if plain:
        rendered.append(Markdown("".join(plain)))
    return Group(*rendered)


def style_recovery_response(text: str):
    """Return Rich panels for recovery contracts and the plan, if present."""
    parts = split_recovery_response(text)
    if parts is None:
        return None
    from rich.console import Group
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.text import Text

    return Group(
        _render_contract_prefix(parts.before),
        Panel(
            Markdown(parts.plan),
            title=Text("🛠 복구 계획", style=f"bold {ACCENT}"),
            title_align="left",
            border_style=ACCENT,
            padding=(0, 1),
        ),
        Markdown(parts.after),
    )


def _section_from_heading(line: str) -> str | None:
    import re

    normalized = re.sub(r"^#{1,3}\s*", "", line.strip()).strip("* :")
    if normalized in (CHANGE_SECTION, PRESERVE_SECTION, PLAN_SECTION, "🛠 복구 계획"):
        return PLAN_SECTION if normalized == "🛠 복구 계획" else normalized
    return None


def _display_width(value: str) -> int:
    """Terminal columns, accounting for Korean full-width glyphs."""
    return sum(0 if unicodedata.combining(ch) else
               2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
               for ch in value)


def _wrap_visible(text: str, first: str, later: str, width: int) -> str:
    """Wrap content without putting ANSI escapes inside width calculations."""
    result = []
    prefix = first
    line = ""
    for char in text:
        if char == "\n":
            result.append(prefix + line)
            prefix, line = later, ""
            continue
        if _display_width(prefix + line + char) > width and line:
            result.append((prefix + line).rstrip())
            prefix, line = later, ""
            if char.isspace():
                continue
        line += char
    result.append((prefix + line).rstrip())
    return "\n".join(result)


def _style_section_line(line: str, state: str | bool, *, body_color: str = "") -> tuple[str, str | bool]:
    """Style section titles and a single accent gutter, not entire body text.

    Each physical output line fits within the terminal, with hanging indentation
    for numbered steps. Neither source text nor recovery state is modified.
    """
    section = _section_from_heading(line)
    if section:
        accent = PRESERVE_ANSI if section == PRESERVE_SECTION else ACCENT_ANSI
        label = "🛠 복구 계획" if section == PLAN_SECTION else section
        return f"{accent}━━ {label} ━━{RESET_ANSI}", section

    normalized = line.strip()
    if normalized in REASONING_LABELS or normalized == "---" or re.match(r"^#{2,3}\s+", normalized):
        return line, False
    if not state or not normalized:
        return line, state

    # Leave paragraph text in the terminal's regular foreground color.
    # Only the gutter and list marker take the section color.
    accent = PRESERVE_BAR_ANSI if state == PRESERVE_SECTION else BAR_ANSI
    body = re.sub(r"^\s*>\s?", "", line).strip()
    item = re.match(r"^([0-9]+[.)])\s+(.*)$", body)
    content_width = max(24, shutil.get_terminal_size(fallback=(80, 24)).columns - 8)
    if item and state == PLAN_SECTION:
        number, text = item.groups()
        indent = " " * (_display_width(number) + 1)
        wrapped = _wrap_visible(text, "┃ " + number + " ", "┃ " + indent, content_width)
        wrapped = wrapped.replace("┃", f"{accent}┃{RESET_ANSI}")
        wrapped = wrapped.replace(number + " ", f"{accent}{number}{RESET_ANSI} ", 1)
        return wrapped, state

    # Wrapped paragraph continuation uses a neutral gutter without repeated
    # markdown list markers or decorative horizontal separators.
    wrapped = _wrap_visible(body, "┃ ", "┃ ", content_width)
    return wrapped.replace("┃", f"{accent}┃{RESET_ANSI}"), state


def style_stream_line(line: str, in_recovery_plan: str | bool, *, body_color: str = "") -> tuple[str, str | bool]:
    """Color contract and plan sections in the normal assistant text stream."""
    return _style_section_line(line, in_recovery_plan, body_color=body_color)


# Fallback visualization for a plan mistakenly streamed in the dim reasoning box.
# This does NOT satisfy Recovery Gate 3's user-visible assistant-response contract.
REASONING_MARKER = "DEVKIT_RECOVERY_PLAN_REASONING_VISUAL_V1"
REASONING_LABELS = frozenset((
    "작업 복구 분석", "복구 방식", "변경 계약", "유지 계약",
    "차단 원인", "원인 분류", "승인 기준", "검증 계획",
    "금지 사항", "⚠ 금지 사항", "구현 요약", "구현 요약:",
))


def style_reasoning_recovery_line(line: str, active: str | bool) -> tuple[str, str | bool]:
    """Display-only accent for contract and recovery plan sections in reasoning."""
    return _style_section_line(line, active)

