#!/usr/bin/env python3
"""Patch Hermes TUI config watcher when upstream uses file_signature without importing it."""

from __future__ import annotations

import argparse
import ast
import py_compile
import tempfile
from pathlib import Path

IMPORT_LINE = "from utils import file_signature\n"
ANCHOR_LINE = "from hermes_cli.commands_completion import SlashCommandAutoSuggest, SlashCommandCompleter\n"
USE_TOKEN = "file_signature("


def has_module_import(source: str) -> bool:
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.module != "utils":
            continue
        if any(alias.name == "file_signature" for alias in node.names):
            return True
    return False


def compile_source(path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="hermes-tui-filesig-") as temp_dir:
        py_compile.compile(
            str(path),
            cfile=str(Path(temp_dir) / "cli_tui_mixin.pyc"),
            doraise=True,
        )


def validate_source(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if USE_TOKEN in source and not has_module_import(source):
        raise RuntimeError(
            f"{path}: file_signature is used by the TUI config watcher but is not imported from utils"
        )
    compile_source(path)


def patch_source(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    uses_file_signature = USE_TOKEN in source
    imported = has_module_import(source)

    if uses_file_signature and not imported:
        if source.count(ANCHOR_LINE) != 1:
            raise RuntimeError(
                f"{path}: cannot safely patch file_signature import because the expected TUI import anchor changed"
            )
        source = source.replace(ANCHOR_LINE, ANCHOR_LINE + IMPORT_LINE, 1)
        path.write_text(source, encoding="utf-8")
        state = "patched"
    elif uses_file_signature and imported:
        state = "already-patched"
    else:
        state = "not-needed"

    validate_source(path)
    return state


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="hermes-tui-filesig-test-") as temp_dir:
        root = Path(temp_dir)

        missing = root / "missing.py"
        missing.write_text(
            "from __future__ import annotations\n"
            + ANCHOR_LINE
            + "def watch(st):\n    return file_signature(st)\n",
            encoding="utf-8",
        )
        if patch_source(missing) != "patched":
            raise RuntimeError("self-test: missing import was not patched")
        if patch_source(missing) != "already-patched":
            raise RuntimeError("self-test: patch is not idempotent")

        fixed = root / "fixed.py"
        fixed.write_text(
            "from __future__ import annotations\n"
            + IMPORT_LINE
            + "def watch(st):\n    return file_signature(st)\n",
            encoding="utf-8",
        )
        if patch_source(fixed) != "already-patched":
            raise RuntimeError("self-test: upstream-fixed import was not accepted")

        legacy = root / "legacy.py"
        legacy.write_text("def watch(st):\n    return st.st_mtime\n", encoding="utf-8")
        if patch_source(legacy) != "not-needed":
            raise RuntimeError("self-test: legacy upstream without file_signature use was not accepted")


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
        print("Hermes TUI file_signature patch self-test passed")
        return
    if args.check_only:
        validate_source(args.path)
        print(f"Hermes TUI file_signature contract valid: {args.path}")
        return
    state = patch_source(args.path)
    print(f"Hermes TUI file_signature source state={state} and validated: {args.path}")


if __name__ == "__main__":
    main()
