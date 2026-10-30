#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from pr_publish_lib import (
    PublishError,
    current_branch,
    emit,
    head_sha,
    list_open_prs,
    remote_head_sha,
    repo_root,
    resolve_workspace,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Read-only PR creation preflight")
    value.add_argument("--workspace", required=True)
    value.add_argument("--remote", default="origin")
    value.add_argument("--base", required=True)
    value.add_argument("--head", required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        workspace = resolve_workspace(args.workspace)
        root = repo_root(workspace)
        branch = current_branch(root)
        if branch != args.head:
            raise PublishError(f"head branch mismatch: expected {args.head}, got {branch}")
        if args.base == args.head:
            raise PublishError("PR base and head must differ")

        local = head_sha(root)
        remote = remote_head_sha(root, args.remote, args.head)
        if remote is None:
            raise PublishError(f"remote head does not exist: {args.remote}/{args.head}")
        if remote != local:
            raise PublishError(
                f"remote head differs from local HEAD: local={local} remote={remote}"
            )

        prs = list_open_prs(root, base=args.base, head=args.head)
        if prs:
            emit("STATUS", "existing-pr")
            emit("PR_NUMBER", prs[0].get("number", ""))
            emit("PR_URL", prs[0].get("url", ""))
            emit("PR_TITLE", prs[0].get("title", ""))
            return 0

        emit("STATUS", "ready")
        emit("BASE", args.base)
        emit("HEAD", args.head)
        emit("LOCAL_HEAD", local)
        emit("REMOTE_HEAD", remote)
        return 0
    except PublishError as exc:
        emit("STATUS", "blocked")
        print(f"ERROR={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
