#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
import re
import subprocess
import sys

class GuardError(RuntimeError):
    pass

def run(cmd: list[str], check=True):
    p = subprocess.run(cmd, text=True, capture_output=True)
    if check and p.returncode != 0:
        raise GuardError((p.stderr or p.stdout).strip() or "command failed")
    return p

def resolve_base_sha(root: Path, value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", value):
        raise GuardError("base SHA must be a full 40-character hexadecimal commit ID")
    resolved = run(["git", "-C", str(root), "rev-parse", "--verify", f"{value}^{{commit}}"], check=False)
    if resolved.returncode != 0:
        raise GuardError(f"base SHA does not resolve to a commit: {value}")
    return resolved.stdout.strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-key", required=True)
    ap.add_argument("--expected-branch", required=True)
    ap.add_argument("--base-sha", required=True)
    ap.add_argument("--workspace")
    ap.add_argument("--expected-workspace")
    args = ap.parse_args()

    workspace = Path(args.workspace or ".").resolve()
    top = run(["git", "-C", str(workspace), "rev-parse", "--show-toplevel"]).stdout.strip()
    root = Path(top).resolve()
    if root != workspace:
        raise GuardError(f"workspace must be the Git repository root: workspace={workspace}, root={root}")

    if args.expected_workspace and root != Path(args.expected_workspace).resolve():
        raise GuardError(
            f"workspace mismatch: expected={Path(args.expected_workspace).resolve()}, actual={root}"
        )

    branch = run(["git", "-C", str(root), "branch", "--show-current"]).stdout.strip()
    if branch != args.expected_branch:
        raise GuardError(f"branch mismatch: expected={args.expected_branch}, actual={branch}")

    inside = run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"]).stdout.strip()
    if inside != "true":
        raise GuardError("not inside Git workspace")

    base_sha = resolve_base_sha(root, args.base_sha)
    ancestor = run(["git", "-C", str(root), "merge-base", "--is-ancestor", base_sha, "HEAD"], check=False)
    if ancestor.returncode == 1:
        raise GuardError(f"base SHA is not an ancestor of HEAD: {base_sha}")
    if ancestor.returncode != 0:
        raise GuardError((ancestor.stderr or ancestor.stdout).strip() or "cannot compare base SHA to HEAD")

    print(f"WORKSPACE={root}")
    print(f"BRANCH={branch}")
    print(f"BASE_SHA={base_sha}")
    print(f"TASK_KEY={args.task_key}")
    print("GIT_WORKSPACE=true")
    print("STATUS=valid")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GuardError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
