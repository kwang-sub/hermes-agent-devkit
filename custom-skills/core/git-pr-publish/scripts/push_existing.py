#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from pr_publish_lib import (
    PublishError,
    classify_changed_rows,
    current_branch,
    emit,
    head_sha,
    push_command,
    remote_head_sha,
    repo_root,
    resolve_workspace,
    run,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Push an already-committed branch without creating a new commit."
    )
    value.add_argument("--workspace", required=True)
    value.add_argument("--remote", default="origin")
    value.add_argument("--branch", required=True)
    value.add_argument("--expected-head", required=True)
    value.add_argument("--include", action="append", default=[])
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        workspace = resolve_workspace(args.workspace)
        root = repo_root(workspace)
        branch = current_branch(root)
        if branch != args.branch:
            raise PublishError(
                f"branch changed after approval: expected {args.branch}, got {branch}"
            )

        local_head = head_sha(root)
        if local_head != args.expected_head:
            raise PublishError(
                f"HEAD changed after approval: expected {args.expected_head}, got {local_head}"
            )

        semantic_rows, eol_only_rows = classify_changed_rows(root, args.include)
        if semantic_rows:
            raise PublishError(
                "semantic working-tree changes exist; use the commit preview flow before pushing"
            )

        before = remote_head_sha(root, args.remote, args.branch)
        if before == local_head:
            emit("STATUS", "already-pushed")
            emit("BRANCH", branch)
            emit("HEAD_SHA", local_head)
            emit("EOL_ONLY_COUNT", len(eol_only_rows))
            return 0

        pushed = run(push_command(root, args.remote, args.branch), cwd=root, check=False)
        if pushed.returncode != 0:
            detail = (pushed.stdout + "\n" + pushed.stderr).strip()
            emit("STATUS", "push-failed")
            print(f"ERROR=push rejected; force push is forbidden\n{detail}", file=sys.stderr)
            return 3

        after = remote_head_sha(root, args.remote, args.branch)
        if after != local_head:
            raise PublishError(
                f"remote head mismatch after push: expected {local_head}, got {after or '<missing>'}"
            )

        emit("STATUS", "pushed-existing-head")
        emit("BRANCH", branch)
        emit("HEAD_SHA", local_head)
        emit("EOL_ONLY_COUNT", len(eol_only_rows))
        return 0
    except PublishError as exc:
        emit("STATUS", "blocked")
        print(f"ERROR={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
