#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
import re
import subprocess
import sys

class ReviewError(RuntimeError):
    pass

def run(cmd, check=True):
    p = subprocess.run(cmd, text=True, capture_output=True)
    if check and p.returncode != 0:
        raise ReviewError((p.stderr or p.stdout).strip() or "command failed")
    return p

def resolve_commit(root: Path, value: str, label: str) -> str:
    resolved = run(["git", "-C", str(root), "rev-parse", "--verify", f"{value}^{{commit}}"], check=False)
    if resolved.returncode != 0:
        raise ReviewError(f"{label} does not resolve to a commit: {value}")
    return resolved.stdout.strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-branch", required=True)
    ap.add_argument("--base-sha", required=True)
    ap.add_argument("--expected-branch", required=True)
    ap.add_argument("--workspace")
    ap.add_argument("--expected-workspace")
    args = ap.parse_args()

    root = Path(args.workspace or ".").resolve()
    top = Path(run(["git", "-C", str(root), "rev-parse", "--show-toplevel"]).stdout.strip()).resolve()
    if top != root:
        raise ReviewError(f"review must start at workspace root: workspace={root}, root={top}")
    if args.expected_workspace and root != Path(args.expected_workspace).resolve():
        raise ReviewError(
            f"workspace mismatch: expected={Path(args.expected_workspace).resolve()}, actual={root}"
        )

    branch = run(["git", "-C", str(root), "branch", "--show-current"]).stdout.strip()
    if branch != args.expected_branch:
        raise ReviewError(f"branch mismatch: expected={args.expected_branch}, actual={branch}")

    if not re.fullmatch(r"[0-9a-fA-F]{40}", args.base_sha):
        raise ReviewError("base SHA must be a full 40-character hexadecimal commit ID")
    base_sha = resolve_commit(root, args.base_sha, "base SHA")
    base_branch_sha = resolve_commit(root, args.base_branch, "base branch/ref")
    ancestor = run(["git", "-C", str(root), "merge-base", "--is-ancestor", base_sha, "HEAD"], check=False)
    if ancestor.returncode == 1:
        raise ReviewError(f"base SHA is not an ancestor of HEAD: {base_sha}")
    if ancestor.returncode != 0:
        raise ReviewError((ancestor.stderr or ancestor.stdout).strip() or "cannot compare base SHA to HEAD")

    status = run(["git", "-C", str(root), "status", "--short", "--untracked-files=all"]).stdout.splitlines()
    tracked = run(["git", "-C", str(root), "diff", "--name-only", base_sha, "--"]).stdout.splitlines()
    untracked = run(["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"]).stdout.splitlines()
    diff_check = run(["git", "-C", str(root), "diff", "--check"], check=False)

    print(f"WORKSPACE={root}")
    print(f"BRANCH={branch}")
    print(f"BASE_BRANCH={args.base_branch}")
    print(f"BASE_BRANCH_SHA={base_branch_sha}")
    print(f"BASE_SHA={base_sha}")
    print(f"BASE_BRANCH_DRIFTED={'true' if base_branch_sha != base_sha else 'false'}")
    print(f"TRACKED_CHANGED_COUNT={len(tracked)}")
    for i, path in enumerate(tracked, 1):
        print(f"TRACKED_{i}={path}")
    print(f"UNTRACKED_COUNT={len(untracked)}")
    for i, path in enumerate(untracked, 1):
        print(f"UNTRACKED_{i}={path}")
    print(f"STATUS_LINE_COUNT={len(status)}")
    print(f"DIFF_CHECK={'PASS' if diff_check.returncode == 0 else 'FAIL'}")
    if diff_check.returncode != 0:
        raise ReviewError((diff_check.stderr or diff_check.stdout).strip() or "git diff --check failed")
    print("STATUS=valid")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
