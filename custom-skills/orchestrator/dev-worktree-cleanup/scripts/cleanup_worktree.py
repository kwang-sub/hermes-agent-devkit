#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

class CleanupError(RuntimeError):
    pass

def run(cmd, check=True):
    p = subprocess.run(cmd, text=True, capture_output=True)
    if check and p.returncode != 0:
        raise CleanupError(
            f"command failed ({p.returncode}): {' '.join(map(str, cmd))}\n"
            f"{(p.stderr or p.stdout).strip()}"
        )
    return p

def section_field(text: str, section: str, key: str) -> str:
    m = re.search(
        rf"(?ms)^{re.escape(section)}:\s*\n(?:(?:  .*\n)*)?^  {re.escape(key)}:\s*(.+?)\s*$",
        text,
    )
    if not m:
        raise CleanupError(f"missing metadata field: {section}.{key}")
    value = m.group(1).strip()
    try:
        decoded = json.loads(value)
        if isinstance(decoded, str):
            return decoded
    except Exception:
        pass
    return value.strip("'\"")

def parse_meta(repo: Path):
    path = repo / ".hermes" / "project.yaml"
    if not path.is_file():
        raise CleanupError(f"project metadata missing: {path}")
    text = path.read_text(encoding="utf-8")
    return {
        "project_id": section_field(text, "project", "id"),
        "repository": section_field(text, "project", "repository"),
        "board": section_field(text, "kanban", "board"),
        "base": section_field(text, "git", "default_base_branch"),
        "worktree_root": section_field(text, "git", "worktree_root"),
    }

def task_status(payload):
    if isinstance(payload, dict):
        if isinstance(payload.get("status"), str):
            return payload["status"]
        task = payload.get("task")
        if isinstance(task, dict) and isinstance(task.get("status"), str):
            return task["status"]
        data = payload.get("data")
        if isinstance(data, dict) and isinstance(data.get("status"), str):
            return data["status"]
    return None

def common_git_dir(path: Path) -> Path:
    p = run(["git", "-C", str(path), "rev-parse", "--path-format=absolute", "--git-common-dir"])
    return Path(p.stdout.strip()).resolve()

def registered_worktrees(repo: Path):
    p = run(["git", "-C", str(repo), "worktree", "list", "--porcelain"])
    paths = []
    for line in p.stdout.splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line[len("worktree "):]).resolve())
    return paths

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--task-key", required=True)
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--branch")
    ap.add_argument("--delete-branch-if-merged", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    top = run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"]).stdout.strip()
    if Path(top).resolve() != repo:
        raise CleanupError("--repo must be the source Git repository root")

    meta = parse_meta(repo)
    if Path(meta["repository"]).resolve() != repo:
        raise CleanupError("metadata repository does not match source repository")

    branch = args.branch or f"feature/{args.task_key}"
    target = (Path(meta["worktree_root"]) / args.task_key).resolve()

    # Kanban status gate.
    show = run([
        "hermes", "kanban", "--board", meta["board"],
        "show", args.task_id, "--json"
    ])
    try:
        payload = json.loads(show.stdout)
    except json.JSONDecodeError as exc:
        raise CleanupError(f"cannot parse Kanban task JSON: {exc}") from exc
    status = task_status(payload)
    if status not in {"done", "archived"}:
        raise CleanupError(f"Kanban task is not terminal: status={status!r}")

    listed = registered_worktrees(repo)
    if not target.exists() and target not in listed:
        print(f"PROJECT_ID={meta['project_id']}")
        print(f"TASK_KEY={args.task_key}")
        print(f"TASK_ID={args.task_id}")
        print(f"WORKTREE_PATH={target}")
        print(f"BRANCH={branch}")
        print(f"KANBAN_STATUS={status}")
        print("WORKTREE_ACTION=already-absent")
        print("BRANCH_ACTION=unchanged")
        print("STATUS=already-clean")
        return 0

    if target not in listed:
        raise CleanupError(f"target exists but is not a registered Git worktree: {target}")

    if common_git_dir(target) != common_git_dir(repo):
        raise CleanupError("target Worktree belongs to a different Git repository")

    actual_branch = run(["git", "-C", str(target), "branch", "--show-current"]).stdout.strip()
    if actual_branch != branch:
        raise CleanupError(f"branch mismatch: expected={branch}, actual={actual_branch}")

    dirty = run([
        "git", "-C", str(target),
        "status", "--porcelain=v1", "--untracked-files=all"
    ]).stdout.strip()
    if dirty:
        raise CleanupError(
            "worktree has unpublished/uncommitted changes; cleanup refused\n" + dirty
        )

    run(["git", "-C", str(repo), "worktree", "remove", str(target)])
    run(["git", "-C", str(repo), "worktree", "prune"])

    branch_action = "kept"
    if args.delete_branch_if_merged:
        exists = run(
            ["git", "-C", str(repo), "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            check=False,
        )
        if exists.returncode == 0:
            merged = run(
                ["git", "-C", str(repo), "merge-base", "--is-ancestor", branch, meta["base"]],
                check=False,
            )
            if merged.returncode == 0:
                run(["git", "-C", str(repo), "branch", "-d", branch])
                branch_action = "deleted-merged"
            else:
                branch_action = "kept-not-merged"
        else:
            branch_action = "already-absent"

    print(f"PROJECT_ID={meta['project_id']}")
    print(f"TASK_KEY={args.task_key}")
    print(f"TASK_ID={args.task_id}")
    print(f"WORKTREE_PATH={target}")
    print(f"BRANCH={branch}")
    print(f"KANBAN_STATUS={status}")
    print("WORKTREE_ACTION=removed")
    print(f"BRANCH_ACTION={branch_action}")
    print("STATUS=cleaned")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CleanupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
