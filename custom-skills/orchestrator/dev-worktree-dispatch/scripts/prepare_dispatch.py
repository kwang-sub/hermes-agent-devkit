#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


MANAGED_MARKER = "# managed-by: dev-project-bootstrap"


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
        description="Prepare an external relative Git worktree from .hermes/project.yaml."
    )
    p.add_argument("--task-key", required=True)
    p.add_argument(
        "--branch",
        help="Compatibility input. Must equal feature/<task-key> when supplied.",
    )
    p.add_argument(
        "--repo",
        help="Optional explicit repository root; default: current Git repository",
    )
    return p.parse_args()


def resolve_repo(explicit: str | None) -> Path:
    if explicit:
        start = Path(explicit)
        if not start.is_absolute():
            raise DispatchError(f"--repo must be absolute: {start}")
    else:
        start = Path.cwd()

    result = run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        check=False,
    )
    if result.returncode != 0:
        raise DispatchError(f"cannot resolve Git repository from: {start}")

    return Path(result.stdout.strip()).resolve()


def git_version() -> str:
    out = run(["git", "--version"]).stdout.strip()
    m = re.search(r"(\d+\.\d+\.\d+)", out)
    if not m:
        raise DispatchError(f"cannot parse Git version: {out}")
    return m.group(1)


def version_tuple(text: str) -> tuple[int, int, int]:
    parts = text.split(".")
    return tuple(int(x) for x in parts[:3])  # type: ignore[return-value]


