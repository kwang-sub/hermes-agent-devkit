#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import dev_environment_preflight as shared
import project_builds


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a lightweight bootstrap preflight by default; full Git change "
            "classification is opt-in."
        )
    )
    parser.add_argument("--repo", required=True, help="Absolute project root")
    parser.add_argument(
        "--allow-non-git",
        action="store_true",
        help="Explicit acknowledgement that the project has no Git version control.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Classify tracked, staged, untracked, and tracked EOL-only changes.",
    )
    return parser.parse_args()


def resolve_project_root(value: str, *, allow_non_git: bool) -> tuple[Path, str]:
    requested = Path(value).expanduser()
    if not requested.is_absolute():
        raise shared.PreflightError(f"--repo must be absolute: {requested}")
    if not requested.is_dir():
        raise shared.PreflightError(
            f"project path does not exist or is not a directory: {requested}"
        )
    requested = requested.resolve()
    result = shared.run(
        ["git", "-C", str(requested), "rev-parse", "--show-toplevel"],
        check=False,
    )
    if result.returncode != 0:
        if not allow_non_git:
            raise shared.PreflightError(
                "project is not a Git repository; explicit Non-Git acknowledgement is required"
            )
        return requested, "none"
    return shared.resolve_repo(str(requested)), "git"


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

    repo, version_control = resolve_project_root(
        args.repo,
        allow_non_git=args.allow_non_git,
    )
    mode = "full" if args.full and version_control == "git" else "fast"
    print(f"== Hermes Development Environment Preflight ({mode}) ==", flush=True)
    print(f"Project    : {repo}", flush=True)
    print(f"VCS        : {version_control}", flush=True)

    shared.assert_repository_writable(repo)

    effective: list[str] = []
    eol_only: list[str] = []
    untracked_count: int | None = None
    if args.full and version_control == "git":
        print("[FULL] Repository-wide Git change classification: start", flush=True)
        effective, eol_only, untracked_count = inspect_git_changes(repo)
        print(f"[INFO] Effective Git changes: {len(effective)}", flush=True)
        print(f"[INFO] Tracked EOL-only noise: {len(eol_only)}", flush=True)
        print(f"[INFO] Untracked changes: {untracked_count}", flush=True)
    else:
        reason = (
            "version control unavailable"
            if version_control == "none"
            else "fast bootstrap path"
        )
        print(
            f"[FAST] Repository-wide Git change/EOL/untracked scan: skipped ({reason})",
            flush=True,
        )

    projects = project_builds.discover_build_projects(repo)
    build_type = project_builds.summarize_build_type(projects)
    print(f"Build      : {build_type}", flush=True)
    print(f"Build roots: {len(projects)}", flush=True)
    for project in projects:
        print(
            "[INFO] Build project: "
            f"{project_builds.project_label(repo, project.root)} ({project.build_type})",
            flush=True,
        )

    toolchain_file, warnings = project_builds.configure_java_toolchain(
        repo,
        projects,
    )

    if version_control == "git":
        gitattributes = shared.ensure_gitattributes(repo)
    else:
        gitattributes = "N/A"
        warnings.append(
            "Version control is disabled; Git diff/history/rollback and .gitattributes policy are unavailable."
        )
    warnings.extend(project_builds.inspect_wrapper_eol(repo, projects))
    for warning in warnings:
        print(f"[WARN] {warning}", flush=True)

    project_summary = ",".join(
        f"{project.build_type}:{project_builds.project_label(repo, project.root)}"
        for project in projects
    )
    print("", flush=True)
    print(f"VERSION_CONTROL={version_control}", flush=True)
    print(f"GIT_SCAN_MODE={mode if version_control == 'git' else 'unsupported'}", flush=True)
    print(f"EFFECTIVE_SCOPE={'all' if args.full else 'not-scanned'}", flush=True)
    print(f"BUILD_TYPE={build_type}", flush=True)
    print(f"BUILD_PROJECT_COUNT={len(projects)}", flush=True)
    print(f"BUILD_PROJECTS={project_summary}", flush=True)
    print(f"TOOLCHAIN_FILE={toolchain_file}", flush=True)
    print(f"GITATTRIBUTES={gitattributes}", flush=True)
    print(
        f"EFFECTIVE_DIRTY={'true' if effective else 'false' if args.full and version_control == 'git' else 'unknown'}",
        flush=True,
    )
    print(
        f"EFFECTIVE_CHANGE_COUNT={len(effective) if args.full and version_control == 'git' else -1}",
        flush=True,
    )
    print(
        f"EOL_ONLY_CHANGE_COUNT={len(eol_only) if args.full and version_control == 'git' else -1}",
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
