#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys


class ReviewError(RuntimeError):
    pass


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise ReviewError((proc.stderr or proc.stdout).strip() or "command failed")
    return proc


def ensure_safe_directory(path: Path) -> None:
    resolved = str(path.resolve())
    current = run(["git", "config", "--global", "--get-all", "safe.directory"], check=False)
    configured = {line.strip() for line in current.stdout.splitlines() if line.strip()}
    if resolved not in configured:
        added = run(["git", "config", "--global", "--add", "safe.directory", resolved], check=False)
        if added.returncode != 0:
            raise ReviewError((added.stderr or added.stdout).strip() or f"cannot register safe.directory: {resolved}")


def resolve_commit(root: Path, value: str, label: str) -> str:
    resolved = run(["git", "-C", str(root), "rev-parse", "--verify", f"{value}^{{commit}}"], check=False)
    if resolved.returncode != 0:
        raise ReviewError(f"{label} does not resolve to a commit: {value}")
    return resolved.stdout.strip()


def normalize_includes(root: Path, values: list[str]) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    for raw in values:
        candidate = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        try:
            rel = candidate.relative_to(root)
        except ValueError as exc:
            raise ReviewError(f"included path is outside workspace: {raw}") from exc
        normalized.append(rel.as_posix())
    return sorted(dict.fromkeys(normalized))


def git_paths(root: Path, args: list[str], includes: list[str]) -> list[str]:
    cmd = ["git", "-C", str(root), *args]
    if includes:
        cmd.extend(["--", *includes])
    return [line.strip() for line in run(cmd).stdout.splitlines() if line.strip()]


def untracked_paths(root: Path, includes: list[str]) -> list[str]:
    all_paths = git_paths(root, ["ls-files", "--others", "--exclude-standard"], [])
    if not includes:
        return all_paths
    return [
        path for path in all_paths
        if any(path == inc or path.startswith(f"{inc.rstrip('/')}/") for inc in includes)
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-branch", required=True)
    ap.add_argument("--base-sha", required=True)
    ap.add_argument("--expected-branch", required=True)
    ap.add_argument("--workspace")
    ap.add_argument("--expected-workspace")
    ap.add_argument("--include", action="append", default=[])
    args = ap.parse_args()

    root = Path(args.workspace or ".").resolve()
    ensure_safe_directory(root)
    top = Path(run(["git", "-C", str(root), "rev-parse", "--show-toplevel"]).stdout.strip()).resolve()
    if top != root:
        raise ReviewError(f"review must start at workspace root: workspace={root}, root={top}")
    if args.expected_workspace and root != Path(args.expected_workspace).resolve():
        raise ReviewError(f"workspace mismatch: expected={Path(args.expected_workspace).resolve()}, actual={root}")

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

    includes = normalize_includes(root, args.include)
    raw_tracked = git_paths(root, ["diff", "--name-only", base_sha], includes)
    effective_tracked = git_paths(root, ["diff", "--name-only", "--ignore-cr-at-eol", base_sha], includes)
    eol_only = sorted(set(raw_tracked) - set(effective_tracked))
    untracked = untracked_paths(root, includes)

    diff_cmd = ["git", "-C", str(root), "diff", "--check", "--ignore-cr-at-eol", base_sha]
    if includes:
        diff_cmd.extend(["--", *includes])
    diff_check = run(diff_cmd, check=False)
    diff_output = "\n".join(part.strip() for part in (diff_check.stdout, diff_check.stderr) if part.strip())
    if diff_check.returncode not in (0, 1) or diff_output:
        raise ReviewError(diff_output or f"git diff --check failed with rc={diff_check.returncode}")

    print(f"WORKSPACE={root}")
    print(f"BRANCH={branch}")
    print(f"BASE_BRANCH={args.base_branch}")
    print(f"BASE_BRANCH_SHA={base_branch_sha}")
    print(f"BASE_SHA={base_sha}")
    print(f"BASE_BRANCH_DRIFTED={'true' if base_branch_sha != base_sha else 'false'}")
    print(f"SCOPE={'ALL' if not includes else ','.join(includes)}")
    print(f"TRACKED_CHANGED_COUNT={len(effective_tracked)}")
    for index, path in enumerate(effective_tracked, 1):
        print(f"TRACKED_{index}={path}")
    print(f"EOL_ONLY_COUNT={len(eol_only)}")
    for index, path in enumerate(eol_only, 1):
        print(f"EOL_ONLY_{index}={path}")
    print(f"UNTRACKED_COUNT={len(untracked)}")
    for index, path in enumerate(untracked, 1):
        print(f"UNTRACKED_{index}={path}")
    print("DIFF_CHECK=PASS")
    print("GIT_SAFE_DIRECTORY=true")
    print("STATUS=valid")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