def parse_managed_metadata(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise DispatchError(
            f"project metadata is missing: {path}\n"
            "Run dev-project-bootstrap before dispatch."
        )

    text = path.read_text(encoding="utf-8")

    if MANAGED_MARKER not in text.splitlines()[:5]:
        raise DispatchError(
            f"project metadata is not managed by dev-project-bootstrap: {path}"
        )

    def field(pattern: str, name: str) -> str:
        m = re.search(pattern, text, flags=re.MULTILINE)
        if not m:
            raise DispatchError(f"required metadata field is missing: {name}")
        return m.group(1).strip().strip("'\"")

    return {
        "project_id": field(r"^\s{2}id:\s*(.+?)\s*$", "project.id"),
        "repository": field(
            r"^\s{2}repository:\s*(.+?)\s*$", "project.repository"
        ),
        "board": field(
            r"^kanban:\s*\n\s{2}board:\s*(.+?)\s*$", "kanban.board"
        ),
        "base": field(
            r"^git:\s*\n\s{2}default_base_branch:\s*(.+?)\s*$",
            "git.default_base_branch",
        ),
        "worktree_root": field(
            r"^\s{2}worktree_root:\s*(.+?)\s*$", "git.worktree_root"
        ),
        "coder": field(
            r"^profiles:\s*\n(?:.*\n)*?\s{2}coder:\s*(.+?)\s*$",
            "profiles.coder",
        ),
        "reviewer": field(
            r"^profiles:\s*\n(?:.*\n)*?\s{2}reviewer:\s*(.+?)\s*$",
            "profiles.reviewer",
        ),
    }


def validate_task_key(task_key: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", task_key):
        raise DispatchError(
            "task key may contain only letters, digits, '.', '_' and '-'"
        )


def common_git_dir(repo: Path) -> Path:
    result = run(
        [
            "git",
            "-C",
            str(repo),
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
        ]
    )
    return Path(result.stdout.strip()).resolve()


def verify_relative_gitfile(target: Path) -> None:
    gitfile = target / ".git"
    if not gitfile.is_file():
        raise DispatchError(f"linked worktree .git file is missing: {gitfile}")

    first = gitfile.read_text(encoding="utf-8").splitlines()[0].strip()
    if not first.startswith("gitdir: "):
        raise DispatchError(f"unexpected worktree .git contents: {first}")

    link = first[len("gitdir: "):].strip()

    # Unix absolute path. This is the problematic format for Docker/Windows sharing.
    if link.startswith("/"):
        raise DispatchError(
            f"absolute Linux gitdir metadata detected; relative metadata required: {first}"
        )


def verify_worktree(
    *,
    repo: Path,
    target: Path,
    branch: str,
) -> None:
    inside = run(
        ["git", "-C", str(target), "rev-parse", "--is-inside-work-tree"],
        check=False,
    )
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        raise DispatchError(f"target is not a valid Git worktree: {target}")

    actual_branch = run(
        ["git", "-C", str(target), "branch", "--show-current"]
    ).stdout.strip()
    if actual_branch != branch:
        raise DispatchError(
            f"target branch mismatch: expected={branch}, actual={actual_branch}"
        )

    verify_relative_gitfile(target)

    source_common = common_git_dir(repo)
    target_common = common_git_dir(target)
    if source_common != target_common:
        raise DispatchError(
            "existing target belongs to a different Git repository: "
            f"source-common={source_common}, target-common={target_common}"
        )

    relative_ext = run(
        ["git", "-C", str(repo), "config", "--get", "extensions.relativeWorktrees"],
        check=False,
    ).stdout.strip().lower()
    if relative_ext != "true":
        raise DispatchError(
            "extensions.relativeWorktrees is not true for the source repository"
        )


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def main() -> int:
    args = parse_args()
    validate_task_key(args.task_key)

    version = git_version()
    if version_tuple(version) < version_tuple("2.48.0"):
        raise DispatchError(f"Git >= 2.48.0 is required; found {version}")

    repo = resolve_repo(args.repo)
    metadata_path = repo / ".hermes" / "project.yaml"
    meta = parse_managed_metadata(metadata_path)

    configured_repo = Path(meta["repository"]).resolve()
    if configured_repo != repo:
        raise DispatchError(
            f"project metadata repository mismatch: "
            f"metadata={configured_repo}, actual={repo}"
        )

    base = meta["base"]
    verify_base = run(
        ["git", "-C", str(repo), "rev-parse", "--verify", f"{base}^{{commit}}"],
        check=False,
    )
    if verify_base.returncode != 0:
        raise DispatchError(f"configured base branch/ref does not resolve: {base}")

    expected_branch = f"feature/{args.task_key}"
    if args.branch and args.branch != expected_branch:
        raise DispatchError(
            f"task branch must follow feature/<TASK-KEY>: "
            f"expected={expected_branch}, requested={args.branch}"
        )
    branch = expected_branch
    check_branch = run(
        ["git", "check-ref-format", "--branch", branch],
        check=False,
    )
    if check_branch.returncode != 0:
        raise DispatchError(f"invalid branch name: {branch}")

    worktree_root = Path(meta["worktree_root"])
    if not worktree_root.is_absolute():
        raise DispatchError(
            f"configured worktree root must be absolute: {worktree_root}"
        )

    target = (worktree_root / args.task_key).resolve()

    if is_inside(target, repo):
        raise DispatchError(
            f"worktree target must be outside source repository: {target}"
        )

    reused = False

    if target.exists():
        verify_worktree(repo=repo, target=target, branch=branch)
        reused = True
    else:
        branch_exists = run(
            [
                "git",
                "-C",
                str(repo),
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{branch}",
            ],
            check=False,
        )
        if branch_exists.returncode == 0:
            raise DispatchError(
                f"local branch already exists but expected Worktree path does not: {branch}\n"
                "Refusing implicit reuse."
            )

        target.parent.mkdir(parents=True, exist_ok=True)

        run(
            [
                "git",
                "-C",
                str(repo),
                "worktree",
                "add",
                "--relative-paths",
                "-b",
                branch,
                str(target),
                base,
            ]
        )

        verify_worktree(repo=repo, target=target, branch=branch)

    print(f"PROJECT_ID={meta['project_id']}")
    print(f"REPO_ROOT={repo}")
    print(f"BOARD={meta['board']}")
    print(f"BASE_BRANCH={base}")
    print(f"WORKTREE_ROOT={worktree_root}")
    print(f"WORKTREE_PATH={target}")
    print(f"WORKSPACE=dir:{target}")
    print(f"ASSIGNEE={meta['coder']}")
    print(f"REVIEWER={meta['reviewer']}")
    print(f"TASK_KEY={args.task_key}")
    print(f"BRANCH={branch}")
    print(f"REUSED={'true' if reused else 'false'}")
    print("STATUS=prepared")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DispatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
