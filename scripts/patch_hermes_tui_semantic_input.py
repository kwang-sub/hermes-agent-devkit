#!/usr/bin/env python3
"""Patch Hermes CLI clarify surfaces with semantic user-input colors.

The DevKit keeps reasoning output dim while making interactive Clarify UI visually
distinct: cyan for required user input and green for the recommended option.
"""

from __future__ import annotations

import argparse
import py_compile
import re
import tempfile
from pathlib import Path

MARKER = "DEVKIT_TUI_SEMANTIC_INPUT_V1"

STYLE_TARGETS = {
    "clarify-border": "#00AFFF",
    "clarify-title": "#00D7FF bold",
    "clarify-question": "#FFFFFF bold",
    "clarify-choice": "#B8B8B8",
    "clarify-selected": "#00D7FF bold",
    "clarify-recommended": "#5FFF87 bold",
    "clarify-active-other": "#00D7FF italic",
}

RECOMMENDED_BRANCH = 'if "(Recommended)" in choice:'
PROMPT_TARGET = 'return _state_fragment("class:clarify-selected", "?")'
SUMMARY_TARGET = 'if label == "Clarify":'


def compile_source(path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="hermes-tui-semantic-input-") as temp_dir:
        py_compile.compile(
            str(path),
            cfile=str(Path(temp_dir) / f"{path.stem}.pyc"),
            doraise=True,
        )


