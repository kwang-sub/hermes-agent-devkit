#!/usr/bin/env python3
"""Patch and strictly validate Hermes CLI's venv\\Scripts docstring."""

from __future__ import annotations

import argparse
import py_compile
import tempfile
import warnings
from pathlib import Path

BAD_LINE = b"    ``venv\\Scripts`` dir, which would shadow the user's ``python`` (#83797) \xe2\x80\x94"
GOOD_LINE = b"    ``venv\\\\Scripts`` dir, which would shadow the user's ``python`` (#83797) \xe2\x80\x94"


def strict_compile(path: Path) -> None:
    """Compile without writing beside the source and treat SyntaxWarning as fatal."""
    with tempfile.TemporaryDirectory(prefix="hermes-syntax-check-") as temp_dir:
        cache_path = Path(temp_dir) / "update_cmd.pyc"
        with warnings.catch_warnings():
            warnings.simplefilter("error", SyntaxWarning)
            py_compile.compile(str(path), cfile=str(cache_path), doraise=True)


def validate_source(path: Path) -> None:
    source = path.read_bytes()

    bad_count = source.count(BAD_LINE)

    if bad_count != 0:
        raise RuntimeError(
            f"{path}: invalid venv\\Scripts source remains "
            f"(invalid={bad_count})"
        )

    strict_compile(path)



def patch_source(path: Path) -> bool:
    source = path.read_bytes()

    good_count = source.count(GOOD_LINE)
    bad_count = source.count(BAD_LINE)

    if bad_count == 1 and good_count == 0:
        path.write_bytes(source.replace(BAD_LINE, GOOD_LINE, 1))
        changed = True

    elif bad_count == 0 and good_count == 1:
        # 과거 Hermes지만 이미 패치된 상태
        changed = False

    elif bad_count == 0 and good_count == 0:
        # Hermes upstream에서 해당 코드가 변경/제거된 경우.
        # SyntaxWarning 자체가 해결됐는지만 검증한다.
        strict_compile(path)
        return False

    else:
        raise RuntimeError(
            f"{path}: unexpected Hermes warning source state "
            f"(escaped={good_count}, invalid={bad_count})"
        )

    strict_compile(path)
    return changed


def self_test() -> None:
    """Exercise the patch, strict compile check, and idempotent second run."""
    with tempfile.TemporaryDirectory(prefix="hermes-warning-patch-test-") as temp_dir:
        fixture = Path(temp_dir) / "update_cmd.py"
        fixture.write_bytes(
            b'def fixture():\n    """Windows path documentation.\n'
            + BAD_LINE
            + b'\n    """\n    return None\n'
        )
        try:
            strict_compile(fixture)
        except py_compile.PyCompileError as error:
            if "invalid escape sequence" not in str(error):
                raise RuntimeError("self-test: unexpected pre-patch failure") from error
        else:
            raise RuntimeError("self-test: invalid escape did not fail strict compile")

        if not patch_source(fixture):
            raise RuntimeError("self-test: first patch did not report a change")
        if patch_source(fixture):
            raise RuntimeError("self-test: second patch was not idempotent")


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
        print("Hermes SyntaxWarning patch self-test passed")
        return

    if args.check_only:
        validate_source(args.path)
        print(f"Hermes source strict SyntaxWarning check passed: {args.path}")
        return

    changed = patch_source(args.path)
    state = "patched" if changed else "already patched"
    print(f"Hermes SyntaxWarning source {state} and validated: {args.path}")


if __name__ == "__main__":
    main()
