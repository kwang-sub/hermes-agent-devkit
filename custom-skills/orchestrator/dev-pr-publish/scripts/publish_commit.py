#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from pr_publish_lib import (
    PublishError,
    current_branch,
    emit,
    head_sha,
    publish_fingerprint,
    repo_root,
    resolve_workspace,
    run,
    validate_conventional_commit,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Commit approved changes and push without force")
    value.add_argument("--workspace", required=True)
    value.add_argument("--remote", default="origin")
    value.add_argument("--branch", required=True)
    value.add_argument("--fingerprint", required=True)
    value.add_argument("--message", required=True)
    value.add_argument("--include", action="append", default=[])
    return value


def staged_paths(root) -> list[str]:
    result = run(["git", "diff", "--cached", "--name-only", "-z"], cwd=root, text=False)
    return [
        item.decode("utf-8", "surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    ]


def path_is_in_scope(path: str, includes: list[str]) -> bool:
    if not includes:
        return True
    from pathlib import PurePosixPath

    candidate = PurePosixPath(path)
    for raw in includes:
        scope = PurePosixPath(raw.rstrip("/"))
        if candidate == scope or scope in candidate.parents:
            return True
    return False


def main() -> int:
    args = parser().parse_args()
    commit_sha = None
    try:
        workspace = resolve_workspace(args.workspace)
        root = repo_root(workspace)
        branch = current_branch(root)
        if branch != args.branch:
            raise PublishError(f"branch changed after approval: expected {args.branch}, got {branch}")

        validate_conventional_commit(args.message)

        current = publish_fingerprint(root, args.include)
        if current != args.fingerprint:
            raise PublishError(
                "publish fingerprint changed after approval; regenerate commit preview and approve again"
            )

        if args.include:
            outside = [path for path in staged_paths(root) if not path_is_in_scope(path, args.include)]
            if outside:
                raise PublishError(
                    "staged changes outside the approved publish scope: " + ", ".join(outside)
                )
            run(["git", "add", "-A", "--", *args.include], cwd=root)
        else:
            run(["git", "add", "-A", "--", "."], cwd=root)

        if run(["git", "diff", "--cached", "--quiet"], cwd=root, check=False).returncode == 0:
            raise PublishError("approved publish scope produced no staged changes")

        run(["git", "commit", "-m", args.message], cwd=root)
        commit_sha = head_sha(root)

        push = run(
            ["git", "push", "--set-upstream", args.remote, args.branch],
            cwd=root,
            check=False,
        )
        if push.returncode != 0:
            detail = (push.stdout + "\n" + push.stderr).strip()
            emit("STATUS", "push-failed")
            emit("COMMIT_SHA", commit_sha)
            print(f"ERROR=push rejected; force push is forbidden\n{detail}", file=sys.stderr)
            return 3

        emit("STATUS", "pushed")
        emit("COMMIT_SHA", commit_sha)
        emit("BRANCH", args.branch)
        emit("REMOTE", args.remote)
        return 0
    except PublishError as exc:
        emit("STATUS", "blocked")
        if commit_sha:
            emit("COMMIT_SHA", commit_sha)
        print(f"ERROR={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