def _style_pattern(key: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?m)^(?P<indent>\s*)(?P<keyq>['\"]){re.escape(key)}(?P=keyq)"
        rf"(?P<sep>\s*:\s*)(?P<valueq>['\"])(?P<value>[^'\"]*)(?P=valueq)"
        rf"(?P<tail>\s*,?\s*)$"
    )


def _set_style(source: str, key: str, value: str, *, required: bool) -> tuple[str, int]:
    pattern = _style_pattern(key)
    match = pattern.search(source)
    if not match:
        if required:
            raise RuntimeError(f"missing expected Hermes TUI style key: {key}")
        return source, 0

    def repl(m: re.Match[str]) -> str:
        quote = m.group("valueq")
        return (
            f"{m.group('indent')}{m.group('keyq')}{key}{m.group('keyq')}"
            f"{m.group('sep')}{quote}{value}{quote}{m.group('tail')}"
        )

    return pattern.sub(repl, source, count=1), 1


def patch_tui_source(path: Path) -> str:
    original = path.read_text(encoding="utf-8")
    source = original

    # Existing clarify roles are normalized rather than matched by their old colors,
    # so a harmless upstream palette tweak does not break the DevKit patch.
    for key, value in STYLE_TARGETS.items():
        if key == "clarify-recommended":
            continue
        source, _ = _set_style(source, key, value, required=True)

    # Add a dedicated recommendation role immediately after the selected role.
    if not _style_pattern("clarify-recommended").search(source):
        selected = _style_pattern("clarify-selected").search(source)
        if not selected:
            raise RuntimeError("cannot add clarify-recommended style: clarify-selected anchor missing")
        indent = selected.group("indent")
        quote = selected.group("keyq")
        insertion = (
            selected.group(0)
            + f"\n{indent}{quote}clarify-recommended{quote}: "
            + f"{quote}{STYLE_TARGETS['clarify-recommended']}{quote},"
        )
        source = source[: selected.start()] + insertion + source[selected.end() :]
    else:
        source, _ = _set_style(
            source, "clarify-recommended", STYLE_TARGETS["clarify-recommended"], required=True
        )

    # The normal Clarify prompt should use the same semantic input role instead of the
    # generic working/spinner role.
    if PROMPT_TARGET not in source:
        prompt_pattern = re.compile(
            r'(?m)^(?P<indent>\s*)return _state_fragment\('
            r'(?P<q1>[\'\"])class:prompt-working(?P=q1),\s*'
            r'(?P<q2>[\'\"])\?(?P=q2)\)\s*$'
        )
        matches = list(prompt_pattern.finditer(source))
        if len(matches) != 1:
            raise RuntimeError(
                f"expected exactly one Clarify prompt-working return, found {len(matches)}"
            )
        m = matches[0]
        replacement = f'{m.group("indent")}{PROMPT_TARGET}'
        source = source[: m.start()] + replacement + source[m.end() :]

    # Recommended choices get a stable green role. This intentionally takes precedence
    # over the selected-row cyan role so the recommended option is visible immediately.
    # Hermes currently has both single-question and batch-question renderers, so patch
    # every renderer that uses the canonical selected/choice style assignment.
    if RECOMMENDED_BRANCH not in source:
        choice_pattern = re.compile(
            r'(?m)^(?P<indent>\s*)style\s*=\s*'
            r'(?P<q1>[\'\"])class:clarify-selected(?P=q1)\s+if\s+'
            r'i\s*==\s*selected\s+and\s+not\s+freetext\s+else\s+'
            r'(?P<q2>[\'\"])class:clarify-choice(?P=q2)\s*$'
        )
        matches = list(choice_pattern.finditer(source))
        if not matches:
            raise RuntimeError("expected at least one Clarify choice style assignment")

        def replace_choice(m: re.Match[str]) -> str:
            i = m.group("indent")
            return (
                f'{i}if "(Recommended)" in choice:\n'
                f"{i}    style = 'class:clarify-recommended'\n"
                f"{i}elif i == selected and not freetext:\n"
                f"{i}    style = 'class:clarify-selected'\n"
                f"{i}else:\n"
                f"{i}    style = 'class:clarify-choice'"
            )

        source = choice_pattern.sub(replace_choice, source)

    if MARKER not in source:
        border = _style_pattern("clarify-border").search(source)
        if not border:
            raise RuntimeError("cannot place semantic-input marker: clarify-border anchor missing")
        indent = border.group("indent")
        comment = f"{indent}# {MARKER}: cyan=user input, green=recommended\n"
        source = source[: border.start()] + comment + source[border.start() :]

    path.write_text(source, encoding="utf-8")
    validate_tui_source(path)
    return "already-patched" if source == original else "patched"


def validate_tui_source(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if MARKER not in source:
        raise RuntimeError(f"{path}: semantic-input marker missing")
    for key, expected in STYLE_TARGETS.items():
        match = _style_pattern(key).search(source)
        if not match or match.group("value") != expected:
            got = match.group("value") if match else "<missing>"
            raise RuntimeError(f"{path}: style {key}={got!r}, expected {expected!r}")
    if PROMPT_TARGET not in source:
        raise RuntimeError(f"{path}: Clarify prompt is not using clarify-selected style")
    if RECOMMENDED_BRANCH not in source or "style = 'class:clarify-recommended'" not in source:
        raise RuntimeError(f"{path}: recommended choice semantic style is missing")
    compile_source(path)


def patch_session_source(path: Path) -> str:
    original = path.read_text(encoding="utf-8")
    source = original

    if SUMMARY_TARGET not in source:
        old = re.compile(
            r'(?m)^(?P<indent>\s*)_cprint\(f"\\n\{_DIM\}\{icon\} '
            r'\{label\}: \{detail\} → \{outcome\}\{_RST\}"\)\s*$'
        )
        matches = list(old.finditer(source))
        if len(matches) != 1:
            raise RuntimeError(
                f"expected exactly one persisted prompt summary renderer, found {len(matches)}"
            )
        m = matches[0]
        i = m.group("indent")
        replacement = (
            f'{i}# {MARKER}: resolved Clarify summaries remain visually distinct from reasoning.\n'
            f'{i}if label == "Clarify":\n'
            f'{i}    cyan = "\\033[96m"\n'
            f'{i}    green = "\\033[92m"\n'
            f'{i}    rendered_outcome = outcome.replace(\n'
            f'{i}        "(Recommended)", f"{{green}}(Recommended){{cyan}}")\n'
            f'{i}    _cprint(f"\\n{{cyan}}{{icon}} {{label}}: {{detail}} → {{rendered_outcome}}{{_RST}}")\n'
            f'{i}else:\n'
            f'{i}    _cprint(f"\\n{{_DIM}}{{icon}} {{label}}: {{detail}} → {{outcome}}{{_RST}}")'
        )
        source = source[: m.start()] + replacement + source[m.end() :]
    elif MARKER not in source:
        # A future upstream may have equivalent Clarify handling without our marker; fail
        # closed rather than claiming DevKit ownership of an unknown implementation.
        raise RuntimeError(
            "Clarify summary semantic branch exists without the DevKit marker; inspect upstream change"
        )

    path.write_text(source, encoding="utf-8")
    validate_session_source(path)
    return "already-patched" if source == original else "patched"


def validate_session_source(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    required = (
        MARKER,
        SUMMARY_TARGET,
        'cyan = "\\033[96m"',
        'green = "\\033[92m"',
        'outcome.replace(',
        '(Recommended)',
        '{rendered_outcome}{_RST}',
    )
    missing = [token for token in required if token not in source]
    if missing:
        raise RuntimeError(f"{path}: semantic Clarify summary contract missing: {missing}")
    compile_source(path)


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="hermes-tui-semantic-input-test-") as temp_dir:
        root = Path(temp_dir)
        tui = root / "cli_tui_mixin.py"
        tui.write_text(
            dedent_fixture(
                """
                STYLE = {
                    'clarify-border': '#CD7F32',
                    'clarify-title': '#FFD700 bold',
                    'clarify-question': '#FFF8DC bold',
                    'clarify-choice': '#AAAAAA',
                    'clarify-selected': '#FFD700 bold',
                    'clarify-active-other': '#FFD700 italic',
                }

                class Stub:
                    def prompt(self):
                        if self._clarify_state:
                            return _state_fragment("class:prompt-working", "?")

                    def rows(self, choices, selected, freetext):
                        for i, choice in enumerate(choices):
                            style = 'class:clarify-selected' if i == selected and not freetext else 'class:clarify-choice'
                            print(style, choice)

                    def batch_rows(self, choices, selected, freetext):
                        for i, choice in enumerate(choices):
                            style = 'class:clarify-selected' if i == selected and not freetext else 'class:clarify-choice'
                            print(style, choice)
                """
            ),
            encoding="utf-8",
        )
        if patch_tui_source(tui) != "patched":
            raise RuntimeError("self-test: TUI source was not patched")
        if tui.read_text(encoding="utf-8").count(RECOMMENDED_BRANCH) != 2:
            raise RuntimeError("self-test: all Clarify choice renderers were not patched")
        if patch_tui_source(tui) != "already-patched":
            raise RuntimeError("self-test: TUI patch is not idempotent")

        session = root / "cli_session_mixin.py"
        session.write_text(
            dedent_fixture(
                """
                class Stub:
                    def _persist_prompt_summary(self, icon, label, detail, outcome):
                        from cli import CLI_CONFIG, _DIM, _RST, _cprint
                        if not CLI_CONFIG.get("display", {}).get("persist_prompts", True):
                            return
                        detail, outcome = (_squash(s) for s in (detail, outcome))
                        _cprint(f"\\n{_DIM}{icon} {label}: {detail} → {outcome}{_RST}")
                """
            ),
            encoding="utf-8",
        )
        if patch_session_source(session) != "patched":
            raise RuntimeError("self-test: session source was not patched")
        if patch_session_source(session) != "already-patched":
            raise RuntimeError("self-test: session patch is not idempotent")

        broken = root / "broken_tui.py"
        broken.write_text("STYLE = {'clarify-border': '#fff'}\n", encoding="utf-8")
        try:
            patch_tui_source(broken)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("self-test: changed upstream TUI shape did not fail closed")


def dedent_fixture(text: str) -> str:
    # Kept local to avoid importing textwrap in the production patch path.
    lines = text.strip("\n").splitlines()
    margin = min((len(line) - len(line.lstrip()) for line in lines if line.strip()), default=0)
    return "\n".join(line[margin:] for line in lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tui-path", type=Path)
    parser.add_argument("--session-path", type=Path)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        if args.tui_path or args.session_path:
            parser.error("--self-test cannot be combined with source paths")
    elif not (args.tui_path and args.session_path):
        parser.error("--tui-path and --session-path are required unless --self-test is used")
    return args


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        print("Hermes TUI semantic-input patch self-test passed")
        return

    if args.check_only:
        validate_tui_source(args.tui_path)
        validate_session_source(args.session_path)
        print("Hermes TUI semantic-input contract valid")
        return

    tui_state = patch_tui_source(args.tui_path)
    session_state = patch_session_source(args.session_path)
    print(
        "Hermes TUI semantic-input source states="
        f"tui:{tui_state},session:{session_state} and validated"
    )


if __name__ == "__main__":
    main()
