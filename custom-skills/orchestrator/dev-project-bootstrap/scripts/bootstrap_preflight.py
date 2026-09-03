#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import dev_environment_preflight as shared


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a lightweight bootstrap preflight by default; full Git change "
            "classification is opt-in."
        )
    )
    parser.add_argument("--repo", required=True, help="Absolute Git repository root")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Classify tracked, staged, untracked, and tracked EOL-only changes.",
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


def inspect_git_changes(repo: Path) -> tuple[list[str], list[str], int]:
    """Run the expensive repository-wide change classification.

    Bootstrap does not need repository dirty-state information to register a
    project. This function is therefore used only by --full diagnostics.
    """
    effective_unstaged = _effective_unstaged(repo)
    staged = _staged(repo)
    normal = _normal_unstaged(repo)
    untracked = _untracked(repo)
    eol_only = sorted(
        set(normal) - set(effective_unstaged) - set(staged)
    )
    effective = sorted(
        set(effective_unstaged) | set(staged) | set(untracked)
    )
    return effective, eol_only, len(untracked)


def main() -> int:
    args = parse_args()
    shared.require_tool("git")
    shared.require_tool("python3")

    repo = shared.resolve_repo(args.repo)
    mode = "full" if args.full else "fast"
    print(f"== Hermes Development Environment Preflight ({mode}) ==", flush=True)
    print(f"Repository : {repo}", flush=True)

    shared.assert_repository_writable(repo)

    effective: list[str] = []
    eol_only: list[str] = []
    untracked_count: int | None = None
    if args.full:
        print("[FULL] Repository-wide Git change classification: start", flush=True)
        effective, eol_only, untracked_count = inspect_git_changes(repo)
        print(f"[INFO] Effective Git changes: {len(effective)}", flush=True)
        print(f"[INFO] Tracked EOL-only noise: {len(eol_only)}", flush=True)
        print(f"[INFO] Untracked changes: {untracked_count}", flush=True)
    else:
        print(
            "[FAST] Repository-wide Git change/EOL/untracked scan: skipped",
            flush=True,
        )

    build_type = shared.detect_build(repo)
    print(f"Build      : {build_type}", flush=True)
    toolchain_file, warnings = shared.configure_java_toolchain(repo, build_type)

    gitattributes = shared.ensure_gitattributes(repo)
    warnings.extend(shared.inspect_wrapper_eol(repo, build_type))
    for warning in warnings:
        print(f"[WARN] {warning}", flush=True)

    print("", flush=True)
    print(f"GIT_SCAN_MODE={mode}", flush=True)
    print(f"EFFECTIVE_SCOPE={'all' if args.full else 'not-scanned'}", flush=True)
    print(f"BUILD_TYPE={build_type}", flush=True)
    print(f"TOOLCHAIN_FILE={toolchain_file}", flush=True)
    print(f"GITATTRIBUTES={gitattributes}", flush=True)
    print(
        f"EFFECTIVE_DIRTY={'true' if effective else 'false' if args.full else 'unknown'}",
        flush=True,
    )
    print(
        f"EFFECTIVE_CHANGE_COUNT={len(effective) if args.full else -1}",
        flush=True,
    )
    print(
        f"EOL_ONLY_CHANGE_COUNT={len(eol_only) if args.full else -1}",
        flush=True,
    )
    print(
        f"UNTRACKED_CHANGE_COUNT={untracked_count if untracked_count is not None else -1}",
        flush=True,
    )
    print(f"WARNINGS={len(warnings)}", flush=True)
    print(
        "PREFLIGHT_STATUS=ready" if not warnings else "PREFLIGHT_STATUS=ready-with-warnings",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except shared.PreflightError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
