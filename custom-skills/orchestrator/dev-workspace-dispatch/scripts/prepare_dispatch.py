#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


MANAGED_MARKER = "# managed-by: dev-project-bootstrap"
HERMES_MANAGED_PREFIX = ".hermes/"
SKIPPED_COUNT = -1
SKIPPED_SECONDS = -1.0
INFRASTRUCTURE_VERSION = "1"
INFRA_RUNTIMES = ("LOCAL_HOST", "NETWORK_HOST", "CONTAINER")
INFRA_PLATFORMS = ("NATIVE", "SUPABASE")
INFRA_VENDORS = ("postgresql", "mysql", "mariadb", "mssql", "oracle", "UNKNOWN")


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
    p.add_argument(
        "--repo",
        help=(
            "Managed source repository root. A linked worktree path is accepted only when it belongs "
            "to the same repository and is canonicalized to the primary worktree."
        ),
    )
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
    p.add_argument("--desired-application-runtime", choices=INFRA_RUNTIMES)
    p.add_argument("--desired-database-runtime", choices=INFRA_RUNTIMES)
    p.add_argument("--desired-database-platform", choices=INFRA_PLATFORMS)
    p.add_argument("--desired-database-vendor", choices=INFRA_VENDORS)
    return p.parse_args()


def validate_task_key(task_key: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", task_key):
        raise DispatchError("task key must start with a letter/digit and may contain only letters, digits, '.', '_' and '-'")
    if task_key in {".", ".."} or ".." in task_key:
        raise DispatchError("task key must not be '.', '..', or contain '..'")
    if task_key.startswith("-"):
        raise DispatchError("task key must not start with '-'")


def infrastructure_args(args: argparse.Namespace) -> dict[str, str] | None:
    values = {
        "application_runtime": args.desired_application_runtime,
        "database_runtime": args.desired_database_runtime,
        "database_platform": args.desired_database_platform,
        "database_vendor": args.desired_database_vendor,
    }
    supplied = [value is not None for value in values.values()]
    if any(supplied) and not all(supplied):
        raise DispatchError(
            "infrastructure desired state is atomic; provide all four --desired-* arguments or none"
        )
    if not any(supplied):
        return None

    resolved = {key: str(value) for key, value in values.items()}
    if resolved["database_platform"] == "SUPABASE":
        if resolved["database_vendor"] not in {"postgresql", "UNKNOWN"}:
            raise DispatchError(
                "SUPABASE desired platform requires database vendor postgresql or UNKNOWN"
            )
        resolved["database_vendor"] = "postgresql"
    return resolved


def split_top_level_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    lines = text.splitlines(keepends=True)
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if line.startswith((" ", "\t")):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+):(?:\s.*)?(?:\r?\n)?$", line)
        if match:
            starts.append((index, match.group(1)))
    if not starts:
        return text, []
    header = "".join(lines[: starts[0][0]])
    sections: list[tuple[str, str]] = []
    for pos, (start, key) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        sections.append((key, "".join(lines[start:end])))
    return header, sections


def infrastructure_section(state: dict[str, str]) -> str:
    return "\n".join(
        [
            "infrastructure:",
            f"  version: {json.dumps(INFRASTRUCTURE_VERSION)}",
            f"  application_runtime: {json.dumps(state['application_runtime'])}",
            f"  database_runtime: {json.dumps(state['database_runtime'])}",
            f"  database_platform: {json.dumps(state['database_platform'])}",
            f"  database_vendor: {json.dumps(state['database_vendor'])}",
        ]
    ) + "\n"


def persist_infrastructure_state(path: Path, state: dict[str, str] | None) -> str:
    if state is None:
        return "not-requested"
    if not path.is_file():
        raise DispatchError(f"project metadata is missing from primary repository: {path}")
    text = path.read_text(encoding="utf-8")
    if MANAGED_MARKER not in text.splitlines()[:5]:
        raise DispatchError(f"project metadata is not managed by dev-project-bootstrap: {path}")

    header, sections = split_top_level_sections(text)
    replacement = infrastructure_section(state)
    output_sections: list[str] = []
    replaced = False
    for key, body in sections:
        if key == "infrastructure":
            output_sections.append(replacement.rstrip())
            replaced = True
        else:
            output_sections.append(body.rstrip())
    if not replaced:
        output_sections.append(replacement.rstrip())

    updated = header.rstrip("\r\n")
    if updated:
        updated += "\n"
    updated += "\n\n".join(part for part in output_sections if part.strip()) + "\n"
    if updated == text:
        return "unchanged"
    path.write_text(updated, encoding="utf-8")
    return "updated"


