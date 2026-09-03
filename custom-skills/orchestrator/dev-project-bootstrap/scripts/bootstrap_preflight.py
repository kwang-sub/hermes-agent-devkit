#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import dev_environment_preflight as shared


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the bootstrap preflight with a fast tracked-only Git scan by default."
        )
    )
    parser.add_argument("--repo", required=True, help="Absolute Git repository root")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also enumerate untracked files and count tracked EOL-only noise.",
    )
    return parser.parse_args()


def _nul_paths(text: str) -> list[str]:
    return [value for value in text.split("\0") if value]


def _numstat_paths(text: str) -> list[str]:
    paths: list[str] = []
    for record in _nul_paths(text):
        parts = record.split("\t", 2)
        if len(parts) != 3:
            raise shared.PreflightError(
                f"unexpected git --numstat record: {record!r}"
            )
        paths.append(parts[2])
    return paths


def _effective_unstaged(repo: Path) -> list[str]:
    result = shared.run([
        "git", "-C", str(repo), "diff",
        "--numstat", "-z",
        "--ignore-cr-at-eol",
        "--no-renames",
        "--no-ext-diff",
        "--no-textconv",
        "--ignore-submodules=all",
    ])
    return _numstat_paths(result.stdout)


def _staged(repo: Path) -> list[str]:
    result = shared.run([
        "git", "-C", str(repo), "diff",
        "--cached",
        "--numstat", "-z",
        "--no-renames",
        "--no-ext-diff",
        "--no-textconv",
        "--ignore-submodules=all",
    ])
    return _numstat_paths(result.stdout)


def _normal_unstaged(repo: Path) -> list[str]:
    result = shared.run([
        "git", "-C", str(repo), "diff",
        "--name-only", "-z",
        "--no-renames",
        "--no-ext-diff",
        "--no-textconv",
        "--ignore-submodules=all",
    ])
    return _nul_paths(result.stdout)


def _untracked(repo: Path) -> list[str]:
    result = shared.run([
        "git", "-C", str(repo),
        "ls-files", "-z", "--others", "--exclude-standard",
    ])
    return _nul_paths(result.stdout)


def inspect_git_changes(
    repo: Path,
    *,
    full_scan: bool = False,
) -> tuple[list[str], list[str], int | None]:
    """Classify repository changes with a cheap default path.

    Fast mode performs one working-tree diff that already suppresses CRLF/LF-only
    patch noise, plus a cached-index diff. It intentionally does not enumerate
    untracked files and does not run a second normal diff just to count EOL noise.

    Full mode adds those two expensive scans for diagnostics.
    """
    effective_unstaged = _effective_unstaged(repo)
    staged = _staged(repo)

    untracked: list[str] = []
    eol_only: list[str] = []
    untracked_count: int | None = None

    if full_scan:
        normal = _normal_unstaged(repo)
        untracked = _untracked(repo)
        untracked_count = len(untracked)
        eol_only = sorted(
            set(normal) - set(effective_unstaged) - set(staged)
        )

    effective = sorted(
        set(effective_unstaged) | set(staged) | set(untracked)
    )
    return effective, eol_only, untracked_count


def main() -> int:
    args = parse_args()
    shared.require_tool("git")
    shared.require_tool("python3")

    repo = shared.resolve_repo(args.repo)
    mode = "full" if args.full else "fast"
    print(f"== Hermes Development Environment Preflight ({mode}) ==")
    print(f"Repository : {repo}")

    shared.assert_repository_writable(repo)
    effective_before, eol_only_before, untracked_count = inspect_git_changes(
        repo,
        full_scan=args.full,
    )
    print(f"[OK] Effective Git changes before bootstrap: {len(effective_before)}")
    if args.full:
        print(f"[INFO] Tracked EOL-only noise: {len(eol_only_before)}")
        print(f"[INFO] Untracked changes: {untracked_count or 0}")
    else:
        print("[FAST] Untracked enumeration: skipped")
        print(
            "[FAST] EOL-only noise count: skipped "
            "(CRLF/LF-only tracked noise is excluded from effective changes)"
        )

    build_type = shared.detect_build(repo)
    print(f"Build      : {build_type}")
    toolchain_file, warnings = shared.configure_java_toolchain(repo, build_type)

    gitattributes = shared.ensure_gitattributes(repo)
    warnings.extend(shared.inspect_wrapper_eol(repo, build_type))
    for warning in warnings:
        print(f"[WARN] {warning}")

    print("")
    print(f"GIT_SCAN_MODE={mode}")
    print(f"EFFECTIVE_SCOPE={'all' if args.full else 'tracked-only'}")
    print(f"BUILD_TYPE={build_type}")
    print(f"TOOLCHAIN_FILE={toolchain_file}")
    print(f"GITATTRIBUTES={gitattributes}")
    print(f"EFFECTIVE_DIRTY={'true' if bool(effective_before) else 'false'}")
    print(f"EFFECTIVE_CHANGE_COUNT={len(effective_before)}")
    print(
        f"EOL_ONLY_CHANGE_COUNT={len(eol_only_before) if args.full else -1}"
    )
    print(
        f"UNTRACKED_CHANGE_COUNT={untracked_count if untracked_count is not None else -1}"
    )
    print(f"WARNINGS={len(warnings)}")
    print("PREFLIGHT_STATUS=ready" if not warnings else "PREFLIGHT_STATUS=ready-with-warnings")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except shared.PreflightError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
