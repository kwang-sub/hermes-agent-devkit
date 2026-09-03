#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


MANAGED_START = "# >>> Hermes Agent managed >>>"
MANAGED_END = "# <<< Hermes Agent managed <<<"
MANAGED_ENTRIES = (
    "/.hermes/",
    "/.worktrees/",
)


class GitIgnoreError(RuntimeError):
    pass


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise GitIgnoreError(
            f"command failed ({result.returncode}): {' '.join(cmd)}\n{detail}"
        )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ensure repository-local Hermes workflow artifacts are ignored by Git."
    )
    parser.add_argument("--repo", required=True, help="Absolute path to a Git repository root")
    return parser.parse_args()


def resolve_repo(path_text: str) -> Path:
    requested = Path(path_text)
    if not requested.is_absolute():
        raise GitIgnoreError(f"--repo must be absolute: {requested}")
    if not requested.is_dir():
        raise GitIgnoreError(f"repository path does not exist or is not a directory: {requested}")

    result = run(["git", "-C", str(requested), "rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        raise GitIgnoreError(f"not a Git repository: {requested}")

    root = Path(result.stdout.strip()).resolve()
    requested_resolved = requested.resolve()
    if root != requested_resolved:
        raise GitIgnoreError(
            f"--repo must point at the Git repository root; "
            f"requested={requested_resolved}, root={root}"
        )
    return root


def managed_block(newline: str) -> str:
    lines = [
        MANAGED_START,
        "# Hermes 로컬 실행/상태 파일 (프로젝트 공용 파일은 Git 추적 유지)",
        *MANAGED_ENTRIES,
        MANAGED_END,
    ]
    return newline.join(lines) + newline


def ensure_gitignore(repo: Path) -> str:
    path = repo / ".gitignore"
    existed = path.exists()
    original = path.read_bytes().decode("utf-8") if existed else ""
    newline = "\r\n" if "\r\n" in original else "\n"

    lines = original.splitlines(keepends=True)
    start_indexes = [
        index for index, line in enumerate(lines)
        if line.rstrip("\r\n") == MANAGED_START
    ]
    end_indexes = [
        index for index, line in enumerate(lines)
        if line.rstrip("\r\n") == MANAGED_END
    ]

    if len(start_indexes) != len(end_indexes) or len(start_indexes) > 1:
        raise GitIgnoreError(
            f"malformed Hermes managed block in {path}; "
            "fix duplicate/missing managed markers before bootstrap"
        )

    block = managed_block(newline)
    if start_indexes:
        start = start_indexes[0]
        end = end_indexes[0]
        if end < start:
            raise GitIgnoreError(
                f"malformed Hermes managed block in {path}; end marker precedes start marker"
            )
        updated = "".join([*lines[:start], block, *lines[end + 1:]])
    else:
        prefix = original
        if prefix and not prefix.endswith(("\n", "\r")):
            prefix += newline
        if prefix and not prefix.endswith(newline * 2):
            prefix += newline
        updated = prefix + block

    if updated == original:
        return "unchanged"

    path.write_bytes(updated.encode("utf-8"))
    return "updated" if existed else "created"


def verify_managed_entries(repo: Path) -> None:
    for path in (".hermes/project.yaml", ".worktrees/bootstrap-probe"):
        result = run(
            ["git", "-C", str(repo), "check-ignore", "-q", "--no-index", "--", path],
            check=False,
        )
        if result.returncode != 0:
            raise GitIgnoreError(
                f"required Hermes local path is not ignored after bootstrap: {path}"
            )


def main() -> int:
    args = parse_args()
    repo = resolve_repo(args.repo)
    status = ensure_gitignore(repo)
    verify_managed_entries(repo)
    print(f"GITIGNORE={status}")
    print("GITIGNORE_HERMES_LOCAL=ignored")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GitIgnoreError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
