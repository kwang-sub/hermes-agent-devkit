#!/usr/bin/env python3
"""Patch Hermes Kanban stop guard so review handoffs end the active worker run."""

from __future__ import annotations

import argparse
import py_compile
import re
import tempfile
from pathlib import Path

REQUIRED_TERMINALS = (
    "kanban_complete",
    "kanban_block",
    "kanban_request_review",
    "kanban_request_changes",
)
LEGACY_TERMINALS = frozenset({"kanban_complete", "kanban_block"})
ASSIGNMENT_RE = re.compile(
    r"_TERMINAL_KANBAN_TOOLS\s*=\s*frozenset\(\{(?P<body>.*?)\}\)",
    flags=re.DOTALL,
)
QUOTED_NAME_RE = re.compile(r"[\"']([^\"']+)[\"']")


def strict_compile(path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="hermes-kanban-terminal-check-") as temp_dir:
        py_compile.compile(
            str(path),
            cfile=str(Path(temp_dir) / "kanban_stop.pyc"),
            doraise=True,
        )


def terminal_names(source: str) -> tuple[re.Match[str] | None, frozenset[str]]:
    match = ASSIGNMENT_RE.search(source)
    if not match:
        return None, frozenset()
    return match, frozenset(QUOTED_NAME_RE.findall(match.group("body")))


def replacement_assignment() -> str:
    body = "\n".join(f'    "{name}",' for name in REQUIRED_TERMINALS)
    return f"_TERMINAL_KANBAN_TOOLS = frozenset({{\n{body}\n}})"


def validate_source(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    match, names = terminal_names(source)
    required = frozenset(REQUIRED_TERMINALS)
    if match is None:
        if not all(name in source for name in REQUIRED_TERMINALS):
            raise RuntimeError(
                f"{path}: Hermes terminal guard shape changed and review handoffs "
                "cannot be verified"
            )
    elif not required.issubset(names):
        raise RuntimeError(
            f"{path}: required Kanban terminal tools are missing: "
            f"{sorted(required - names)}"
        )
    strict_compile(path)


def patch_source(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    match, names = terminal_names(source)
    required = frozenset(REQUIRED_TERMINALS)

    if match is None:
        if all(name in source for name in REQUIRED_TERMINALS):
            state = "not-needed"
        else:
            raise RuntimeError(
                f"{path}: unexpected Hermes Kanban stop-guard structure; "
                "refusing an unsafe compatibility patch"
            )
    elif required.issubset(names):
        state = "already-patched"
    elif names == LEGACY_TERMINALS:
        source = source[:match.start()] + replacement_assignment() + source[match.end():]
        path.write_text(source, encoding="utf-8")
        state = "patched"
    else:
        raise RuntimeError(
            f"{path}: unexpected terminal tool set {sorted(names)}; "
            "refusing to overwrite upstream lifecycle policy"
        )

    validate_source(path)
    return state


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="hermes-kanban-terminal-test-") as temp_dir:
        root = Path(temp_dir)
        legacy = root / "legacy.py"
        legacy.write_text(
            '_TERMINAL_KANBAN_TOOLS = frozenset({"kanban_complete", "kanban_block"})\n',
            encoding="utf-8",
        )
        if patch_source(legacy) != "patched":
            raise RuntimeError("self-test: legacy source was not patched")
        if patch_source(legacy) != "already-patched":
            raise RuntimeError("self-test: patch is not idempotent")

        refactored = root / "refactored.py"
        refactored.write_text(
            "TERMINALS = ('kanban_complete', 'kanban_block', "
            "'kanban_request_review', 'kanban_request_changes')\n",
            encoding="utf-8",
        )
        if patch_source(refactored) != "not-needed":
            raise RuntimeError("self-test: upstream-refactored source was not accepted")

        unexpected = root / "unexpected.py"
        unexpected.write_text(
            '_TERMINAL_KANBAN_TOOLS = frozenset({"kanban_complete", "custom_terminal"})\n',
            encoding="utf-8",
        )
        try:
            patch_source(unexpected)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("self-test: unexpected upstream policy was overwritten")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test == (args.path is not None):
        parser.error("provide either --self-test or a source path")
    return args


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        print("Hermes Kanban terminal patch self-test passed")
        return
    if args.check_only:
        validate_source(args.path)
        print(f"Hermes Kanban terminal contract valid: {args.path}")
        return
    state = patch_source(args.path)
    print(f"Hermes Kanban terminal source state={state} and validated: {args.path}")


if __name__ == "__main__":
    main()