def add_process_safe_directory(path: str | Path) -> None:
    """Trust only the approved repository/worktree in this process.

    This uses Git's environment config protocol instead of mutating global or
    repository config, so routed Hermes profiles and host Git configuration are
    unaffected.
    """
    resolved = str(Path(path).expanduser().resolve())
    count = int(os.environ.get("GIT_CONFIG_COUNT", "0") or "0")
    existing = {
        os.environ.get(f"GIT_CONFIG_VALUE_{index}")
        for index in range(count)
        if os.environ.get(f"GIT_CONFIG_KEY_{index}") == "safe.directory"
    }
    if resolved in existing:
        return
    os.environ[f"GIT_CONFIG_KEY_{count}"] = "safe.directory"
    os.environ[f"GIT_CONFIG_VALUE_{count}"] = resolved
    os.environ["GIT_CONFIG_COUNT"] = str(count + 1)


def resolve_git_root(path: Path, label: str) -> Path:
    result = run(["git", "-C", str(path), "rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        suffix = f"\n{detail}" if detail else ""
        raise DispatchError(f"cannot resolve Git repository from {label}: {path}{suffix}")
    return Path(result.stdout.strip()).resolve()


def worktree_paths(path: Path) -> list[Path]:
    result = run(["git", "-C", str(path), "worktree", "list", "--porcelain"])
    paths: list[Path] = []
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line[len("worktree "):]).resolve())
    if not paths:
        raise DispatchError(f"git worktree list returned no registered worktrees: {path}")
    return paths


def primary_worktree(path: Path) -> Path:
    primary = worktree_paths(path)[0]
    if not primary.is_dir():
        raise DispatchError(f"primary worktree path does not exist: {primary}")
    add_process_safe_directory(primary)
    return primary


def common_git_dir(path: Path) -> Path:
    result = run(["git", "-C", str(path), "rev-parse", "--path-format=absolute", "--git-common-dir"])
    return Path(result.stdout.strip()).resolve()


def resolve_project_repository(workspace: Path, explicit_repo: str | None) -> Path:
    primary = primary_worktree(workspace)
    if explicit_repo:
        requested = Path(explicit_repo).expanduser().resolve()
        add_process_safe_directory(requested)
        explicit_root = resolve_git_root(requested, "repo")
        add_process_safe_directory(explicit_root)
        if common_git_dir(explicit_root) != common_git_dir(workspace):
            raise DispatchError(
                "approved workspace does not belong to the explicitly selected managed repository: "
                f"workspace={workspace}, repo={explicit_root}"
            )
    return primary


def parse_managed_metadata(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise DispatchError(
            f"project metadata is missing from primary repository: {path}\n"
            "Run dev-project-bootstrap for the primary repository; linked worktrees do not need their own .hermes/project.yaml."
        )
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
    desired_infrastructure = infrastructure_args(args)

    workspace_start = Path(args.workspace).expanduser().resolve() if args.workspace else Path.cwd().resolve()
    add_process_safe_directory(workspace_start)
    workspace = resolve_git_root(workspace_start, "workspace")
    add_process_safe_directory(workspace)
    if workspace != workspace_start:
        raise DispatchError(f"approved workspace must be the Git repository root: workspace={workspace_start}, root={workspace}")

    repo = resolve_project_repository(workspace, args.repo)
    metadata_path = repo / ".hermes" / "project.yaml"
    meta = parse_managed_metadata(metadata_path)

    configured_repo = Path(meta["repository"]).expanduser().resolve()
    if configured_repo != repo:
        raise DispatchError(f"project metadata repository mismatch: metadata={configured_repo}, primary={repo}")

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

    # Persist approved project-wide desired state only after workspace/branch
    # verification has succeeded. A blocked dispatch must not mutate metadata.
    infrastructure_state_status = persist_infrastructure_state(metadata_path, desired_infrastructure)

    linked_worktree = workspace != repo
    workspace_metadata = workspace / ".hermes" / "project.yaml"

    print(f"PROJECT_ID={meta['project_id']}")
    print(f"REPO_ROOT={repo}")
    print(f"PROJECT_REPOSITORY={repo}")
    print(f"PROJECT_METADATA_FILE={metadata_path}")
    print(f"PROJECT_CONTEXT_SOURCE=primary-worktree")
    print(f"LINKED_WORKTREE={'true' if linked_worktree else 'false'}")
    if linked_worktree and workspace_metadata.is_file():
        print(f"WORKSPACE_METADATA_IGNORED={workspace_metadata}")
    else:
        print("WORKSPACE_METADATA_IGNORED=")
    print(f"INFRASTRUCTURE_STATE_STATUS={infrastructure_state_status}")
    if desired_infrastructure is None:
        print("INFRASTRUCTURE_DESIRED_STATE=not-requested")
    else:
        print(
            "INFRASTRUCTURE_DESIRED_STATE="
            + ",".join(
                [
                    f"application_runtime={desired_infrastructure['application_runtime']}",
                    f"database_runtime={desired_infrastructure['database_runtime']}",
                    f"database_platform={desired_infrastructure['database_platform']}",
                    f"database_vendor={desired_infrastructure['database_vendor']}",
                ]
            )
        )
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
