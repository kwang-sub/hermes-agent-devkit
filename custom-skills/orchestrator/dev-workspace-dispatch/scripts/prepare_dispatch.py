#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys
import time


MANAGED_MARKER = "# managed-by: dev-project-bootstrap"
HERMES_MANAGED_PREFIX = ".hermes/"
SKIPPED_COUNT = -1
SKIPPED_SECONDS = -1.0


class DispatchError(RuntimeError):
    pass


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise DispatchError(
            f"command failed ({result.returncode}): {' '.join(cmd)}\n{detail}"
        )
    return result


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Prepare an approved Git workspace/branch for Hermes Kanban dispatch."
    )
    p.add_argument("--task-key", required=True)
    p.add_argument("--workspace", help="Approved Git workspace path. Default: current working directory.")
    p.add_argument("--repo", help="Managed source repository root. Default: resolved workspace repository root.")
    p.add_argument("--branch-mode", choices=("current", "create"), required=True, help="User-approved branch strategy.")
    p.add_argument("--branch", help="Branch to verify in current mode or create in create mode. Default in create mode: feature/<TASK-KEY>.")
    p.add_argument("--start-point", help="Start point for --branch-mode create. Default: current HEAD.")
    p.add_argument(
        "--confirmed-dirty",
        action="store_true",
        help=(
            "User already approved preserving any existing workspace changes. "
            "Skips repository-wide dirty/EOL/untracked classification."
        ),
    )
    return p.parse_args()


