#!/usr/bin/env python3
"""Add a narrowly scoped Recovery Plan presentation style to classic Hermes CLI.

Keep all existing reasoning, Clarify, Kanban, and streamed message content
semantics unchanged. Only style the user-visible Recovery Plan marker.
Fail closed if an upstream source anchor changes.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import tempfile

RENDER_MARKER = "DEVKIT_RECOVERY_PLAN_RENDER_V1"
STREAM_MARKER = "DEVKIT_RECOVERY_PLAN_STREAM_V1"
RESET_MARKER = "DEVKIT_RECOVERY_PLAN_STREAM_RESET_V1"

RENDER_ANCHOR = "    return Markdown(plain)\n"
RENDER_REPLACEMENT = (
    "    # " + RENDER_MARKER + ": style only normal assistant Recovery Plan responses.\n"
    "    from hermes_cli.devkit_recovery_plan_style import style_recovery_response\n"
    "    styled = style_recovery_response(plain)\n"
    "    if styled is not None:\n"
    "        return styled\n"
    + RENDER_ANCHOR
)

STREAM_ANCHOR = (
    '        _tc = getattr(self, "_stream_text_ansi", "")\n'
    '        _cprint(\n'
)
STREAM_REPLACEMENT = (
    '        _tc = getattr(self, "_stream_text_ansi", "")\n'
    '        # ' + STREAM_MARKER + ': recover plan emphasis in normal response stream.\n'
    '        from hermes_cli.devkit_recovery_plan_style import style_stream_line\n'
    '        printed_line, active = style_stream_line(\n'
    '            printed_line, bool(getattr(self, "_devkit_recovery_plan_active", False)),\n'
    '            body_color=_tc,\n'
    '        )\n'
    '        self._devkit_recovery_plan_active = active\n'
    '        _cprint(\n'
)

RESET_ANCHOR = (
    '    def _reset_stream_state(self) -> None:\n'
    '        """Reset streaming state before each agent invocation."""\n'
    '        self._stream_buf = ""\n'
)
RESET_REPLACEMENT = RESET_ANCHOR + (
    '        self._devkit_recovery_plan_active = False  # '
    + RESET_MARKER + '\n'
)


def replace_once(text: str, before: str, after: str, name: str) -> str:
    count = text.count(before)
    if count != 1:
        raise RuntimeError(f"{name}: expected exactly one upstream anchor, found {count}")
    return text.replace(before, after, 1)


def patch_render(text: str) -> str:
    if RENDER_MARKER in text:
        return text
    return replace_once(text, RENDER_ANCHOR, RENDER_REPLACEMENT, "Rich assistant response")


def patch_stream(text: str) -> str:
    if STREAM_MARKER not in text:
        text = replace_once(text, STREAM_ANCHOR, STREAM_REPLACEMENT, "stream response line")
    if RESET_MARKER not in text:
        text = replace_once(text, RESET_ANCHOR, RESET_REPLACEMENT, "stream per-turn reset")
    return text


def _write_source(path: Path, func) -> None:
    source = path.read_text(encoding="utf-8")
    updated = func(source)
    ast.parse(updated, filename=str(path))
    if updated != source:
        path.write_text(updated, encoding="utf-8")


def check(render_path: Path, stream_path: Path) -> None:
    for path, markers in (
        (render_path, (RENDER_MARKER,)),
        (stream_path, (STREAM_MARKER, RESET_MARKER)),
    ):
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                raise RuntimeError(f"{path}: missing style marker {marker}")
        ast.parse(text, filename=str(path))


def self_test() -> None:
    render = (
        "def _render_final_assistant_content(plain):\n"
        "    from rich.markdown import Markdown\n"
        + RENDER_ANCHOR
    )
    stream = (
        "class Sample:\n"
        "    def _emit_stream_line(self, printed_line):\n"
        "        from cli import _RST, _STREAM_PAD, _cprint\n"
        + STREAM_ANCHOR
        + '            f"{_STREAM_PAD}{_tc}{printed_line}{_RST}" '
          'if _tc else f"{_STREAM_PAD}{printed_line}")\n\n'
        + RESET_ANCHOR
        + '        self._stream_started = False\n'
    )
    with tempfile.TemporaryDirectory(prefix="devkit-recovery-style-") as temp:
        root = Path(temp)
        rich_path = root / "cli_render.py"
        stream_path = root / "cli_stream_mixin.py"
        rich_path.write_text(render, encoding="utf-8")
        stream_path.write_text(stream, encoding="utf-8")
        _write_source(rich_path, patch_render)
        _write_source(stream_path, patch_stream)
        check(rich_path, stream_path)
        assert patch_render(rich_path.read_text(encoding="utf-8")) == rich_path.read_text(encoding="utf-8")
        assert patch_stream(stream_path.read_text(encoding="utf-8")) == stream_path.read_text(encoding="utf-8")
        assert "_devkit_recovery_plan_active" in stream_path.read_text(encoding="utf-8")
        try:
            patch_stream("class ChangedUpstream: pass\n")
        except RuntimeError:
            pass
        else:
            raise AssertionError("changed upstream render contract must fail closed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-root", default="/opt/hermes")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("PASS: Recovery Plan TUI style patch fixtures")
        return 0

    root = Path(args.hermes_root)
    render_path = root / "hermes_cli/cli_render.py"
    stream_path = root / "hermes_cli/cli_stream_mixin.py"
    if not render_path.is_file() or not stream_path.is_file():
        raise SystemExit("missing Hermes classic CLI response render modules")
    if not args.check_only:
        _write_source(render_path, patch_render)
        _write_source(stream_path, patch_stream)
    check(render_path, stream_path)
    print("PASS: Recovery Plan classic CLI normal-response highlight")


if __name__ == "__main__":
    raise SystemExit(main())
