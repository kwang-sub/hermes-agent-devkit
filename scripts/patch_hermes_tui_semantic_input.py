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


# Latest Hermes routes persisted prompt summaries through t() for i18n.
# Preserve the upstream translation call, and color only the Clarify result.
I18N_SUMMARY_ANCHOR = (
    '_cprint(f"\\n{_DIM}{t(\'cli.session.persist_prompt_summary\', '
    'icon=icon, label=label, detail=detail, outcome=outcome)}{_RST}")'
)


def patch_session_source(path: Path) -> str:
    original = path.read_text(encoding="utf-8")
    source = original

    if SUMMARY_TARGET not in source:
        legacy = re.compile(
            r'(?m)^(?P<indent>[ \t]*)_cprint\(f"\\n\{_DIM\}\{icon\} '
            r'\{label\}: \{detail\} → \{outcome\}\{_RST\}"\)[ \t]*$'
        )
        old_matches = list(legacy.finditer(source))
        new_matches = list(re.finditer(
            r'(?m)^(?P<indent>[ \t]*)' + re.escape(I18N_SUMMARY_ANCHOR) + r'[ \t]*$',
            source,
        ))
        if len(old_matches) + len(new_matches) != 1:
            raise RuntimeError(
                "expected exactly one legacy or translated persisted prompt summary "
                f"renderer, found legacy={len(old_matches)}, translated={len(new_matches)}"
            )
        match = (old_matches + new_matches)[0]
        i = match.group("indent")
        common = (
            f'{i}# {MARKER}: color Clarify summaries, preserve all other prompts.\n'
            f'{i}if label == "Clarify":\n'
            f'{i}    cyan = "\\033[96m"\n'
            f'{i}    green = "\\033[92m"\n'
            f'{i}    rendered_outcome = outcome.replace(\n'
            f'{i}        "(Recommended)", f"{{green}}(Recommended){{cyan}}")\n'
        )
        if new_matches:
            replacement = (
                common
                + f'{i}    rendered_summary = t("cli.session.persist_prompt_summary",\n'
                + f'{i}        icon=icon, label=label, detail=detail, outcome=rendered_outcome)\n'
                + f'{i}    _cprint(f"\\n{{cyan}}{{rendered_summary}}{{_RST}}")\n'
                + f'{i}else:\n'
                + f'{i}    {I18N_SUMMARY_ANCHOR}'
            )
        else:
            replacement = (
                common
                + f'{i}    _cprint(f"\\n{{cyan}}{{icon}} {{label}}: {{detail}} → {{rendered_outcome}}{{_RST}}")\n'
                + f'{i}else:\n'
                + f'{i}    _cprint(f"\\n{{_DIM}}{{icon}} {{label}}: {{detail}} → {{outcome}}{{_RST}}")'
            )
        source = source[:match.start()] + replacement + source[match.end():]
    elif MARKER not in source:
        raise RuntimeError(
            "Clarify summary semantic branch exists without the DevKit marker; inspect upstream change"
        )

    # Never leave a partial patch behind if upstream shape is incompatible.
    if source != original:
        with tempfile.TemporaryDirectory(prefix="hermes-session-patch-") as tmp:
            candidate = Path(tmp) / path.name
            candidate.write_text(source, encoding="utf-8")
            validate_session_source(candidate)
        path.write_text(source, encoding="utf-8")
    else:
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
    )
    missing = [token for token in required if token not in source]
    if missing:
        raise RuntimeError(f"{path}: semantic Clarify summary contract missing: {missing}")
    translated = 'rendered_summary = t("cli.session.persist_prompt_summary"' in source
    legacy = '{rendered_outcome}{_RST}' in source
    if translated == legacy:
        raise RuntimeError(f"{path}: expected exactly one supported Clarify summary renderer")
    if translated and (
        I18N_SUMMARY_ANCHOR not in source
        or 'outcome=rendered_outcome)' not in source
        or '{rendered_summary}{_RST}' not in source
    ):
        raise RuntimeError(f"{path}: translated Clarify summary contract missing")
    compile_source(path)

SEARCH_SKIP_PARTS = {
    ".git",
    "node_modules",
    "__pycache__",
    "web",
    "ui-tui",
    "apps",
}


def _iter_primary_python_sources(root: Path):
    seen: set[Path] = set()
    preferred = (
        root / "hermes_cli",
        root / "cli.py",
    )
    for base in preferred:
        if base.is_file():
            resolved = base.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield base
        elif base.is_dir():
            for path in base.rglob("*.py"):
                if any(part in SEARCH_SKIP_PARTS for part in path.parts):
                    continue
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                yield path

    for path in root.glob("*.py"):
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        yield path


def _iter_fallback_site_package_sources(root: Path):
    venv = root / ".venv"
    if not venv.is_dir():
        return
    for site_packages in venv.glob("lib/python*/site-packages"):
        if not site_packages.is_dir():
            continue
        for path in site_packages.rglob("*.py"):
            if any(part in SEARCH_SKIP_PARTS for part in path.parts):
                continue
            yield path