def validate_task_key(task_key: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", task_key):
        raise DispatchError("task key must start with a letter/digit and may contain only letters, digits, '.', '_' and '-'")
    if task_key in {".", ".."} or ".." in task_key:
        raise DispatchError("task key must not be '.', '..', or contain '..'")
    if task_key.startswith("-"):
        raise DispatchError("task key must not start with '-'")


def resolve_git_root(path: Path, label: str) -> Path:
    result = run(["git", "-C", str(path), "rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        raise DispatchError(f"cannot resolve Git repository from {label}: {path}")
    return Path(result.stdout.strip()).resolve()


def common_git_dir(path: Path) -> Path:
    result = run(["git", "-C", str(path), "rev-parse", "--path-format=absolute", "--git-common-dir"])
    return Path(result.stdout.strip()).resolve()


def parse_managed_metadata(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise DispatchError(f"project metadata is missing: {path}\nRun dev-project-bootstrap before dispatch.")
    text = path.read_text(encoding="utf-8")
    if MANAGED_MARKER not in text.splitlines()[:5]:
        raise DispatchError(f"project metadata is not managed by dev-project-bootstrap: {path}")

    def field(pattern: str, name: str) -> str:
        m = re.search(pattern, text, flags=re.MULTILINE)
        if not m:
            raise DispatchError(f"required metadata field is missing: {name}")
        return m.group(1).strip().strip("'\"")

    return {
        "project_id": field(r"^\s{2}id:\s*(.+?)\s*$", "project.id"),
        "repository": field(r"^\s{2}repository:\s*(.+?)\s*$", "project.repository"),
        "board": field(r"^kanban:\s*\n\s{2}board:\s*(.+?)\s*$", "kanban.board"),
        "base": field(r"^git:\s*\n\s{2}default_base_branch:\s*(.+?)\s*$", "git.default_base_branch"),
        "coder": field(r"^profiles:\s*\n(?:.*\n)*?\s{2}coder:\s*(.+?)\s*$", "profiles.coder"),
        "reviewer": field(r"^profiles:\s*\n(?:.*\n)*?\s{2}reviewer:\s*(.+?)\s*$", "profiles.reviewer"),
    }


def current_branch(repo: Path) -> str:
    branch = run(["git", "-C", str(repo), "branch", "--show-current"]).stdout.strip()
    if not branch:
        raise DispatchError("workspace is in detached HEAD; select or create a branch first")
    return branch


def git_paths(repo: Path, args: list[str]) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise DispatchError(
            f"command failed ({result.returncode}): git -C {repo} {' '.join(args)}\n{detail}"
        )
    return {
        item.decode("utf-8", errors="surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    }


def timed_git_paths(repo: Path, args: list[str]) -> tuple[set[str], float]:
    started = time.monotonic()
    paths = git_paths(repo, args)
    return paths, time.monotonic() - started


def is_hermes_managed(path: str) -> bool:
    return path == ".hermes" or path.startswith(HERMES_MANAGED_PREFIX)


def classify_workspace_changes(repo: Path) -> tuple[dict[str, list[str]], dict[str, float]]:
    total_started = time.monotonic()

    tracked, tracked_seconds = timed_git_paths(
        repo, ["diff", "--name-only", "-z", "HEAD"]
    )
    effective_tracked, effective_seconds = timed_git_paths(
        repo, ["diff", "--name-only", "-z", "--ignore-cr-at-eol", "HEAD"]
    )
    untracked, untracked_seconds = timed_git_paths(
        repo, ["ls-files", "-z", "--others", "--exclude-standard"]
    )

    classify_started = time.monotonic()
    hermes_managed = {
        path for path in tracked | untracked if is_hermes_managed(path)
    }
    effective = (effective_tracked | untracked) - hermes_managed
    eol_only = (tracked - effective_tracked) - hermes_managed
    classification_seconds = time.monotonic() - classify_started

    changes = {
        "effective": sorted(effective),
        "eol_only": sorted(eol_only),
        "hermes_managed": sorted(hermes_managed),
    }
    timings = {
        "tracked_scan": tracked_seconds,
        "effective_scan": effective_seconds,
        "untracked_scan": untracked_seconds,
        "classification": classification_seconds,
        "total": time.monotonic() - total_started,
    }
    return changes, timings


def change_summary_lines(changes: dict[str, list[str]]) -> list[str]:
    lines = [
        f"EFFECTIVE_CHANGED_COUNT={len(changes['effective'])}",
        f"EOL_ONLY_COUNT={len(changes['eol_only'])}",
        f"HERMES_MANAGED_COUNT={len(changes['hermes_managed'])}",
    ]
    for key, label in (
        ("effective", "EFFECTIVE_CHANGED"),
        ("eol_only", "EOL_ONLY"),
        ("hermes_managed", "HERMES_MANAGED"),
    ):
        for index, path in enumerate(changes[key], start=1):
            lines.append(f"{label}_{index}={path}")
    return lines


def skipped_change_summary_lines() -> list[str]:
    return [
        f"EFFECTIVE_CHANGED_COUNT={SKIPPED_COUNT}",
        f"EOL_ONLY_COUNT={SKIPPED_COUNT}",
        f"HERMES_MANAGED_COUNT={SKIPPED_COUNT}",
    ]


def timing_summary_lines(timings: dict[str, float]) -> list[str]:
    return [
        f"GIT_TRACKED_SCAN_SECONDS={timings['tracked_scan']:.3f}",
        f"GIT_EFFECTIVE_SCAN_SECONDS={timings['effective_scan']:.3f}",
        f"GIT_UNTRACKED_SCAN_SECONDS={timings['untracked_scan']:.3f}",
        f"CLASSIFICATION_SECONDS={timings['classification']:.3f}",
        f"WORKSPACE_CLASSIFICATION_TOTAL_SECONDS={timings['total']:.3f}",
    ]


def skipped_timing_summary_lines() -> list[str]:
    return [
        f"GIT_TRACKED_SCAN_SECONDS={SKIPPED_SECONDS:.3f}",
        f"GIT_EFFECTIVE_SCAN_SECONDS={SKIPPED_SECONDS:.3f}",
        f"GIT_UNTRACKED_SCAN_SECONDS={SKIPPED_SECONDS:.3f}",
        f"CLASSIFICATION_SECONDS={SKIPPED_SECONDS:.3f}",
        f"WORKSPACE_CLASSIFICATION_TOTAL_SECONDS={SKIPPED_SECONDS:.3f}",
    ]


def check_branch_name(branch: str) -> None:
    check = run(["git", "check-ref-format", "--branch", branch], check=False)
    if check.returncode != 0:
        raise DispatchError(f"invalid branch name: {branch}")


def ref_exists(repo: Path, branch: str) -> bool:
    result = run(["git", "-C", str(repo), "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], check=False)
    return result.returncode == 0


def rev_parse(repo: Path, ref: str) -> str:
    result = run(["git", "-C", str(repo), "rev-parse", "--verify", f"{ref}^{{commit}}"], check=False)
    if result.returncode != 0:
        raise DispatchError(f"ref does not resolve to a commit: {ref}")
    return result.stdout.strip()


def main() -> int:
    args = parse_args()
    validate_task_key(args.task_key)

    workspace_start = Path(args.workspace).resolve() if args.workspace else Path.cwd().resolve()
    workspace = resolve_git_root(workspace_start, "workspace")
    if workspace != workspace_start:
        raise DispatchError(f"approved workspace must be the Git repository root: workspace={workspace_start}, root={workspace}")

    repo = resolve_git_root(Path(args.repo).resolve(), "repo") if args.repo else workspace
    metadata_path = repo / ".hermes" / "project.yaml"
    meta = parse_managed_metadata(metadata_path)

    configured_repo = Path(meta["repository"]).resolve()
    if configured_repo != repo:
        raise DispatchError(f"project metadata repository mismatch: metadata={configured_repo}, actual={repo}")

    if common_git_dir(workspace) != common_git_dir(repo):
        raise DispatchError(f"approved workspace does not belong to the managed repository: workspace={workspace}, repo={repo}")

    base = meta["base"]
    base_sha = rev_parse(repo, base)
    before_branch = current_branch(workspace)

    changes: dict[str, list[str]] | None
    timings: dict[str, float] | None
    if args.confirmed_dirty:
        # The user already approved preserving all existing workspace changes.
        # Repository-wide dirty/EOL/untracked classification is not required for
        # safe dispatch and can be prohibitively slow on Windows bind mounts.
        changes = None
        timings = None
        scan_mode = "skipped-approved-preservation"
    else:
        changes, timings = classify_workspace_changes(workspace)
        scan_mode = "full"
        if changes["effective"]:
            summary = "\n".join(change_summary_lines(changes) + timing_summary_lines(timings))
            raise DispatchError(
                "approved workspace has existing effective project changes; "
                "show the exact change counts/paths to the user and rerun with --confirmed-dirty if they approve.\n"
                + summary
            )

    created_branch = False
    if args.branch_mode == "current":
        if args.branch and args.branch != before_branch:
            raise DispatchError(f"current branch mismatch: expected current branch {before_branch}, requested {args.branch}")
        branch = before_branch
    else:
        branch = args.branch or f"feature/{args.task_key}"
        check_branch_name(branch)
        if ref_exists(workspace, branch):
            raise DispatchError(f"branch already exists; choose current mode or another branch: {branch}")
        start_point = args.start_point or "HEAD"
        start_sha = rev_parse(workspace, start_point)
        run(["git", "-C", str(workspace), "checkout", "-b", branch, start_sha])
        created_branch = True

    final_branch = current_branch(workspace)
    if final_branch != branch:
        raise DispatchError(f"branch verification failed: expected={branch}, actual={final_branch}")

    print(f"PROJECT_ID={meta['project_id']}")
    print(f"REPO_ROOT={repo}")
    print(f"BOARD={meta['board']}")
    print(f"BASE_BRANCH={base}")
    print(f"BASE_SHA={base_sha}")
    print(f"WORKSPACE_PATH={workspace}")
    print(f"WORKSPACE=dir:{workspace}")
    print(f"ASSIGNEE={meta['coder']}")
    print(f"REVIEWER={meta['reviewer']}")
    print(f"TASK_KEY={args.task_key}")
    print(f"BRANCH_MODE={args.branch_mode}")
    print(f"BRANCH={branch}")
    print(f"PREVIOUS_BRANCH={before_branch}")
    print(f"CREATED_BRANCH={'true' if created_branch else 'false'}")
    print(f"WORKSPACE_CHANGE_SCAN_MODE={scan_mode}")
    print(f"EXISTING_CHANGES_PRESERVATION_APPROVED={'true' if args.confirmed_dirty else 'false'}")

    if changes is None:
        print("WORKSPACE_DIRTY=unknown")
        print("WORKSPACE_EFFECTIVE_DIRTY=unknown")
        for line in skipped_change_summary_lines():
            print(line)
        for line in skipped_timing_summary_lines():
            print(line)
    else:
        raw_dirty = any(changes.values())
        print(f"WORKSPACE_DIRTY={'true' if raw_dirty else 'false'}")
        print(f"WORKSPACE_EFFECTIVE_DIRTY={'true' if bool(changes['effective']) else 'false'}")
        for line in change_summary_lines(changes):
            print(line)
        assert timings is not None
        for line in timing_summary_lines(timings):
            print(line)

    print("STATUS=prepared")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DispatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
