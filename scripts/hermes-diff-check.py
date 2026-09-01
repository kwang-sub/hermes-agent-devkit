#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys


class DiffCheckError(RuntimeError):
    pass


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise DiffCheckError((result.stderr or result.stdout).strip() or "command failed")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CRLF-aware trailing-whitespace validation for Hermes scoped changes."
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--tracked", action="append", default=[])
    parser.add_argument("--untracked", action="append", default=[])
    return parser.parse_args()


def repo_root(value: str) -> Path:
    requested = Path(value).resolve()
    root = Path(
        run(["git", "-C", str(requested), "rev-parse", "--show-toplevel"]).stdout.strip()
    ).resolve()
    if root != requested:
        raise DiffCheckError(f"--repo must be repository root: requested={requested}, root={root}")
    return root


def trailing_whitespace(content: str) -> bool:
    return bool(re.search(r"[ \t]+$", content))


def tracked_errors(root: Path, base: str, paths: list[str]) -> list[str]:
    errors: list[str] = []
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
    for path in sorted(dict.fromkeys(paths)):
        result = run(
            [
                "git", "-C", str(root), "diff", "--no-ext-diff", "--no-color",
                "--unified=0", "--ignore-cr-at-eol", base, "--", path,
            ],
            check=False,
        )
        if result.returncode not in (0, 1):
            raise DiffCheckError(
                (result.stderr or result.stdout).strip()
                or f"cannot diff tracked path {path}: rc={result.returncode}"
            )

        new_line: int | None = None
        for raw in result.stdout.splitlines():
            hunk = hunk_re.match(raw)
            if hunk:
                new_line = int(hunk.group(1))
                continue
            if new_line is None:
                continue
            if raw.startswith("+++") or raw.startswith("---"):
                continue
            if raw.startswith("+"):
                if trailing_whitespace(raw[1:]):
                    errors.append(f"{path}:{new_line}: trailing whitespace")
                new_line += 1
            elif raw.startswith("-"):
                continue
            elif raw.startswith("\\"):
                continue
            else:
                new_line += 1
    return errors


def untracked_errors(root: Path, paths: list[str]) -> list[str]:
    errors: list[str] = []
    for path in sorted(dict.fromkeys(paths)):
        file_path = root / path
        if not file_path.is_file():
            continue
        data = file_path.read_bytes()
        if b"\0" in data:
            continue
        for line_no, raw in enumerate(data.splitlines(keepends=True), start=1):
            if raw.endswith(b"\r\n"):
                content = raw[:-2]
            elif raw.endswith((b"\n", b"\r")):
                content = raw[:-1]
            else:
                content = raw
            if content.endswith((b" ", b"\t")):
                errors.append(f"{path}:{line_no}: trailing whitespace")
    return errors


def main() -> int:
    args = parse_args()
    root = repo_root(args.repo)
    errors = tracked_errors(root, args.base, args.tracked)
    errors.extend(untracked_errors(root, args.untracked))

    print(f"WHITESPACE_ERROR_COUNT={len(errors)}")
    for index, error in enumerate(errors, start=1):
        print(f"WHITESPACE_ERROR_{index}={error}")
    print("STATUS=valid" if not errors else "STATUS=invalid")
    return 0 if not errors else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DiffCheckError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