def _read_source(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _is_tui_candidate(source: str) -> bool:
    required = (
        "clarify-border",
        "clarify-title",
        "clarify-question",
        "clarify-choice",
        "clarify-selected",
        "clarify-active-other",
        "_clarify_state",
    )
    return all(token in source for token in required) and (
        'class:prompt-working", "?"' in source or PROMPT_TARGET in source
    )


def _is_session_candidate(source: str) -> bool:
    required = ("_persist_prompt_summary", "_cprint", "_DIM", "_RST")
    if not all(token in source for token in required):
        return False
    return (
        ("{label}: {detail}" in source and "{outcome}" in source)
        or ("cli.session.persist_prompt_summary" in source and
            "icon=icon, label=label, detail=detail, outcome=outcome" in source)
        or (SUMMARY_TARGET in source and MARKER in source)
    )

def _discover_from(paths) -> tuple[list[Path], list[Path]]:
    tui: list[Path] = []
    session: list[Path] = []
    seen_tui: set[Path] = set()
    seen_session: set[Path] = set()
    for path in paths:
        source = _read_source(path)
        if source is None:
            continue
        resolved = path.resolve()
        if _is_tui_candidate(source) and resolved not in seen_tui:
            tui.append(path)
            seen_tui.add(resolved)
        if _is_session_candidate(source) and resolved not in seen_session:
            session.append(path)
            seen_session.add(resolved)
    return tui, session


def discover_source_paths(root: Path) -> tuple[Path, Path]:
    if not root.is_dir():
        raise RuntimeError(f"Hermes search root does not exist: {root}")

    tui, session = _discover_from(_iter_primary_python_sources(root))
    if not tui or not session:
        fallback_tui, fallback_session = _discover_from(_iter_fallback_site_package_sources(root))
        if not tui:
            tui = fallback_tui
        if not session:
            session = fallback_session

    if len(tui) != 1 or len(session) != 1:
        raise RuntimeError(
            "cannot uniquely discover Hermes Clarify sources: "
            f"tui={[str(p) for p in tui]!r}, session={[str(p) for p in session]!r}"
        )
    return tui[0], session[0]


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

        # New upstream keeps the presentation localized via t(...).
        translated = root / "cli_session_translated.py"
        translated.write_text(
            dedent_fixture(
                """
                class Stub:
                    def _persist_prompt_summary(self, icon, label, detail, outcome):
                        from cli import CLI_CONFIG, _DIM, _RST, _cprint
                        if not CLI_CONFIG.get("display", {}).get("persist_prompts", True):
                            return
                        detail, outcome = (_squash(s) for s in (detail, outcome))
                        _cprint(f"\\n{_DIM}{t('cli.session.persist_prompt_summary', icon=icon, label=label, detail=detail, outcome=outcome)}{_RST}")
                """
            ),
            encoding="utf-8",
        )
        if not _is_session_candidate(translated.read_text(encoding="utf-8")):
            raise RuntimeError("self-test: translated session was not discovered")
        if patch_session_source(translated) != "patched":
            raise RuntimeError("self-test: translated session was not patched")
        if patch_session_source(translated) != "already-patched":
            raise RuntimeError("self-test: translated session patch is not idempotent")
        translated_source = translated.read_text(encoding="utf-8")
        if "outcome=rendered_outcome)" not in translated_source:
            raise RuntimeError("self-test: translated Clarify lost translated outcome")
        if I18N_SUMMARY_ANCHOR not in translated_source:
            raise RuntimeError("self-test: non-Clarify translation not preserved")
        translated.unlink()  # Keep discovery fixture unambiguous for the legacy test.

        # Avoid silently patching an unknown future source shape.
        unsupported = root / "unsupported_session.py"
        unsupported.write_text(
            "def _persist_prompt_summary(self):\n    _cprint('changed upstream')\n",
            encoding="utf-8",
        )
        try:
            patch_session_source(unsupported)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("self-test: unknown session source did not fail closed")

        future = root / "future_layout"
        future.mkdir()
        discovered_tui = future / "interactive_surface.py"
        discovered_session = future / "history_surface.py"
        discovered_tui.write_text(tui.read_text(encoding="utf-8"), encoding="utf-8")
        discovered_session.write_text(session.read_text(encoding="utf-8"), encoding="utf-8")
        found_tui, found_session = discover_source_paths(root)
        if found_tui.resolve() != tui.resolve() or found_session.resolve() != session.resolve():
            raise RuntimeError(
                f"self-test: discovery should prefer primary root sources, got {found_tui}, {found_session}"
            )

        isolated = root / "isolated"
        isolated.mkdir()
        isolated_tui = isolated / "interactive_surface.py"
        isolated_session = isolated / "history_surface.py"
        isolated_tui.write_text(tui.read_text(encoding="utf-8"), encoding="utf-8")
        isolated_session.write_text(session.read_text(encoding="utf-8"), encoding="utf-8")
        found_tui, found_session = discover_source_paths(isolated)
        if found_tui.resolve() != isolated_tui.resolve() or found_session.resolve() != isolated_session.resolve():
            raise RuntimeError(
                f"self-test: path-independent discovery failed: {found_tui}, {found_session}"
            )

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
    parser.add_argument("--search-root", type=Path)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    explicit = args.tui_path is not None or args.session_path is not None
    if args.self_test:
        if explicit or args.search_root:
            parser.error("--self-test cannot be combined with source paths or --search-root")
    elif args.search_root:
        if explicit:
            parser.error("--search-root cannot be combined with --tui-path/--session-path")
    elif not (args.tui_path and args.session_path):
        parser.error("provide --search-root or both --tui-path and --session-path")
    return args


def resolve_source_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.search_root:
        return discover_source_paths(args.search_root)
    return args.tui_path, args.session_path


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        print("Hermes TUI semantic-input patch self-test passed")
        return

    tui_path, session_path = resolve_source_paths(args)
    print(f"Hermes TUI semantic-input targets: tui={tui_path}, session={session_path}")

    if args.check_only:
        validate_tui_source(tui_path)
        validate_session_source(session_path)
        print("Hermes TUI semantic-input contract valid")
        return

    tui_state = patch_tui_source(tui_path)
    session_state = patch_session_source(session_path)
    print(
        "Hermes TUI semantic-input source states="
        f"tui:{tui_state},session:{session_state} and validated"
    )


if __name__ == "__main__":
    main()
